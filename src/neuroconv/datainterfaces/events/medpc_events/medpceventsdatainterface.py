from datetime import datetime
from typing import Literal

import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from neuroconv.utils import DeepDict

from ..baseeventsinterface import BaseEventsInterface, _EventsData

# The reader is shared with the deprecated MedPCInterface, which still owns it; it moves into this package
# when that interface is removed.
from ...behavior.medpc.medpc_helpers import read_medpc_file

# MED-PC IV writes the same fixed header above every session, so a session always begins at its `Start Date` line
# and the reader needs no configuration to find it.
_SESSION_START_FIELD = "Start Date"

# MedPC's own array terminator, documented in Med Associates' shipped programs as "the code value -987.987 can be
# used to seal or terminate an array at the last valid element", and written automatically by a `Sealed_Array`
# declaration. It is a marker, not an event.
_ARRAY_SEAL = -987.987

# What one stored value is worth in seconds. MedPC stores whatever the MSN program divided by before writing,
# and the file records neither that choice nor the box's timing resolution, so it is stated rather than detected.
# A raw `BTIME` tick has no name here because its worth is the installed resolution: 0.002 on a 2 ms system.
_TIME_UNIT_TO_SECONDS = {
    "decaseconds": 10.0,
    "seconds": 1.0,
    "deciseconds": 0.1,
    "centiseconds": 0.01,
    "milliseconds": 0.001,
}
TimeUnit = Literal["decaseconds", "seconds", "deciseconds", "centiseconds", "milliseconds"]


class _MedPCEventsInterface(BaseEventsInterface):
    """
    Data Interface for the discrete events of a MedPC output file.

    The output files from MedPC are raw text files that contain behavioral data from the operant box sessions such as
    lever presses, reward port entries, nose pokes, etc. The output text files format this data into a series of
    colon-separated variables that are either single-line (for metadata) or multi-line (for arrays). The multi-line
    variables keep a colon-separated index of the array every 5 elements. For example, a single variable might look
    like::

        Start Date: 11/09/18

    while a multi-line variable might look like::

        A:
            0:      175.150      270.750      762.050      762.900     1042.600
            5:     1567.800     1774.950     2448.450     2454.050     2552.800
            10:     2620.550     2726.250

    A file holds several sessions, one per run of the program, separated from each other by a blank line. Every one
    of them opens with the same header, which MED-PC IV writes rather than the MSN program, so its fields are the
    same in every file::

        Start Date: 04/10/19
        End Date: 04/10/19
        Subject: 95.259
        Experiment: FR1
        Group: 1
        Box: 1
        Start Time: 12:36:13
        End Time: 13:38:19
        MSN: FOOD_FR1 TTL Left

    The session to read is picked out by ``session_header``, which states the values of as many of those fields as
    it takes to name one session in the file.


    Each event type is written as a ``pynwb.event.EventsTable`` into ``nwbfile.events``. Which arrays hold events,
    and how, is what the two concrete interfaces differ in; everything above is common to both.
    """

    keywords = ("events", "behavior", "MedPC")
    associated_suffixes = (".txt",)

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for this interface.

        Five header lines of the selected session are reported: ``Start Date`` and ``Start Time`` as
        ``NWBFile/session_start_time``, ``Subject`` as ``Subject/subject_id``, ``MSN`` as ``NWBFile/protocol``,
        since the MED State Notation program is the protocol the session ran and is what gives every array its
        meaning, and ``Experiment`` as ``NWBFile/experiment_description``. The last two are often left blank at
        the box and are reported only where the line carries something.

        The date is taken as month/day/year, which is what MedPC IV writes on a machine set to that short date
        format and what every file seen so far uses. A day-first date is only recognized where the first field is
        above twelve, so a box set to that format needs the time supplied through editable metadata instead. The
        header states no timezone, so the datetime is left naive and pynwb attaches the local one at write.

        ``Box`` and ``Group`` are not reported, as neither has a field in the NWB schema, nor are the file's
        non-event arrays (counters, trial schedules, session parameters). Reach them with
        :func:`~neuroconv.datainterfaces.behavior.medpc.medpc_helpers.get_medpc_variables`.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()

        header_names = ("Start Date", "Start Time", "Subject", "MSN", "Experiment")
        header_dict = self._read_session(
            medpc_name_to_info_dict={name: {"name": name, "is_array": False} for name in header_names}
        )
        session_start_time = _parse_session_start_time(
            start_date=header_dict.get("Start Date"), start_time=header_dict.get("Start Time")
        )
        if session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = session_start_time
        if header_dict.get("Subject"):
            metadata["Subject"]["subject_id"] = header_dict["Subject"]
        if header_dict.get("MSN"):
            metadata["NWBFile"]["protocol"] = header_dict["MSN"]
        if header_dict.get("Experiment"):
            metadata["NWBFile"]["experiment_description"] = header_dict["Experiment"]

        # Declare one entry per event type, seeding each editable event_name from the name the user gave the array
        # or its code's legend entry, plus one column per value array the type carries.
        # A MedPC file carries no prose of its own, so no description is reported here and a value column's codes
        # are left unlabelled: what an array or a code records lives in the MSN program and in the experimenter's
        # head, and is the user's to add.
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        for event_type_source_id in self._get_events_data_dict():
            entry = {"event_name": event_type_source_id}
            payload_variables = self._payload_variables(event_type_source_id=event_type_source_id)
            if payload_variables:
                entry["columns"] = {medpc_name: {"column_name": medpc_name} for medpc_name in payload_variables}
            event_types[event_type_source_id] = entry
        return metadata

    def set_aligned_timestamps(self, aligned_timestamps_dict: dict[str, np.ndarray]) -> None:
        """Replace the timestamps of one or more event types with externally aligned ones.

        The interface's own alignment is a rigid offset (``alignment.shift_times``), which is what a session
        recorded on one clock needs. This is for the other case: times recovered from another device, such as the
        TTL pulses a photometry rig recorded for each MedPC event, which are not the source's times shifted but
        different times altogether. The substituted values are what the writer writes and what
        ``get_event_times`` reports, with ``alignment.offset`` still applied on top.

        Parameters
        ----------
        aligned_timestamps_dict : dict of str to numpy.ndarray
            The aligned onset times, in seconds, keyed by event type identifier: the MedPC variable name for a
            array-per-type file, or the code's zero-padded digits for a coded one, as
            ``get_event_type_source_ids`` lists them. An event type left out keeps the times read from the file.

        Raises
        ------
        KeyError
            If an identifier names no event type this interface reads.
        ValueError
            If an array does not hold one timestamp per event of its type.
        """
        events_data_dict = self._get_events_data_dict()
        for event_type_source_id, aligned_timestamps in aligned_timestamps_dict.items():
            if event_type_source_id not in events_data_dict:
                raise KeyError(
                    f"No event type '{event_type_source_id}' in {type(self).__name__}. This interface reads "
                    f"{sorted(events_data_dict)}, which get_event_type_source_ids lists."
                )
            event = events_data_dict[event_type_source_id]
            aligned_timestamps = np.asarray(aligned_timestamps)
            if aligned_timestamps.ndim != 1:
                raise ValueError(
                    f"The aligned timestamps for '{event_type_source_id}' have shape {aligned_timestamps.shape}, "
                    "but an event type's onsets are one time per event, so a one-dimensional array is expected."
                )
            if len(aligned_timestamps) != len(event.timestamps):
                raise ValueError(
                    f"The event type '{event_type_source_id}' has {len(event.timestamps)} events but "
                    f"{len(aligned_timestamps)} aligned timestamps were given for it."
                )
            event.timestamps = aligned_timestamps

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None) -> None:
        """Write the events as ``pynwb.event.EventsTable`` objects inside ``nwbfile.events``.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the events to.
        metadata : dict, optional
            Metadata dictionary; see :meth:`get_metadata_schema`. If None, ``get_metadata()`` is used.
        """
        if metadata is not None and "MedPC" in metadata:
            raise ValueError(
                "metadata['MedPC'] is not read by this interface, which would leave the events it describes "
                "unwritten. It takes its editable metadata from "
                f"metadata['Events']['{self.metadata_key}']['event_types'], one entry per event type keyed by the "
                "MedPC variable name or by the event code, and which arrays hold events "
                "is declared on the interface rather than in the metadata. The deprecated MedPCInterface is what "
                "reads metadata['MedPC']."
            )
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation from the MedPC file, cached after the first call."""
        if self._events_data_dict is None:
            self._events_data_dict = self._read_events()
        return self._events_data_dict

    def _read_events(self) -> dict[str, _EventsData]:
        """Read the selected session's events. Implemented by each layout's interface."""
        raise NotImplementedError

    def _payload_variables(self, event_type_source_id: str) -> list[str]:
        """Return the arrays one event type carries as value columns."""
        return []

    def _validate_within_the_session(self, times: np.ndarray, medpc_name: str) -> None:
        """Raise where a decoded time falls after the session's own recorded end.

        The header states `Start Time` and `End Time`, so the session has a length the file itself asserts and no
        event can fall outside it. This is the only bound a MedPC file offers on the magnitude of a time, which
        makes it the one check the ordering check cannot do: accumulating intervals always yields a rising series,
        so `relative_mode=True` satisfies the ordering check whether or not the program used Relative Mode, and
        only the length catches the difference.

        It is one-sided. Times that come out too large run past the session end and are caught; times that come
        out too small sit inside it and climb correctly, so a unit smaller than the truth passes both checks
        silently. Nothing in a MedPC file bounds a time from below.
        """
        if len(times) == 0:
            return
        duration = self._session_duration_in_seconds()
        if duration is None:
            return
        latest = float(np.max(times))
        # Whole seconds only in the header, and a box is opened and closed around the program, so the bound is
        # generous: only a time well past the end is evidence of anything.
        if latest <= duration * 1.05 + 1:
            return
        raise ValueError(
            f"The last event read from the MedPC variable '{medpc_name}' is at {latest:.6g} s, but the header "
            f"says the session ran {duration:.6g} s, from '{self._header_field('Start Time')}' to "
            f"'{self._header_field('End Time')}'. No event can happen after the session ended, so the values "
            "are coming out larger than the program wrote them. Check the MSN program that wrote the file: "
            "`time_unit` against what it divided by before storing, which for a program that stored the raw "
            "BTIME counter is the resolution MED-PC was installed at (0.002 on a 2 ms system, 0.005 on a 5 ms "
            "one), and, where `relative_mode` is on, that it really wrote intervals, since accumulating times "
            "that were already elapsed inflates them exactly this way. If the program shows the file is already being read as it "
            "was written, this is a layout NeuroConv does not support yet: please open an issue at "
            "https://github.com/catalystneuro/neuroconv/issues with the program and a sample file."
        )

    def _header_field(self, name: str) -> str | None:
        """Return one header line of the selected session, reading the header once and keeping it."""
        if getattr(self, "_header_dict", None) is None:
            names = ("Start Date", "Start Time", "End Time", "Subject", "MSN", "Experiment")
            self._header_dict = self._read_session(
                medpc_name_to_info_dict={field: {"name": field, "is_array": False} for field in names}
            )
        return self._header_dict.get(name)

    def _session_duration_in_seconds(self) -> float | None:
        """Return how long the header says the session ran, or None where it does not say."""
        start = _parse_clock_time(self._header_field("Start Time"))
        end = _parse_clock_time(self._header_field("End Time"))
        if start is None or end is None:
            return None
        seconds = end - start
        # A session running past midnight wraps the clock; the header carries no second date to resolve it.
        return seconds + 24 * 3600 if seconds < 0 else seconds

    def _read_session(self, medpc_name_to_info_dict: dict) -> dict:
        """Read the selected session's variables out of the MedPC file."""
        return read_medpc_file(
            file_path=self.source_data["file_path"],
            medpc_name_to_info_dict=medpc_name_to_info_dict,
            session_conditions=self.source_data["session_header"],
            start_variable=_SESSION_START_FIELD,
        )

    def _get_variable_array(self, session_dict: dict, medpc_name: str) -> np.ndarray:
        """Return one array variable of the read session, naming it if the session does not hold it."""
        if medpc_name not in session_dict:
            raise ValueError(
                f"The MedPC variable '{medpc_name}' is not in the session selected by "
                f"{self.source_data['session_header']} of {self.source_data['file_path']}."
            )
        values = np.asarray(session_dict[medpc_name], dtype=float)
        # A sealed array carries `-987.987` after its last real element. The seal marks the end, so everything
        # from it on is padding rather than data, which is what a `Sealed_Array` declaration writes.
        sealed = np.flatnonzero(values == _ARRAY_SEAL)
        return values[: sealed[0]] if len(sealed) else values

    def _decode_times(self, values: np.ndarray, medpc_name: str, check_order: bool = True) -> np.ndarray:
        """Turn one array's raw values into onset times in seconds.

        MedPC writes whatever the MSN program computed, so a value is a time only after the unit is applied and,
        for a program written in relative mode, after the deltas are accumulated. Neither the unit nor the mode is
        recorded in the file, which is why both are stated on the interface.
        """
        if self.source_data["relative_mode"]:
            # In Med Associates' Relative Mode each element is the time since the previous event, so the series is
            # a set of intervals and only their running total is a time. NWB records a time as the offset from the
            # session's start, so the accumulation is what makes the values times at all.
            values = np.cumsum(values)
        seconds = self._scale_to_seconds(values)
        self._validate_within_the_session(times=seconds, medpc_name=medpc_name)
        if check_order:
            self._validate_non_decreasing(times=seconds, medpc_name=medpc_name)
        return seconds

    def _scale_to_seconds(self, values: np.ndarray, time_unit=None) -> np.ndarray:
        """Apply the stated unit to raw values, without accumulating or checking their order."""
        time_unit = time_unit if time_unit is not None else self._single_time_unit()
        scale = time_unit if isinstance(time_unit, (int, float)) else _TIME_UNIT_TO_SECONDS[time_unit]
        return values * scale

    def _single_time_unit(self) -> str:
        """Return the one unit that applies to every value, refusing a per-type mapping where none can."""
        time_unit = self.source_data["time_unit"]
        if isinstance(time_unit, dict):
            raise ValueError(
                f"`time_unit` is a mapping ({time_unit}), which states a unit per event type. Only "
                "MedPCCodedEventsInterface can use one, since only there do several event types share an array. "
                "Pass a single unit here."
            )
        return time_unit

    def _validate_non_decreasing(
        self, times: np.ndarray, medpc_name: str, event_type_source_id: str | None = None
    ) -> None:
        """Raise where a decoded series runs backwards, unless the caller has turned the check off.

        This is the one check that catches a misread unit or mode, because every one of them decodes without
        error and only the ordering betrays it. A program written in Relative Mode and read as absolute is the
        common case: the intervals are small and arbitrary, so the series jumps around instead of climbing.
        """
        if len(times) < 2:
            return
        backwards = np.flatnonzero(np.diff(times) < 0)
        if len(backwards) == 0:
            return
        first = int(backwards[0])
        of_type = f" (event type '{event_type_source_id}')" if event_type_source_id is not None else ""
        raise ValueError(
            f"The onsets read from the MedPC variable '{medpc_name}'{of_type} run backwards: event {first} is at "
            f"{times[first]:.6g} s and event {first + 1} is at {times[first + 1]:.6g} s. Onsets cannot go "
            "backwards. Check the MSN program that wrote the file. The likeliest cause is Med Associates' "
            "Relative Mode, where the program stored the time since the previous event rather than the time "
            "since the session began: pass `relative_mode=True` to accumulate them. Failing that, a `time_unit` "
            f"other than the one the program divided by before storing. {self._extra_decoding_causes()}If the "
            "program shows the file is already being read as it was written, this is a layout NeuroConv does not "
            "support yet: please open an issue at https://github.com/catalystneuro/neuroconv/issues with the "
            "program and a sample file."
        )

    def _extra_decoding_causes(self) -> str:
        """Return the causes of a backwards series that only some layouts can have."""
        return ""


class MedPCArrayEventsInterface(_MedPCEventsInterface):
    """Data Interface for the discrete events of a MedPC file that holds one array per event type.

    Each lettered array is one event type, holding that type's onset times in seconds, so the array's name is the
    event type's identity. Which arrays those are is decided by the MSN program that wrote the file and stated
    through ``event_configuration``. An entry naming a ``duration`` is durative and takes its per-event durations
    from a second array; one naming a ``payload`` carries a per-event value from each array it names as a column
    of the event type's table.

    Use :class:`MedPCCodedEventsInterface` instead for a file whose events are all in one array as
    ``TIME.EVENTCODE`` values. This interface replaces
    :class:`~neuroconv.datainterfaces.behavior.medpc.medpcdatainterface.MedPCInterface`, which reads the same
    layout and writes it as ``ndx-events`` objects and ``IntervalSeries`` into the behavior processing module.
    """

    display_name = "MedPCArrayEvents"
    info = "Interface for the discrete events of MedPC files holding one array per event type."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        session_header: dict,
        event_configuration: dict,
        time_unit: TimeUnit | float = "seconds",
        relative_mode: bool = False,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """
        Initialize MedPCArrayEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the MedPC file.
        session_header : dict
            The header fields identifying which of the file's sessions to read, keyed by the header line's name
            ('Start Date', 'End Date', 'Subject', 'Experiment', 'Group', 'Box', 'Start Time', 'End Time', 'MSN') and
            valued as that session carries them. Whichever fields tell the sessions apart is a property of how the
            file was collected, so pass as many as it takes to name exactly one; the first session matching all of
            them is read.
            ex. {"Start Date": "04/10/19", "Start Time": "12:36:13"} where one animal ran on several days and the
            date, or the date and the time where it ran twice in a day, is what separates them
            ex. {"Start Date": "10/06/22", "Subject": "cohort10-M3.3"} where a cohort's animals were pooled into one
            file and the subject is needed as well
        event_configuration : dict
            The event types of a per-array file, keyed by the MedPC variable holding their onset times (ex. 'A').
            That variable is the event type's identifier, the handle ``get_event_times`` takes and the key of its
            metadata entry. Each value states how that array is read, or is None where the array is a plain list
            of onsets: an optional 'duration' naming the MedPC variable that holds the per-event durations, which
            makes the type durative rather than a point event, and an optional 'payload' listing MedPC variables
            holding one value per event, each written as a column of the same table.

            Nothing here names anything. A MedPC variable is a slot number rather than a label, so an event type
            arrives called 'A' and a payload column called 'K'; set ``event_name`` and ``column_name`` in the
            editable metadata, which is also where a payload column's raw codes are relabelled and explained
            through ``column_categories``.
            ex. {"A": None, "G": {"duration": "E"}, "S": {"payload": ["K"]}}
        time_unit : str or float, optional
            What one stored value is worth, default = "seconds". Either a named unit, "decaseconds",
            "seconds", "deciseconds", "centiseconds" or "milliseconds", or a number of seconds. MedPC stores
            whatever the MSN program divided by before writing and records neither that choice nor the box's
            timing resolution, so it is stated rather than detected. A program that stored the raw `BTIME`
            counter takes the resolution as a number: 0.002 on a 2 ms system, 0.005 on a 5 ms one.
        relative_mode : bool, optional
            Whether the program wrote each value as the time since the previous event rather than the time since
            the session began, default = False. This is Med Associates' own term, from the shipped example
            procedures that use it: "Relative Mode means that each event is listed by the amount of time that has
            passed since the last event has happened". The values are accumulated when True, because a time
            written into NWB is the time since the session started.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata. If None
            (default), "medpc" is used, so several MedPC interfaces in one conversion need a key each.
        verbose : bool, optional
            Whether to print verbose output, by default False.
        """

        _validate_time_arguments(time_unit=time_unit)
        super().__init__(
            file_path=file_path,
            session_header=session_header,
            event_configuration=event_configuration,
            time_unit=time_unit,
            relative_mode=relative_mode,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "medpc"
        self._header_dict = None

    def _read_events(self) -> dict[str, _EventsData]:
        """Read one event type per declared array, plus the arrays named as its durations and payload."""
        event_configuration = self.source_data["event_configuration"]

        # Read every array in one pass, keyed by the MedPC variable name itself so the event type's identifier is
        # the source's own handle for it rather than a name that has to be mapped back.
        read_dict = {}
        for medpc_name, info_dict in event_configuration.items():
            read_dict[medpc_name] = {"name": medpc_name, "is_array": True}
            durations_variable = (info_dict or {}).get("duration")
            if durations_variable is not None:
                read_dict[durations_variable] = {"name": durations_variable, "is_array": True}
            for value_name in (info_dict or {}).get("payload", []):
                read_dict[value_name] = {"name": value_name, "is_array": True}
        session_dict = self._read_session(medpc_name_to_info_dict=read_dict)

        events_data_dict = {}
        for medpc_name, info_dict in event_configuration.items():
            raw_timestamps = self._get_variable_array(session_dict=session_dict, medpc_name=medpc_name)
            timestamps = self._decode_times(values=raw_timestamps, medpc_name=medpc_name)
            durations = None
            durations_variable = (info_dict or {}).get("duration")
            if durations_variable is not None:
                # A duration is an elapsed time, so it takes the same unit as the onsets. It is never relative,
                # since each one already is an interval, and it is never accumulated.
                durations = self._scale_to_seconds(
                    self._get_variable_array(session_dict=session_dict, medpc_name=durations_variable)
                )
                if len(durations) > len(timestamps):
                    raise ValueError(
                        f"The event type '{medpc_name}' has {len(timestamps)} onsets but its durations array "
                        f"'{durations_variable}' holds {len(durations)} values, so the two cannot be paired."
                    )
                # A session cut short mid-event leaves its last onsets without an offset, which the writer records
                # as a missing duration rather than dropping the onset.
                missing = len(timestamps) - len(durations)
                if missing > 0:
                    durations = np.concatenate([durations, np.full(shape=missing, fill_value=np.nan)])
            payload = {}
            for value_name in (info_dict or {}).get("payload", []):
                values = self._get_variable_array(session_dict=session_dict, medpc_name=value_name)
                # A value array holds one value per event, so a length that does not match the onsets is a
                # mis-stated variable rather than something to pad: unlike a missing offset, there is no reading
                # of the file under which some events have a value and the rest do not.
                if len(values) != len(timestamps):
                    raise ValueError(
                        f"The event type '{medpc_name}' has {len(timestamps)} events but its value array "
                        f"'{value_name}' holds {len(values)} values, so they are not one value per event. Note "
                        "that MedPC pads an array to the length it was dimensioned at and this reader trims those "
                        "trailing zeros, which shortens a value array whose last values are genuinely zero."
                    )
                payload[value_name] = _to_integer_where_whole(values=values)
            events_data_dict[medpc_name] = _EventsData(
                event_type_source_id=medpc_name, timestamps=timestamps, durations=durations, payload=payload
            )
        return events_data_dict

    def _payload_variables(self, event_type_source_id: str) -> list[str]:
        """Return the value arrays one event type carries."""
        return (self.source_data["event_configuration"][event_type_source_id] or {}).get("payload", [])


class MedPCCodedEventsInterface(_MedPCEventsInterface):
    """Data Interface for the discrete events of a MedPC file that carries the event type in the data.

    One array holds the onset times of every event of the session, and which type each one is comes from the data
    rather than from the array's name, in either of the two ways an MSN program does that:

    - **Packed into the time value.** The classic ``TIME.EVENTCODE`` form, written by a line like
      ``Set A(Y) = BTIME-U + code/1000``: the code rides in the fractional digits and the time is the integer
      part. ``event_code_factor`` is the divisor the program used and ``event_code_position`` is "fraction". Some programs
      pack the other way round, adding a large constant so the code sits in the leading digits
      (``^PeckLeft=10000`` with ``set x(y)=^PeckLeft+Btime/1"``, giving ``aabbbb.bbb``); that is
      ``event_code_position="leading"`` with ``event_code_factor=10000``.
    - **In a companion array.** A second array of the same length holds one code per event
      (``DIM B`` for all event times beside ``DIM C`` for all event identities). Name it with
      ``event_type_variable`` and nothing is unpacked.

    Every code found becomes an event type identified by its digits, so the file names its own event types and
    nothing has to be declared beyond how to read them.

    Use :class:`MedPCArrayEventsInterface` instead for a file that holds one array per event type.
    """

    display_name = "MedPCCodedEvents"
    info = "Interface for the discrete events of MedPC files carrying the event type in the data."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        session_header: dict,
        timestamps_variable: str,
        event_type_variable: str | None = None,
        event_code_factor: int | None = None,
        event_code_position: Literal["fraction", "leading"] | None = None,
        time_unit: TimeUnit | float | dict[str, TimeUnit | float] = "seconds",
        relative_mode: bool = False,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """
        Initialize MedPCCodedEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the MedPC file.
        session_header : dict
            The header fields identifying which of the file's sessions to read, keyed by the header line's name
            ('Start Date', 'End Date', 'Subject', 'Experiment', 'Group', 'Box', 'Start Time', 'End Time', 'MSN') and
            valued as that session carries them. Whichever fields tell the sessions apart is a property of how the
            file was collected, so pass as many as it takes to name exactly one; the first session matching all of
            them is read.
            ex. {"Start Date": "04/10/19", "Start Time": "12:36:13"} where one animal ran on several days and the
            date, or the date and the time where it ran twice in a day, is what separates them
            ex. {"Start Date": "09/25/15", "Subject": "ML03"} where a cohort's animals were pooled into one file
        timestamps_variable : str
            The MedPC variable holding the event times (ex. 'A'). The MSN program picks it, so it is stated
            rather than defaulted: 'A' is what the readers of this convention happen to use, not something the
            format fixes.
        event_type_variable : str, optional
            The MedPC variable holding one event code per event, where the program wrote the codes into their own
            array instead of packing them into the times. When given, ``timestamps_variable`` is read as plain
            times and nothing is unpacked, so ``event_code_factor`` and ``event_code_position`` do not apply.
            ex. 'C', beside timestamps in 'B'
        event_code_factor : int, optional
            The constant the program divided the code by, or added it to, when packing, default = 1000. With
            ``event_code_position="fraction"`` it is the divisor of ``time + code/divisor``, so 1000 leaves three
            fractional digits and 100 leaves two. With ``event_code_position="leading"`` it is the multiplier of
            ``code * divisor + time``, so 10000 puts the code above four digits of time.
        event_code_position : {"fraction", "leading"}, optional
            Where in the value the code sits, default = "fraction". Which one a program used cannot be read off
            the data reliably, since both produce plausible numbers; the MSN program settles it.
        time_unit : str, float or dict, optional
            What one stored value is worth, default = "seconds". Either a named unit, "decaseconds",
            "seconds", "deciseconds", "centiseconds" or "milliseconds", or a number of seconds. MedPC stores
            whatever the MSN program divided by before writing and records neither that choice nor the box's
            timing resolution, so it is stated rather than detected. A program that stored the raw `BTIME`
            counter takes the resolution as a number: 0.002 on a 2 ms system, 0.005 on a 5 ms one.

            May also be a dict giving one unit per event type, keyed as the identifiers this interface
            reports (ex. ``{"1": "seconds", "3": "decaseconds"}``). A program can time two event types
            differently and store them in the same array; nothing in the file records that it did, and the
            ordinary sign of it is that the pooled times run backwards while each type on its own climbs. A
            mapping has to name every type the array holds.
        relative_mode : bool, optional
            Whether the program wrote each value as the time since the previous event rather than the time since
            the session began, default = False. This is Med Associates' own term, from the shipped example
            procedures that use it: "Relative Mode means that each event is listed by the amount of time that has
            passed since the last event has happened". The values are accumulated when True, because a time
            written into NWB is the time since the session started.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata. If None
            (default), "medpc" is used, so several MedPC interfaces in one conversion need a key each.
        verbose : bool, optional
            Whether to print verbose output, by default False.
        """
        _validate_time_arguments(time_unit=time_unit)
        if event_type_variable is not None and (event_code_factor is not None or event_code_position is not None):
            raise ValueError(
                f"`event_type_variable` names '{event_type_variable}' as the array holding the codes, so nothing "
                "is unpacked from the times and `event_code_factor` and `event_code_position` would not be used. Pass the "
                "companion array or the packing arguments, not both."
            )
        event_code_factor = 1000 if event_code_factor is None else event_code_factor
        event_code_position = "fraction" if event_code_position is None else event_code_position
        if event_code_factor < 10:
            raise ValueError(
                f"`event_code_factor` is {event_code_factor}, which leaves no digits for a code. It is the "
                "constant the program combined the code with: 1000 for `time + code/1000`, 10000 for "
                "`code * 10000 + time`."
            )

        super().__init__(
            file_path=file_path,
            session_header=session_header,
            timestamps_variable=timestamps_variable,
            event_type_variable=event_type_variable,
            event_code_factor=event_code_factor,
            event_code_position=event_code_position,
            time_unit=time_unit,
            relative_mode=relative_mode,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "medpc"
        self._header_dict = None

    def _read_events(self) -> dict[str, _EventsData]:
        """Read the one time array, recover each event's code, and group the times by it."""
        timestamps_variable = self.source_data["timestamps_variable"]
        event_type_variable = self.source_data["event_type_variable"]

        to_read = [timestamps_variable] + ([event_type_variable] if event_type_variable else [])
        session_dict = self._read_session(
            medpc_name_to_info_dict={name: {"name": name, "is_array": True} for name in to_read}
        )
        values = self._get_variable_array(session_dict=session_dict, medpc_name=timestamps_variable)

        if event_type_variable is not None:
            codes = self._get_variable_array(session_dict=session_dict, medpc_name=event_type_variable)
            if len(codes) != len(values):
                raise ValueError(
                    f"The times in '{timestamps_variable}' number {len(values)} but the codes in "
                    f"'{event_type_variable}' number {len(codes)}, so they are not one code per event."
                )
            raw_times = values
        else:
            raw_times, codes = self._unpack(values=values)

        identifiers = np.asarray([self._format_code(code) for code in codes.tolist()])
        if self.source_data["relative_mode"]:
            # A gap is between consecutive events whatever type they are, so the accumulation is over the whole
            # array and only the scaling can differ per type.
            raw_times = np.cumsum(raw_times)
        timestamps = np.empty(len(raw_times), dtype=float)
        for event_type_source_id in dict.fromkeys(identifiers.tolist()):
            of_this_type = identifiers == event_type_source_id
            timestamps[of_this_type] = self._scale_to_seconds(
                raw_times[of_this_type], time_unit=self._time_unit_for(event_type_source_id)
            )
        self._validate_within_the_session(times=timestamps, medpc_name=timestamps_variable)

        # Every code found becomes an event type, in the order the codes first occur, whether or not the legend
        # names it: the legend gives a code a name, and a file is not read less completely for lacking one.
        events_data_dict = {}
        # A program that writes every event of one type before the next leaves the pooled array unsorted by
        # construction, so its order says nothing. One that interleaves the types is writing them as they
        # happened, and then the pooled order is a time order and has to hold.
        if not _is_grouped_by_type(identifiers):
            self._validate_non_decreasing(times=timestamps, medpc_name=timestamps_variable)
        for event_type_source_id in dict.fromkeys(identifiers.tolist()):
            of_this_type = timestamps[identifiers == event_type_source_id]
            # Checked per type as well, since no single type's onsets can run backwards whichever way the
            # program wrote them out.
            self._validate_non_decreasing(
                times=of_this_type,
                medpc_name=timestamps_variable,
                event_type_source_id=event_type_source_id,
            )
            events_data_dict[event_type_source_id] = _EventsData(
                event_type_source_id=event_type_source_id, timestamps=of_this_type
            )
        return events_data_dict

    def _time_unit_for(self, event_type_source_id: str) -> str:
        """Return the unit one event type's times are in.

        A single ``time_unit`` covers the whole array, which is the ordinary case. A mapping states one per
        event type, for a program that timed two types differently and stored them in the same array; that
        happens, and nothing in the file records it.
        """
        time_unit = self.source_data["time_unit"]
        if not isinstance(time_unit, dict):
            return time_unit
        if event_type_source_id not in time_unit:
            raise ValueError(
                f"`time_unit` is a mapping and names {sorted(time_unit)}, but the array also holds the event "
                f"type '{event_type_source_id}'. A mapping has to give a unit for every type in the array, "
                "since a type left out has no unit at all."
            )
        return time_unit[event_type_source_id]

    def _unpack(self, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Split packed values into their time part and their code part."""
        divisor = self.source_data["event_code_factor"]
        if self.source_data["event_code_position"] == "fraction":
            times = np.floor(values)
            # The values are read as floats, so the code is recovered by rounding rather than by comparing
            # fractions, which would fail on the representation error a decimal fraction carries in binary.
            codes = np.round((values - times) * divisor)
            # A fraction that rounds up to the scale itself has more digits than the scale leaves for a code,
            # which is what a value carrying more decimals than the program packed looks like.
            too_wide = np.flatnonzero(codes >= divisor)
            if len(too_wide):
                index = int(too_wide[0])
                raise ValueError(
                    f"The value {values[index]:.6f} of '{self.source_data['timestamps_variable']}' leaves a code "
                    f"of {int(codes[index])}, which `event_code_factor={divisor}` has no room for. The array carries "
                    "more decimals than that scale accounts for, so either the program packed with a larger "
                    "scale or these values are not packed codes at all."
                )
        else:
            codes = np.floor(values / divisor)
            times = values - codes * divisor
        return times, codes

    def _extra_decoding_causes(self) -> str:
        """Name the packing arguments too, since a wrong one leaves part of the code in the time."""
        if self.source_data["event_type_variable"] is not None:
            return ""
        return "For a packed array, a `event_code_factor` or `event_code_position` that leaves part of the code in the time. "

    def _format_code(self, code: float) -> str:
        """Return the identifier one event code is known by.

        A code packed into the fraction is zero-padded to the width its divisor implies, so the identifiers read
        as the program writes them (``'011'`` for a code of 11 packed with 1000). A code in the leading digits has
        no such width, since the digits below it are the time, and a code from a companion array has none either,
        where some programs use fractional codes such as 3.1. Both are left as the program wrote them.
        """
        if not float(code).is_integer():
            return str(code)
        if self.source_data["event_type_variable"] is not None or self.source_data["event_code_position"] == "leading":
            return str(int(code))
        width = len(str(self.source_data["event_code_factor"])) - 1
        return f"{int(code):0{width}d}"


def _is_grouped_by_type(identifiers: np.ndarray) -> bool:
    """Whether each event type occupies one contiguous run of the array.

    That is what a program writing out all of one type before the next produces, and it is the one case where the
    pooled array's order carries no information about when the events happened.
    """
    if len(identifiers) < 2:
        return True
    changes = identifiers[1:] != identifiers[:-1]
    runs = int(np.count_nonzero(changes)) + 1
    return runs == len(set(identifiers.tolist()))


def _validate_time_arguments(time_unit) -> None:
    """Check that every unit given is a name or a positive number of seconds."""
    units = time_unit.values() if isinstance(time_unit, dict) else [time_unit]
    for unit in units:
        if isinstance(unit, (int, float)) and not isinstance(unit, bool):
            if unit <= 0:
                raise ValueError(
                    f"`time_unit` is {unit}, which is not a length of time. A number states what one stored "
                    "value is worth in seconds, so a raw BTIME counter takes the box's timing resolution: "
                    "0.002 on a 2 ms system, 0.005 on a 5 ms one."
                )
        elif unit not in _TIME_UNIT_TO_SECONDS:
            raise ValueError(
                f"`time_unit` is {unit!r}, which is neither one of {sorted(_TIME_UNIT_TO_SECONDS)} nor a number "
                "of seconds per stored value."
            )


def _to_integer_where_whole(values: np.ndarray) -> np.ndarray:
    """Cast a value array read as floats to integers where every value is whole.

    MedPC writes every array as decimals, so a trial type reads as ``[3.0, 1.0, ...]``. Casting those to integers
    is what lets the metadata's ``column_categories`` be keyed by the code as the program writes it (``{1: "water"}``
    rather than ``{1.0: "water"}``), and it keeps the written column's dtype honest about what it holds.
    """
    if len(values) > 0 and np.all(np.mod(values, 1) == 0):
        return values.astype(int)
    return values


def _parse_clock_time(value: str | None) -> float | None:
    """Return a header clock time as seconds past midnight, or None where it is absent or unreadable."""
    if not value:
        return None
    parts = value.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = (float(part) for part in parts)
    except ValueError:
        return None
    return hours * 3600 + minutes * 60 + seconds


def _parse_session_start_time(start_date: str | None, start_time: str | None) -> datetime | None:
    """Build the session's start time out of the header's 'Start Date' and 'Start Time', or None if it cannot be.

    MedPC prints the date in the short format of the machine it ran on, which carries no marker of which field is
    the month, so month-first is tried first and day-first only after it fails, which is exactly the dates whose
    first field is above twelve. A file that is genuinely day-first and dated on or before the twelfth is read a
    month off, and there is nothing in the file to catch that with, so the header's format is worth checking
    against the recording's filename where the program writes one.
    """
    if not start_date or not start_time:
        return None
    for date_format in ("%m/%d/%y", "%m/%d/%Y", "%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(f"{start_date} {start_time}", f"{date_format} %H:%M:%S")
        except ValueError:
            continue
    return None
