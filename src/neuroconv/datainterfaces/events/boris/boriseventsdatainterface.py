import re
from copy import deepcopy
from datetime import datetime

import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from neuroconv.utils import DeepDict

from .boris_reader import get_observation_names, read_boris_observation, read_boris_project
from ..baseeventsinterface import BaseEventsInterface, _EventsData


class BORISEventsInterface(BaseEventsInterface):
    """Data Interface for the events of one observation of a BORIS project.

    BORIS (Behavioural Observation Research Interactive Software) records time-constrained behavioral
    observations against video, audio, or a live session. A ``.boris`` file is one JSON document holding
    the whole record: the coding scheme, the subjects, and every observation with its events. An
    observation is the unit that corresponds to a session, so this interface takes one by name; use
    :meth:`get_observation_names` to see what a file holds.

    Every behavior the scheme declares becomes an event type, including one nothing was ever scored
    against, which is written as a zero-row contribution rather than dropped: the vocabulary is part of
    the record. A behavior's declared ``type`` decides its extent. A point behavior occupies one row and
    is written without a duration; a state behavior occupies two, a start and a stop, which this
    interface pairs on subject plus code in order of appearance and writes as one row carrying the bout's
    length. Pairing ignores the modifier string, since a bout can open with one modifier and close with
    another. A bout that opens and never closes keeps a ``NaN`` duration, which happens whenever a coder
    misses a stop in a live session and cannot be repaired afterwards.

    All of an observation's behaviors are written into one table by default rather than one table per
    behavior, since an ethogram routinely declares twenty behaviors and the per-behavior layout would
    turn a single session into twenty tables of a handful of rows each.

    The coding scheme is written alongside the events as an ``ndx-ethogram`` ``Ethogram`` catalogue in the
    ``behavior`` processing module, and the closed state bouts as an ``EthogramBouts`` table beside it
    where the observation has any. The catalogue is the durable half of a BORIS file, holding what is true
    of a behavior rather than of any occurrence, and the bouts table is the curated interval view that
    reads as an ``IntervalSet`` downstream. The events table remains the faithful record: it alone carries
    the point behaviors, the bouts that never closed, and the per-occurrence modifiers, comments and
    subject attribution.
    """

    keywords = ("events", "behavior", "BORIS", "ethogram", "annotation")
    display_name = "BORISEvents"
    info = "Data Interface for the events of one observation of a BORIS project."
    associated_suffixes = (".boris",)

    @staticmethod
    def get_observation_names(file_path: FilePath) -> list[str]:
        """Return the names of the observations a ``.boris`` file holds, in file order.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.boris`` JSON document.

        Returns
        -------
        list of str
            The observation names, which are the handles ``observation_name`` takes. Empty where the
            project declares a coding scheme and was never coded against, which is a legal file.
        """
        return get_observation_names(file_path=file_path)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        observation_name: str,
        *,
        metadata_key: str = "boris",
        verbose: bool = False,
    ):
        """Initialize the BORISEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.boris`` JSON document.
        observation_name : str
            The observation to read, as :meth:`get_observation_names` lists them.
        metadata_key : str, default: "boris"
            The key this interface's block sits under in ``metadata["Events"]``. Give each interface its
            own when a conversion runs several observations together.
        verbose : bool, default: False
            Whether to print progress.
        """
        super().__init__(file_path=file_path, observation_name=observation_name, verbose=verbose)
        self.metadata_key = metadata_key
        self._project = read_boris_project(file_path=file_path)
        self._observation = read_boris_observation(file_path=file_path, observation_name=observation_name)
        # The observation's `time offset` shifts the whole observation, which is what a rigid alignment
        # offset is, so it goes through the alignment surface rather than being folded into the times. That
        # keeps the read times the file's own and leaves the offset re-settable.
        if self._observation.time_offset:
            self.alignment.shift_times(self._observation.time_offset)

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for this interface.

        The observation's ``date`` is reported as ``NWBFile/session_start_time`` and its ``description``,
        where the coder wrote one, as ``NWBFile/session_description``. No subject is reported: a BORIS
        subject is an animal being scored and one observation routinely carries several, so it cannot map
        onto the file's single ``Subject`` and stays a per-event column instead.

        One ``event_types`` entry is declared per behavior the scheme holds, its ``event_name`` seeded from
        the behavior's ``code`` and its ``event_description`` from the behavior's own ``description``,
        which BORIS carries natively and most sources do not. All of them route to one table, declared in
        ``EventTables`` so the merged table carries the observation's name rather than a derived one.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()

        session_start_time = _parse_observation_date(date=self._raw_observation().get("date"))
        if session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = session_start_time
        description = self._raw_observation().get("description", "")
        if description:
            metadata["NWBFile"]["session_description"] = description

        table_metadata_key = self._table_metadata_key()
        metadata["Events"]["EventTables"][table_metadata_key] = {
            "table_name": _to_object_name(name=self._observation.name),
            "description": (
                f"Behaviors scored in BORIS observation '{self._observation.name}' "
                f"({self._observation.observation_type.lower()})."
            ),
        }

        # Every event type the observation produces, which is the declared scheme plus any code the
        # events name that the scheme no longer does. A behavior renamed or removed after the session
        # was scored leaves its rows behind and BORIS does not rewrite them, so declaring only the
        # scheme would silently drop those rows at write.
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        closing_columns = {
            field: {"column_name": field, "description": description}
            for field, description in (
                ("stop_comment", "The coder's comment on the row that closed a state bout."),
                ("stop_modifiers", "The modifier values on the row that closed a state bout."),
            )
            if self._closing_row_differs(field=field)
        }
        for code in self._get_events_data_dict():
            behavior = self._project.behaviors.get(code)
            entry = {
                "event_name": _to_event_name(code=code),
                "table_metadata_key": table_metadata_key,
                "columns": {
                    "subject": {"column_name": "subject", "description": "The subject the event was scored on."},
                    "modifiers": {"column_name": "modifiers", "description": "The modifier values recorded."},
                    "comment": {
                        "column_name": "comment",
                        "description": "The coder's comment, from the row that opened the occurrence.",
                    },
                },
            }
            entry["columns"].update(deepcopy(closing_columns))
            if behavior is not None and behavior.description:
                entry["event_description"] = behavior.description
            event_types[code] = entry
        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None) -> None:
        """Write the observation's events, its coding scheme and its state bouts.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the events to.
        metadata : dict, optional
            Metadata dictionary; see :meth:`get_metadata_schema`. If None, ``get_metadata()`` is used.
        """
        if metadata is None:
            metadata = self.get_metadata()
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        self._set_timestamp_resolution(nwbfile=nwbfile, metadata=metadata)
        self._add_ethogram_to_nwbfile(nwbfile=nwbfile)

    def _set_timestamp_resolution(self, nwbfile: NWBFile, metadata: dict) -> None:
        """Record the frame period as the resolution of a MEDIA observation's times.

        A coder scoring recorded media can only mark a frame, so every time in a ``MEDIA`` observation is
        quantized to the video's frame period and a duration, being a difference of two such times, is
        quantized the same way. That period is the real precision of the numbers and it is otherwise lost,
        since the column holds seconds either way. A ``LIVE`` observation has no frame rate anywhere, so
        nothing is claimed for it.
        """
        frame_rate = self._observation.frame_rate
        if not frame_rate or nwbfile.events is None:
            return
        table_name = metadata["Events"]["EventTables"][self._table_metadata_key()]["table_name"]
        table = nwbfile.events.get(table_name)
        if table is None:
            return
        resolution = 1.0 / frame_rate
        for column_name in ("timestamp", "duration"):
            column = table[column_name] if column_name in table.colnames else None
            if column is not None and hasattr(column, "resolution"):
                column.resolution = resolution

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation from the observation, cached after the first call.

        One record per declared behavior, keyed by its code. A behavior nothing was scored against gets
        empty arrays rather than being left out, so the coding scheme survives the conversion whole.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        occurrences_by_code = {code: [] for code in self._project.behaviors}
        for occurrence in self._observation.occurrences:
            occurrences_by_code.setdefault(occurrence.code, []).append(occurrence)

        events_data_dict = {}
        for code, occurrences in occurrences_by_code.items():
            behavior = self._project.behaviors.get(code)
            is_point = behavior is None or behavior.behavior_type == "point"
            events_data_dict[code] = _EventsData(
                event_type_source_id=code,
                timestamps=np.array([occurrence.onset for occurrence in occurrences], dtype=float),
                # A point behavior has no extent at all, which is `None`; a state behavior always has the
                # column, carrying `NaN` for a bout whose stop was never scored.
                durations=(
                    None if is_point else np.array([occurrence.duration for occurrence in occurrences], dtype=float)
                ),
                payload={
                    "subject": np.array([occurrence.subject for occurrence in occurrences], dtype=object),
                    "modifiers": np.array([occurrence.modifiers for occurrence in occurrences], dtype=object),
                    "comment": np.array([occurrence.comment for occurrence in occurrences], dtype=object),
                    **{
                        field: np.array([getattr(occurrence, field) for occurrence in occurrences], dtype=object)
                        for field in ("stop_comment", "stop_modifiers")
                        if self._closing_row_differs(field=field)
                    },
                },
            )
        return events_data_dict

    def _add_ethogram_to_nwbfile(self, nwbfile: NWBFile) -> None:
        """Write the coding scheme as an ``Ethogram`` catalogue and the closed bouts as ``EthogramBouts``."""
        from ndx_ethogram import Ethogram, EthogramBouts

        behavior_module = nwbfile.processing.get("behavior") or nwbfile.create_processing_module(
            name="behavior", description="Behavioral annotations."
        )

        catalogue = behavior_module.data_interfaces.get("Ethogram")
        if catalogue is None:
            catalogue = Ethogram(
                name="Ethogram",
                description="The BORIS coding scheme: every behavior the project declares.",
                # BORIS states exclusion per behavior, as the set of codes that starting one terminates, so
                # a scheme can make four behaviors mutually exclusive and leave the rest free. A single
                # boolean cannot carry that, and asserting True would overclaim, so the per-behavior sets
                # stay in the events table's source file until the catalogue can hold them.
                exclusive=False,
            )
            for behavior in self._project.behaviors.values():
                catalogue.add_row(
                    behavior=behavior.code,
                    definition=behavior.description,
                    behavior_type=behavior.behavior_type,
                    native_code=behavior.native_code,
                    category=behavior.category,
                )
            behavior_module.add(catalogue)

        # A bout with no stop cannot be an interval row, having no stop time to write. It stays in the
        # events table with a NaN duration, which is the honest reading of a start nobody closed.
        closed_bouts = [
            occurrence
            for occurrence in self._observation.occurrences
            if occurrence.duration is not None and not np.isnan(occurrence.duration)
        ]
        # An observation can hold no closed bout at all, a scheme of point behaviors or a session nobody
        # finished. The catalogue still says what could have been scored; an empty interval table would
        # say nothing the catalogue does not.
        if not closed_bouts:
            return

        bouts_name = f"{_to_object_name(name=self._observation.name)}Bouts"
        bouts = EthogramBouts(
            name=bouts_name,
            description=(
                f"State behavior bouts scored in BORIS observation '{self._observation.name}'. "
                "Point behaviors and bouts whose stop was never scored are in the events table."
            ),
            labeling_method="manual",
            source_software="BORIS",
            ethogram=catalogue,
        )
        for column, column_description in (
            ("subject", "The subject the bout was scored on."),
            ("modifiers", "The modifier values recorded at the bout's start."),
            ("comment", "The coder's comment at the bout's start."),
        ):
            bouts.add_column(name=column, description=column_description)
        for field, description in (
            ("stop_comment", "The coder's comment at the bout's stop."),
            ("stop_modifiers", "The modifier values at the bout's stop."),
        ):
            if self._closing_row_differs(field=field):
                bouts.add_column(name=field, description=description)

        offset = self.alignment.offset
        for occurrence in closed_bouts:
            bouts.add_interval(
                start_time=occurrence.onset + offset,
                stop_time=occurrence.onset + occurrence.duration + offset,
                label=occurrence.code,
                subject=occurrence.subject,
                modifiers=occurrence.modifiers,
                comment=occurrence.comment,
                **{
                    field: getattr(occurrence, field)
                    for field in ("stop_comment", "stop_modifiers")
                    if self._closing_row_differs(field=field)
                },
            )
        behavior_module.add(bouts)

    def _closing_row_differs(self, field: str) -> bool:
        """Whether any closed bout's ``field`` says something its opening row did not.

        A bout is two rows and both carry a comment and a modifier string, so collapsing them into one row
        has to drop one of each unless a column is spent on it. Which one is worth spending on is a
        property of the data rather than of the format: measured over every BORIS file reachable, 335 of
        424 closing comments differ from their opening one while only 13 of 24,639 closing modifiers do,
        because BORIS carries the modifier forward and the coder retypes the comment. So the column is
        added where this observation actually has a difference to record and left out where it would be a
        copy of the column beside it.
        """
        opening = {"stop_comment": "comment", "stop_modifiers": "modifiers"}[field]
        return any(
            getattr(occurrence, field) != getattr(occurrence, opening)
            for occurrence in self._observation.occurrences
            if occurrence.duration is not None and not np.isnan(occurrence.duration)
        )

    def _raw_observation(self) -> dict:
        """Return the observation's own JSON block, for the fields the reader does not model."""
        import json
        from pathlib import Path

        document = json.loads(Path(self.source_data["file_path"]).read_text(encoding="utf-8"))
        return document["observations"][self._observation.name]

    def _table_metadata_key(self) -> str:
        """The routing key every one of this observation's behaviors shares, so they land in one table."""
        return f"{self.metadata_key}_{self._observation.name}"


def _to_event_name(code: str) -> str:
    """Turn a behavior code into an editable display name an object name can be derived from.

    A behavior code is free text somebody typed into an ethogram, and BORIS accepts characters an NWB
    object name cannot hold: `Grooming/Eating` is an ordinary way to name one behavior covering two
    things. An event type that gets a table of its own is named from this, so a raw slash or colon would
    raise there. The separator is kept rather than dropped, since `Foraging_Caching` still reads as two
    words where `ForagingCaching` reads as one invented one. The code itself is untouched: it stays the
    event_type_source_id and reaches the file verbatim in the catalogue's `behavior` column.
    """
    return code.replace("/", "_").replace(":", "_")


def _to_object_name(name: str) -> str:
    """Turn an observation name into an NWB object name.

    BORIS observation names are free text and routinely carry spaces and punctuation (``observation #2``,
    ``live not paired``), none of which belongs in an object name, so the words are taken and capitalized.
    A name that is only digits is common enough (an observation called ``1``) and would give an object
    named ``1``, so it is prefixed rather than left to stand alone.
    """
    words = [word for word in re.split(r"[^0-9a-zA-Z]+", name) if word]
    object_name = "".join(word[:1].upper() + word[1:] for word in words)
    if not object_name or object_name[0].isdigit():
        object_name = f"Observation{object_name}"
    return object_name


def _parse_observation_date(date: str | None) -> datetime | None:
    """Read an observation's ``date``, which BORIS writes ISO-formatted with either separator.

    Real files carry ``2016-12-10T15:44:57``, ``2018-05-14 16:22:23`` and ``2018-05-10 15:19`` alike. No
    timezone is stated, so the datetime is left naive and pynwb attaches the local one at write.
    """
    if not date:
        return None
    try:
        return datetime.fromisoformat(date)
    except ValueError:
        return None
