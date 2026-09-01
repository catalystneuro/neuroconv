import re
from datetime import datetime

import numpy as np
from hdmf.common import MeaningsTable
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from neuroconv.utils import DeepDict

from ._boris_reader import (
    _get_observation_names,
    _read_boris_observation,
    _read_boris_project,
    _strip_modifier_shortcut,
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
    has no extent; a state behavior occupies two, a start and a stop, which this interface pairs on
    subject plus code in order of appearance and writes as one row carrying the bout's length. Pairing
    ignores the modifier string, since a bout can open with one modifier and close with another. A bout
    that opens and never closes keeps a ``NaN`` duration, which happens whenever a coder misses a stop in
    a live session and cannot be repaired afterwards.

    Every behavior shares one ``duration`` column, so a ``NaN`` in it reads two ways: a point behavior,
    which has no extent to record, and a state bout nobody closed. The catalogue's ``behavior_type`` is
    what tells them apart.

    All of an observation's behaviors are written into one table by default. A behavior may declare
    modifier slots, the qualifiers a coder answers whenever they score it (``Walking`` asking for a speed
    and a direction), and each slot becomes a column named after it rather than surviving as the
    ``|``-joined string BORIS records; a behavior that declares no such slot writes an empty cell there.
    The column is named after the behavior and the slot, so two behaviors declaring a slot of the same
    name get a column each and every column holds one vocabulary; a slot the scheme leaves unnamed falls
    back to its position. Which columns a behavior writes into is on the catalogue, in ``modifiers``,
    along with the menu each offers in ``modifier_values``.

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
        return _get_observation_names(file_path=file_path)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        observation_name: str,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the BORISInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.boris`` JSON document.
        observation_name : str
            The observation to read, as :meth:`get_observation_names` lists them.
        metadata_key : str, optional
            The key this interface's block sits under in ``metadata["Events"]``. Defaults to the
            observation's own name, ``boris_live_not_paired`` for an observation called
            ``live not paired``, since a project holds many observations and a conversion running
            several of them would otherwise write them all under one key.
        verbose : bool, default: False
            Whether to print progress.
        """
        super().__init__(file_path=file_path, observation_name=observation_name, verbose=verbose)
        # A project holds many observations and each is its own interface, so the key is derived from
        # the observation rather than fixed: a conversion running several of them would otherwise write
        # every block under the same handle. Observation names are free text, so the words are joined.
        observation_words = [word for word in re.split(r"[\W_]+", observation_name, flags=re.UNICODE) if word]
        self.metadata_key = metadata_key or "_".join(["boris", *(word.lower() for word in observation_words)])
        self._project = _read_boris_project(file_path=file_path)
        self._observation = _read_boris_observation(file_path=file_path, observation_name=observation_name)
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

        # BORIS writes the date ISO-formatted with either separator, `2016-12-10T15:44:57` and
        # `2018-05-14 16:22:23` both occurring, and states no timezone, so the datetime is left naive
        # and pynwb attaches the local one at write.
        if self._observation.date:
            try:
                metadata["NWBFile"]["session_start_time"] = datetime.fromisoformat(self._observation.date)
            except ValueError:
                pass
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
        metadata["Events"]["EventTables"][self.metadata_key] = {
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
                # A behavior code is free text and BORIS accepts characters an NWB object name cannot
                # hold, `Grooming/Eating` being an ordinary way to name one behavior covering two
                # things. The code itself is untouched, staying the identifier and reaching the
                # catalogue's `behavior` column verbatim; only the display name is made safe, because
                # routing a behavior to a table of its own derives that table's name from it. The
                # separator is kept rather than dropped, since `Foraging_Caching` still reads as two
                # words where `ForagingCaching` reads as one invented one.
                "event_name": code.replace("/", "_").replace(":", "_"),
                "table_metadata_key": self.metadata_key,
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
        self._check_table_name_is_free(nwbfile=nwbfile, metadata=metadata)
        self._check_columns_are_not_shared_by_two_behaviors(metadata=metadata)
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        self._add_ethogram_to_nwbfile(nwbfile=nwbfile)

    def _check_table_name_is_free(self, nwbfile: NWBFile, metadata: dict) -> None:
        """Refuse to write into an events table another observation already owns.

        An observation name is free text and the object name derived from it drops the punctuation, so
        `Boccia 223 2` and `Boccia 223_2`, two trials a real study recorded an hour apart against
        different videos, both come out as `Boccia2232`. The events writer is deliberately
        append-capable, which is right for several interfaces sharing one table on purpose and wrong
        here: the second observation's rows would join the first's with nothing to say which trial they
        came from.

        Only the events table needs this. The bouts table goes through `ProcessingModule.add`, which
        rejects a duplicate name already.
        """
        declared = metadata["Events"]["EventTables"].get(self.metadata_key)
        if declared is None:
            # The user re-routed the behaviors and named the tables themselves, so the name this
            # interface would have chosen is not in play.
            return
        table_name = declared["table_name"]
        existing = nwbfile.events.get(table_name) if nwbfile.events is not None else None
        if existing is None or f"observation '{self._observation.name}'" in existing.description:
            return
        raise ValueError(
            f"An events table named '{table_name}' already exists and holds a different observation: "
            f"{existing.description} Two observation names that differ only in punctuation derive the "
            f"same object name, and '{self._observation.name}' is one of them. Give this one a name of "
            f"its own with metadata['Events']['EventTables']['{self.metadata_key}']['table_name'], or "
            "write the two observations to separate files."
        )

    def _check_columns_are_not_shared_by_two_behaviors(self, metadata: dict) -> None:
        """Refuse to merge two behaviors' modifier answers into one column.

        A column is keyed on the behavior as well as the slot so that two behaviors asking a same-named
        question get a column each. Both halves are normalized and joined with underscores, so two
        different splits can still flatten to one name: behavior `Traffic` with slot `lights state` and
        behavior `Traffic lights` with slot `State` both give `modifier_traffic_lights_state`. Nothing
        downstream would notice, since the two agree on the description and on the vocabulary, so the
        writer would accept them and their answers would merge into one column holding two vocabularies.

        Checked here rather than at read, and against the resolved metadata rather than the names this
        interface derived, for two reasons. `get_metadata` still returns, so the dict naming the column is
        reachable, which is the whole recourse; and what is checked is what the user actually asked for,
        so a rename fixes it and a rename that collides afresh is caught too. `subject`, `comment` and
        `stop_comment` are exempt because every behavior declares them and sharing them is the point.
        """
        shared_by_design = ("subject", "comment", "stop_comment")
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        owner_of_column = {}
        for code, entry in event_types.items():
            table_metadata_key = entry.get("table_metadata_key", code)
            for field, column_spec in entry.get("columns", {}).items():
                if field in shared_by_design:
                    continue
                column_name = column_spec.get("column_name", field)
                # Two behaviors in different tables may share a name; only one table is one column.
                previous_owner = owner_of_column.setdefault((table_metadata_key, column_name), code)
                if previous_owner == code:
                    continue
                raise ValueError(
                    f"Behaviors '{previous_owner}' and '{code}' both write the column '{column_name}' "
                    f"into one events table, so their answers would merge into one column holding two "
                    "vocabularies. A column is named for the behavior and the slot together, and these "
                    "two flatten to the same name. Give one of them a column of its own before writing:\n"
                    f"    metadata['Events']['{self.metadata_key}']['event_types']['{code}']"
                    f"['columns']['{field}']['column_name'] = '{column_name}_2'\n"
                    "Or rename the slot on either behavior in BORIS and re-save."
                )

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
        # The slots are worked out per behavior, and the column name carries the behavior, so two
        # behaviors sharing one table still get a column each.
        modifier_columns = {
            code: self._modifier_column_names(code=code, occurrences=occurrences)
            for code, occurrences in occurrences_by_code.items()
        }
        events_data_dict = {}
        for code, occurrences in occurrences_by_code.items():
            behavior = self._project.behaviors.get(code)
            is_point = behavior is None or behavior.behavior_type == "point"

            onsets = np.array([occurrence.onset for occurrence in occurrences], dtype=float)
            # A point behavior has no extent at all, which is `None`; a state behavior always has the
            # column, carrying `NaN` for a bout whose stop was never scored.
            durations = None
            if not is_point:
                durations = np.array([occurrence.duration for occurrence in occurrences], dtype=float)

            payload = {
                "subject": np.array([occurrence.subject for occurrence in occurrences], dtype=object),
                "comment": np.array([occurrence.comment for occurrence in occurrences], dtype=object),
            }

            # A modifier is the values ticked in one declared slot, so it gets one ragged column per
            # slot rather than the `|`- and `,`-joined string BORIS records. Which slot each column is
            # stays on the catalogue, since it is a property of the behavior and not of any occurrence.
            #
            # A slot nobody ticked in this observation writes no column: every cell would be an empty
            # list, which gives hdmf no dtype to infer and fails at write. The catalogue still records
            # that the behavior declares the slot, so nothing about the scheme is lost.
            for position, column_name in enumerate(modifier_columns[code]):
                column = _modifier_column(occurrences=occurrences, position=position)
                if any(len(cell) for cell in column):
                    payload[column_name] = column

            # A bout closes on its own comment and modifier row, and BORIS carries the opening answers
            # forward, so the closing ones earn a column only where this observation has a bout that
            # changed mid-way. They are split the same way, so `None` reads as unanswered here too.
            if closing_comment:
                stop_comments = [occurrence.stop_comment for occurrence in occurrences]
                payload["stop_comment"] = np.array(stop_comments, dtype=object)
            if closing_modifiers:
                for position, column_name in enumerate(modifier_columns[code]):
                    column = _modifier_column(occurrences=occurrences, position=position, field="stop_modifier_values")
                    if any(len(cell) for cell in column):
                        payload[f"stop_{column_name}"] = column

            events_data_dict[code] = _EventsData(
                event_type_source_id=code, timestamps=onsets, durations=durations, payload=payload
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
                # boolean cannot carry that, and asserting True would overclaim, so the flag stays False
                # and the per-behavior sets go into the `excludes` column below.
                exclusive=False,
            )
            # BORIS states exclusion per behavior, as the codes that starting one terminates, so it is
            # per-behavior data and belongs in a column beside `category` rather than in the table-level
            # `exclusive` flag, which asks a different question: whether the whole scheme is a single
            # label partition. Written only where some behavior excludes something, for the same dtype
            # reason as the modifier columns below.
            declares_exclusions = any(behavior.excluded for behavior in self._project.behaviors.values())
            if declares_exclusions:
                catalogue.add_column(
                    name="excludes",
                    description=(
                        "The behaviors that starting this one terminates, as BORIS's exclusion matrix "
                        "states them. Per behavior and partial, so a scheme can make four behaviors "
                        "mutually exclusive and leave the rest free, and enforced per subject, so a "
                        "multi-subject observation has overlapping bouts however complete the matrix "
                        "is. Empty where the behavior excludes nothing."
                    ),
                    index=True,
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
                    **({"excludes": behavior.excluded} if declares_exclusions else {}),
                    **(
                        {
                            "modifiers": [slot.name.strip() for slot in behavior.modifier_slots],
                            "modifier_values": [
                                [_strip_modifier_shortcut(value) for value in slot.values]
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
        # A modifier field holds the values ticked in one slot, so its column is ragged here too: the
        # interval view describes a bout the same way the events table does.
        ragged_fields = {
            field
            for data in events_data_dict.values()
            for field, values in data.payload.items()
            if any(isinstance(value, list) for value in values)
        }
        # A ragged column no bout fills is dropped rather than written empty: its values dataset would
        # carry nothing for hdmf to infer a dtype from, and it fails at write. That happens whenever a
        # behavior with modifier slots is a point behavior, since only closed bouts reach this table.
        filled_ragged_fields = {
            field
            for field in ragged_fields
            if any(
                len(events_data_dict[occurrence.code].payload[field][rows_by_occurrence[id(occurrence)]])
                for occurrence in closed_bouts
                if field in events_data_dict[occurrence.code].payload
            )
        }
        payload_fields = [field for field in payload_fields if field not in ragged_fields - filled_ragged_fields]
        for field in payload_fields:
            bouts.add_column(
                name=field,
                description=_column_description(field=field),
                **({"index": True} if field in filled_ragged_fields else {}),
            )

        offset = self.alignment.offset
        for occurrence in closed_bouts:
            payload = events_data_dict[occurrence.code].payload
            index = rows_by_occurrence[id(occurrence)]
            # A behavior writes an empty cell in a column it does not own, since the bouts table keeps
            # the union of the per-behavior columns.
            cells = {
                field: (payload[field][index] if field in payload else ([] if field in ragged_fields else ""))
                for field in payload_fields
            }
            bouts.add_interval(
                start_time=occurrence.onset + offset,
                stop_time=occurrence.onset + occurrence.duration + offset,
                label=occurrence.code,
                **cells,
            )

        # `label` holds the behavior code, the same vocabulary the events table's `event_type` carries, so
        # it earns the same MeaningsTable. The two coincide by construction, both being built from the
        # ethogram's `description`, and the repetition is what the schema asks for: a MeaningsTable targets
        # a column of the table it sits in, so one object cannot serve both. Only a state behavior can be a
        # bout, so this lists the state subset of what `event_type` lists. As there, a behavior the scheme
        # left undescribed earns no row, and a scheme that describes nothing gets no table at all rather
        # than one restating each code back at the reader.
        described_state_behaviors = [
            behavior
            for behavior in self._project.behaviors.values()
            if behavior.behavior_type == "state" and behavior.description
        ]
        if described_state_behaviors:
            meanings_table = MeaningsTable(target=bouts["label"], description="Meaning of each behavior.")
            for behavior in described_state_behaviors:
                meanings_table.add_row(value=behavior.code, meaning=behavior.description)
            bouts.add_meanings_table(meanings_table)

        # `subject` is categorical here too and BORIS describes a subject, so it earns its meanings on
        # both tables for the same reason `label` does. Built through `_column_spec`, the same call the
        # events table's column goes through, so the two cannot drift apart.
        if "subject" in bouts.colnames:
            categories = self._column_spec(field="subject", values=np.asarray(bouts["subject"].data, dtype=object))[
                "column_categories"
            ]
            meanings_table = MeaningsTable(target=bouts["subject"], description="Meaning of each subject.")
            for name, meaning in categories["meanings"].items():
                meanings_table.add_row(value=categories["labels"][name], meaning=meaning)
            bouts.add_meanings_table(meanings_table)

        behavior_module.add(bouts)

    def _modifier_column_names(self, code: str, occurrences: list) -> list[str]:
        """The events-table column each of a behavior's modifier slots writes into.

        Named after the behavior and the slot rather than after the slot's position, because the position
        mixes unrelated questions: ``Walking``'s first slot is a speed and ``Standing``'s is a distance,
        and a column holding both can be given no coherent vocabulary. Why the behavior is in the name as
        well as the slot is in :func:`_to_modifier_column_name`.

        A slot the scheme leaves unnamed falls back to its position, which the BORIS demo project needs
        since it names neither of its slots. So does a recorded answer beyond the declared slots, which
        happens where the scheme lost a slot after the session was scored.
        """
        behavior = self._project.behaviors.get(code)
        declared_slots = behavior.modifier_slots if behavior is not None else []
        # A row can carry more answers than the scheme declares, where a slot was removed after the
        # session was scored, and those still need a column each.
        answers_recorded = max((len(occurrence.modifier_values) for occurrence in occurrences), default=0)
        number_of_columns = max(len(declared_slots), answers_recorded)

        names = []
        for position in range(number_of_columns):
            is_declared = position < len(declared_slots)
            slot_name = declared_slots[position].name.strip() if is_declared else ""
            names.append(_to_modifier_column_name(code=code, slot_name=slot_name, position=position))
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
        opening_column = field.removeprefix("stop_")
        is_modifier_column = opening_column.startswith("modifier_")

        if field == "subject":
            # The project's declared roster, not only the animals this observation happened to score, so
            # the file records who could have been attributed an event. The empty string is one of them:
            # BORIS writes an event attributed to nobody as either the empty string or the literal
            # `No focal subject`, and the reader reads both as nobody.
            roster = {""} | set(self._project.subject_names) | {str(value) for value in values}
            # A subject carries a free-text description in `subjects_conf` exactly as a behavior does in
            # `behaviors_conf`, so the column earns real meanings rather than the empty ones a source that
            # only names its categories would give. Nobody is described here rather than in the project,
            # since the empty label is the one value in the column a reader cannot guess: an unattributed
            # event is a coding decision and not a gap in the record.
            meanings = {
                name: description
                for name, description in self._project.subject_descriptions.items()
                if description and name in roster
            }
            meanings[""] = (
                "The event was scored against no subject. BORIS writes this as an empty subject or as the "
                "literal 'No focal subject', which are the same thing and never a declared name."
            )
            spec["column_categories"] = {"labels": {name: name for name in sorted(roster)}, "meanings": meanings}
            return spec

        if not is_modifier_column:
            return spec

        # The vocabulary is what was recorded plus what the slot's menu offers. A cell is a list of the
        # values ticked in that slot, so the vocabulary is drawn from inside the cells; a cell with
        # nothing ticked contributes nothing, since an empty list holds no value to declare.
        vocabulary = {str(value) for cell in values for value in cell}
        for behavior in self._project.behaviors.values():
            for position, slot in enumerate(behavior.modifier_slots):
                column = _to_modifier_column_name(code=behavior.code, slot_name=slot.name.strip(), position=position)
                writes_into_this_column = column == opening_column
                if writes_into_this_column:
                    vocabulary.update(_strip_modifier_shortcut(value) for value in slot.values)
        # Identity labels: BORIS records the value the coder chose, so there is nothing to relabel, and
        # the map is here to declare the vocabulary. Meanings stay empty because BORIS describes a slot
        # and never its values, and the writer skips the MeaningsTable when nothing is described.
        spec["column_categories"] = {"labels": {value: value for value in sorted(vocabulary)}, "meanings": {}}
        return spec

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


def _modifier_column(occurrences: list, position: int, field: str = "modifier_values") -> np.ndarray:
    """The answers one modifier slot received, as a ragged events-table column.

    Each cell is the list of values ticked in that slot, so the array is filled element by element:
    ``np.array`` on a list of lists gives a 2D array where they happen to share a length and refuses
    outright where they do not.
    """
    column = np.empty(len(occurrences), dtype=object)
    for index, occurrence in enumerate(occurrences):
        column[index] = _modifier_answer(occurrence=occurrence, position=position, field=field)
    return column


def _modifier_answer(occurrence, position: int | None, field: str = "modifier_values") -> list[str]:
    """The values an occurrence ticked in one modifier slot, empty where it ticked none.

    A list rather than one value, because a multiple-selection slot takes several at once and the cell
    then carries them as a ragged column rather than as a string somebody has to split. ``None`` means the
    behavior declares no slot writing into that column, and an index past the recorded answers means the
    row carried fewer fields than the scheme declares. Both read as unanswered.
    """
    answers = getattr(occurrence, field)
    if position is None or position >= len(answers):
        return []
    return answers[position]


def _to_modifier_column_name(code: str, slot_name: str, position: int) -> str:
    """Turn one behavior's modifier slot into an events-table column name.

    Keyed on the behavior as well as the slot, so two behaviors declaring a slot of the same name get a
    column each. A slot name is free text somebody typed into an ethogram editor, so two identical
    strings are not two askings of the same question: the pedestrian scheme asks ``Direction`` of
    ``Walking`` meaning road or elsewhere and of ``Looking`` meaning front or side. Sharing a column
    between them would give it two vocabularies at once and no cell in it could be read without also
    reading ``event_type``. BORIS itself keys its analysis dataframe on the behavior and the modifier set
    rather than on the slot name for the same reason.

    The price is that a slot two behaviors genuinely do share, ``Speed`` on ``Walking`` and ``Crossing``,
    splits as well, so a filter across both reads the columns from the catalogue's ``modifiers``. That is
    the cheaper loss, and the column count barely moves: over the whole harvested corpus this takes the
    mean from 0.18 modifier columns per observation to 0.35 and the worst case from three to five.

    Both names are normalized, since a behavior code and a slot name alike carry whatever punctuation and
    case somebody typed (``2 sets``, ``set #1``, ``test 2 ``). The ``modifier_`` prefix keeps a slot
    called ``comment`` or ``subject`` from landing on a column that already means something else.
    """

    def words(text: str) -> list[str]:
        return [word for word in re.split(r"[\W_]+", text, flags=re.UNICODE) if word]

    slot = "_".join(words(slot_name)).lower() if words(slot_name) else str(position + 1)
    return "_".join(["modifier", *(word.lower() for word in words(code)), slot])


def _column_description(field: str) -> str:
    """The description of an events-table column.

    ``subject``, ``comment`` and ``stop_comment`` are shared: every behavior declares them, and the
    writer requires every contributor to a shared column to describe it identically, which is why they
    are fixed strings here rather than built per behavior. A modifier column belongs to one behavior, so
    its description could name that behavior, but it is derived from the column name for consistency
    with the three above and because the column name already carries the behavior.
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
        f"The '{slot}' modifier answered {when}. The Ethogram's `modifiers` column says which slot this "
        "is for each behavior, and `modifier_values` what it could hold."
    )


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
