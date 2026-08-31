import re
from datetime import datetime

import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from neuroconv.utils import DeepDict

from .boris_reader import (
    get_observation_names,
    read_boris_observation,
    read_boris_project,
    strip_modifier_shortcut,
)
from ...events.baseeventsinterface import BaseEventsInterface, _EventsData


class BORISInterface(BaseEventsInterface):
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

    All of an observation's behaviors are written into one table by default. A behavior may declare
    modifier slots, the qualifiers a coder answers whenever they score it (``Walking`` asking for a speed
    and a direction), and each slot becomes a column named after it rather than surviving as the
    ``|``-joined string BORIS records; a behavior that declares no such slot writes an empty cell there.
    The column is named after the slot rather than its position, so a slot two behaviors both ask is one
    column and can be queried across them, and a slot the scheme leaves unnamed falls back to its
    position. What each column means per behavior is on the catalogue, in ``modifiers``, along with the
    menu each offers in ``modifier_values``.

    The layout is stated in ``get_metadata`` rather than fixed in the writer, so a behavior is routed
    into a table of its own by giving its ``event_types`` entry its own ``table_metadata_key`` and naming
    it in ``EventTables``. Merging is the default because a modifier slot is rare in real projects: half
    of them declare none at all, so one table per behavior would buy density that is usually not missing
    and pay one NWB object per declared behavior for it.

    The coding scheme is written alongside the events as an ``ndx-ethogram`` ``Ethogram`` catalogue in the
    ``behavior`` processing module, and the closed state bouts as an ``EthogramBouts`` table beside it
    where the observation has any. The catalogue is the durable half of a BORIS file, holding what is true
    of a behavior rather than of any occurrence, and the bouts table is the curated interval view that
    reads as an ``IntervalSet`` downstream. The events table remains the faithful record: it alone carries
    the point behaviors, the bouts that never closed, and the per-occurrence modifier answers, comments
    and subject attribution.
    """

    keywords = ("events", "behavior", "BORIS", "ethogram", "annotation")
    display_name = "BORIS"
    info = "Data Interface for one observation of a BORIS project."
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
        """Initialize the BORISInterface.

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

        session_start_time = _parse_observation_date(date=self._observation.date)
        if session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = session_start_time
        description = self._observation.description
        if description:
            metadata["NWBFile"]["session_description"] = description

        # Every event type the observation produces, which is the declared scheme plus any code the
        # events name that the scheme no longer does. A behavior renamed or removed after the session
        # was scored leaves its rows behind and BORIS does not rewrite them, so declaring only the
        # scheme would silently drop those rows at write.
        #
        # The layout is stated here rather than fixed in the writer, so it is a metadata edit away.
        # Every behavior routes into one table by default, because a modifier slot is rare in real
        # projects: half of them declare none at all, and the median observation needs no modifier
        # column, so one table per behavior would buy density that is almost never missing and pay for
        # it in one NWB object per declared behavior. Giving a behavior its own `table_metadata_key`,
        # and naming it in `EventTables`, is what splits it back out.
        table_metadata_key = self._table_metadata_key()
        metadata["Events"]["EventTables"][table_metadata_key] = {
            "table_name": _to_object_name(name=self._observation.name),
            "description": (
                f"Behaviors scored in BORIS observation '{self._observation.name}' "
                f"({self._observation.observation_type.lower()})."
            ),
        }
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        for code, events_data in self._get_events_data_dict().items():
            behavior = self._project.behaviors.get(code)
            entry = {
                "event_name": _to_event_name(code=code),
                "table_metadata_key": table_metadata_key,
                # One column per payload field the read produced, which is subject, comment, whichever
                # closing-row fields say something new, and one per modifier slot this behavior declares.
                "columns": {
                    field: self._column_spec(field=field, values=events_data.payload[field])
                    for field in events_data.payload
                },
            }
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
        resolution = 1.0 / frame_rate
        table_name = metadata["Events"]["EventTables"][self._table_metadata_key()]["table_name"]
        table = nwbfile.events.get(table_name)
        if table is None:
            return
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

        # Whether a closing-row column earns its place is a property of the observation, not of any one
        # behavior, so it is settled once here rather than re-walked for every code.
        closing_comment = self._closing_row_differs(field="stop_comment")
        closing_modifiers = self._closing_row_differs(field="stop_modifiers")
        # Each behavior writes only its own slots, since it has a table to itself.
        modifier_columns = {
            code: self._modifier_column_names(code=code, occurrences=occurrences)
            for code, occurrences in occurrences_by_code.items()
        }

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
                    "comment": np.array([occurrence.comment for occurrence in occurrences], dtype=object),
                    # A modifier is one answer per declared slot, so it gets one column per slot rather
                    # than the `|`-joined string BORIS records. Which slot each column is stays on the
                    # catalogue, since it is a property of the behavior and not of any occurrence.
                    **{
                        column_name: np.array(
                            [_modifier_answer(occurrence=occurrence, position=position) for occurrence in occurrences],
                            dtype=object,
                        )
                        for position, column_name in enumerate(modifier_columns[code])
                    },
                    **(
                        {
                            "stop_comment": np.array(
                                [occurrence.stop_comment for occurrence in occurrences], dtype=object
                            )
                        }
                        if closing_comment
                        else {}
                    ),
                    # A bout closes on its own modifier row, and BORIS carries the opening answer forward,
                    # so this says something new only where the coder changed it mid-bout. It is split the
                    # same way rather than left as the raw string, so `None` reads as unanswered here too.
                    **{
                        f"stop_{column_name}": np.array(
                            [
                                _modifier_answer(occurrence=occurrence, position=position, field="stop_modifier_values")
                                for occurrence in occurrences
                            ],
                            dtype=object,
                        )
                        for position, column_name in enumerate(modifier_columns[code] if closing_modifiers else [])
                    },
                },
            )
        self._events_data_dict = events_data_dict
        return self._events_data_dict

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
            # A behavior's modifier slots are a property of the behavior rather than of any occurrence,
            # so they belong here. The menu is written as BORIS records it, with the keyboard shortcut
            # stripped, so a declared value and a recorded answer are the same string.
            #
            # Written only where some behavior declares a slot. Half of real projects declare none at
            # all, and a ragged column whose every row is an empty list gives hdmf no dtype to infer, so
            # writing it unconditionally fails at write rather than storing an empty column.
            declares_modifiers = any(behavior.modifier_slots for behavior in self._project.behaviors.values())
            if declares_modifiers:
                catalogue.add_column(
                    name="modifiers",
                    description=(
                        "The modifier slots this behavior declares, named as the scheme names them and in "
                        "the order it declares them. Empty where the behavior declares no modifiers."
                    ),
                    index=True,
                )
                catalogue.add_column(
                    name="modifier_values",
                    description=(
                        "The menu each slot in `modifiers` offers, in the same order, with the keyboard "
                        "shortcut stripped as BORIS strips it when recording. Empty for a free numeric "
                        "slot, which has no menu."
                    ),
                    index=2,
                )
            for behavior in self._project.behaviors.values():
                catalogue.add_row(
                    behavior=behavior.code,
                    definition=behavior.description,
                    behavior_type=behavior.behavior_type,
                    category=behavior.category,
                    **(
                        {
                            "modifiers": [slot.name.strip() for slot in behavior.modifier_slots],
                            "modifier_values": [
                                [strip_modifier_shortcut(value) for value in slot.values]
                                for slot in behavior.modifier_slots
                            ],
                        }
                        if declares_modifiers
                        else {}
                    ),
                )
            behavior_module.add(catalogue)
        elif list(catalogue["behavior"].data) != list(self._project.behaviors):
            # A second observation of the same project meets its own catalogue and reuses it. A second
            # project meets somebody else's, and extending it would make one catalogue claim to be the
            # scheme of two projects while its `exclusive` flag and its rows describe only the first.
            raise ValueError(
                f"The behavior processing module already holds an 'Ethogram' catalogue declaring "
                f"{list(catalogue['behavior'].data)}, and this project declares "
                f"{list(self._project.behaviors)}. A catalogue is one project's coding scheme, so two "
                "BORIS projects cannot share one NWB file. Write them to separate files."
            )

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

        # One bouts table for the observation, matching the events table. It carries the union of the
        # per-behavior columns, and a behavior writes an empty cell in a column it never asks.
        events_data_dict = self._get_events_data_dict()
        payload_fields = list(dict.fromkeys(field for data in events_data_dict.values() for field in data.payload))

        # An `_EventsData` holds one behavior's occurrences in the order they appear, so an occurrence's
        # row is its position among the occurrences sharing its code. Counted once here rather than
        # searched per bout, which would be quadratic and would also pick the wrong row where two
        # occurrences of one behavior share an onset.
        rows_by_occurrence = {}
        seen = {}
        for occurrence in self._observation.occurrences:
            rows_by_occurrence[id(occurrence)] = seen.get(occurrence.code, 0)
            seen[occurrence.code] = rows_by_occurrence[id(occurrence)] + 1

        bouts = EthogramBouts(
            name=f"{_to_object_name(name=self._observation.name)}Bouts",
            description=(
                f"State behavior bouts scored in BORIS observation '{self._observation.name}'. "
                "Point behaviors and bouts whose stop was never scored are in the events table."
            ),
            labeling_method="manual",
            source_software="BORIS",
            ethogram=catalogue,
        )
        for field in payload_fields:
            bouts.add_column(name=field, description=_column_description(field=field))

        offset = self.alignment.offset
        for occurrence in closed_bouts:
            payload = events_data_dict[occurrence.code].payload
            index = rows_by_occurrence[id(occurrence)]
            bouts.add_interval(
                start_time=occurrence.onset + offset,
                stop_time=occurrence.onset + occurrence.duration + offset,
                label=occurrence.code,
                **{field: (payload[field][index] if field in payload else "") for field in payload_fields},
            )
        behavior_module.add(bouts)

    def _modifier_column_names(self, code: str, occurrences: list) -> list[str]:
        """The events-table column each of a behavior's modifier slots writes into.

        Named after the slot rather than its position, because the position mixes unrelated questions:
        ``Walking``'s first slot is a speed and ``Standing``'s is a distance, and a column holding both
        can be given no coherent vocabulary. The slot name groups them the way somebody querying the
        table wants, so ``Speed`` asked of two behaviors is one column and asking for the fast ones works
        across both.

        A slot the scheme leaves unnamed falls back to its position, which the BORIS demo project needs
        since it names neither of its slots. So does a recorded answer beyond the declared slots, which
        happens where the scheme lost a slot after the session was scored.
        """
        behavior = self._project.behaviors.get(code)
        slots = behavior.modifier_slots if behavior is not None else []
        recorded = max((len(occurrence.modifier_values) for occurrence in occurrences), default=0)
        names = []
        for position in range(max(len(slots), recorded)):
            declared = slots[position].name.strip() if position < len(slots) else ""
            names.append(_to_modifier_column_name(slot_name=declared, position=position))
        return names

    def _column_spec(self, field: str, values: np.ndarray) -> dict:
        """The metadata for one events-table column.

        A modifier column declares its vocabulary, which is the slot's declared menu together with
        whatever was actually recorded, since a coder can score a value the menu no longer offers. That
        does two things. It says in the file what the column may hold, which is the honest description of
        a categorical column and where a ``MeaningsTable`` would come from once BORIS gives us prose per
        value. And it decides the fill: the writer fills a column a behavior does not declare with ``""``
        where the column is categorical and with ``NaN`` otherwise, and a float cannot share a column
        with text. Since a behavior declares only the slots it has, merging behaviors with different
        slots depends on that, which is what keeps the table layout a metadata choice rather than a
        fixed one.
        """
        spec = {"column_name": field, "description": _column_description(field=field)}
        if not field.removeprefix("stop_").startswith("modifier_"):
            return spec
        vocabulary = {""} | {str(value) for value in values}
        for behavior in self._project.behaviors.values():
            for position, slot in enumerate(behavior.modifier_slots):
                if _to_modifier_column_name(slot_name=slot.name.strip(), position=position) == field.removeprefix(
                    "stop_"
                ):
                    vocabulary.update(strip_modifier_shortcut(value) for value in slot.values)
        # Identity labels: BORIS records the value the coder chose, so there is nothing to relabel, and
        # the map is here to declare the vocabulary. Meanings stay empty because BORIS describes a slot
        # and never its values, and the writer skips the MeaningsTable when nothing is described.
        spec["column_categories"] = {"labels": {value: value for value in sorted(vocabulary)}, "meanings": {}}
        return spec

    def _table_metadata_key(self) -> str:
        """The routing key every one of this observation's behaviors shares, so they land in one table."""
        return f"{self.metadata_key}_{self._observation.name}"

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


def _modifier_answer(occurrence, position: int | None, field: str = "modifier_values") -> str:
    """The answer an occurrence recorded in one modifier column, empty where it has none.

    ``None`` means the behavior declares no slot writing into that column, and an index past the recorded
    answers means the row carried fewer fields than the scheme declares. Both read as unanswered.
    """
    answers = getattr(occurrence, field)
    if position is None or position >= len(answers):
        return ""
    return answers[position]


def _to_modifier_column_name(slot_name: str, position: int) -> str:
    """Turn a modifier slot into an events-table column name.

    A slot name is free text somebody typed into an ethogram, so it carries their punctuation and case
    (``set #1``, ``test 2 ``) and has to be normalized before it can be a column. The ``modifier_`` prefix
    keeps a slot called ``comment`` or ``subject`` from landing on top of a column that already means
    something else.
    """
    words = [word for word in re.split(r"[\W_]+", slot_name, flags=re.UNICODE) if word]
    return f"modifier_{'_'.join(words).lower()}" if words else f"modifier_{position + 1}"


def _column_description(field: str) -> str:
    """The description of an events-table column, which several behaviors may write into.

    Derived from the column name rather than from the behavior or the slot's declared spelling, because
    the writer requires every contributor to a shared column to describe it identically, and two
    behaviors reaching one column by different spellings of a slot name would otherwise disagree.
    """
    fixed = {
        "subject": "The subject the event was scored on.",
        "comment": "The coder's comment, from the row that opened the occurrence.",
        "stop_comment": "The coder's comment on the row that closed a state bout.",
    }
    if field in fixed:
        return fixed[field]
    closing = field.startswith("stop_")
    slot = field.removeprefix("stop_").removeprefix("modifier_")
    when = "on the row that closed a state bout" if closing else "when the behavior was scored"
    return (
        f"The '{slot}' modifier answered {when}. The Ethogram's `modifier_slots` column says which slot "
        "this is for each behavior, and `modifier_slot_values` what it could hold."
    )


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

    BORIS observation names and behavior codes are free text and routinely carry spaces and punctuation
    (``observation #2``, ``live not paired``), none of which belongs in an object name, so the words are
    taken and capitalized. A name that is only digits is common enough (an observation called ``1``) and
    would give an object named ``1``, so it is prefixed rather than left to stand alone.

    The split is on non-word characters rather than on non-ASCII ones, because NWB rejects only ``/`` and
    ``:`` in a name and accents survive a round trip intact. An ethogram is written in the language its
    author speaks, so ``Exploración`` has to stay ``Exploración`` rather than become ``ExploraciN``.
    """
    words = [word for word in re.split(r"[\W_]+", name, flags=re.UNICODE) if word]
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
