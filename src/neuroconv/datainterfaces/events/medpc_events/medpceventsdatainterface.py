from datetime import datetime

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
            entry = {"event_name": self._event_name(event_type_source_id)}
            payload_variables = self._payload_variables(event_type_source_id=event_type_source_id)
            if payload_variables:
                entry["columns"] = {
                    medpc_name: {"column_name": column_name} for medpc_name, column_name in payload_variables.items()
                }
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

    def _event_name(self, event_type_source_id: str) -> str:
        """Return the ``event_name`` seeded for one event type."""
        raise NotImplementedError

    def _payload_variables(self, event_type_source_id: str) -> dict:
        """Return the arrays one event type carries as value columns, mapping each to its column name."""
        return {}

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
        return session_dict[medpc_name]


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
        metadata_key: str = "medpc",
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
        event_configuration : dict, optional
            The event types of a per-array file, keyed by the name of the MedPC variable holding their onset times
            (ex. 'A'). That name is the event type's identifier, the handle ``get_event_times`` takes and the key of
            its metadata entry. Each value declares what that array becomes: a required 'name', which seeds the
            editable ``event_name``; an optional 'duration' naming the MedPC variable that holds the per-event
            durations in seconds, which makes the type durative rather than a point event; and an optional
            'payload' mapping a MedPC variable holding one value per event to the name of the column it rides
            along as. A payload column is written with the raw values the program wrote, so relabelling those
            codes and saying what they mean is done in the metadata through ``column_categories``.
            ex. {"G": {"name": "port_entries", "duration": "E"}}
            ex. {"S": {"name": "cs_presentations", "payload": {"K": "cs_type"}}}
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata, default = "medpc".
        verbose : bool, optional
            Whether to print verbose output, by default False.
        """
        for medpc_name, info_dict in event_configuration.items():
            if "name" not in info_dict:
                raise ValueError(
                    f"The entry for the MedPC variable '{medpc_name}' has no 'name', which seeds the event type's "
                    f"editable event_name. Pass {{'name': ...}} for every variable that holds events."
                )

        super().__init__(
            file_path=file_path,
            session_header=session_header,
            event_configuration=event_configuration,
            verbose=verbose,
        )
        self.metadata_key = metadata_key

    def _read_events(self) -> dict[str, _EventsData]:
        """Read one event type per declared array, plus the arrays named as its durations and payload."""
        event_configuration = self.source_data["event_configuration"]

        # Read every array in one pass, keyed by the MedPC variable name itself so the event type's identifier is
        # the source's own handle for it rather than a name that has to be mapped back.
        read_dict = {}
        for medpc_name, info_dict in event_configuration.items():
            read_dict[medpc_name] = {"name": medpc_name, "is_array": True}
            durations_variable = info_dict.get("duration")
            if durations_variable is not None:
                read_dict[durations_variable] = {"name": durations_variable, "is_array": True}
            for value_name in info_dict.get("payload", {}):
                read_dict[value_name] = {"name": value_name, "is_array": True}
        session_dict = self._read_session(medpc_name_to_info_dict=read_dict)

        events_data_dict = {}
        for medpc_name, info_dict in event_configuration.items():
            timestamps = self._get_variable_array(session_dict=session_dict, medpc_name=medpc_name)
            durations = None
            durations_variable = info_dict.get("duration")
            if durations_variable is not None:
                durations = self._get_variable_array(session_dict=session_dict, medpc_name=durations_variable)
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
            for value_name in info_dict.get("payload", {}):
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

    def _event_name(self, event_type_source_id: str) -> str:
        """Return the ``event_name`` seeded for one event type."""
        return self.source_data["event_configuration"][event_type_source_id]["name"]

    def _payload_variables(self, event_type_source_id: str) -> dict:
        """Return the value arrays one event type carries, mapping each to the column name it is written as."""
        return self.source_data["event_configuration"][event_type_source_id].get("payload", {})


class MedPCCodedEventsInterface(_MedPCEventsInterface):
    """Data Interface for the discrete events of a MedPC file that holds them all in one coded array.

    One array carries every event as a ``TIME.EVENTCODE`` value: the integer part is the time in clock ticks and
    the fractional digits are the code of the event type, so the event type is a value in the data rather than the
    array's name. The MSN program packs it with a line like ``Set A(Y) = BTIME-U + code/1000``. This is often
    called a time-event code file, after the reference reader ``med_to_tec.py`` the convention comes from; MedPC
    itself has no name for it, since nothing in the format marks such a file as different.

    Every code the array holds becomes an event type, identified by its zero-padded digits (ex. ``'011'``), so the
    file names its own event types and ``event_configuration`` only supplies names for them.

    Use :class:`MedPCArrayEventsInterface` instead for a file that holds one array per event type.
    """

    display_name = "MedPCCodedEvents"
    info = "Interface for the discrete events of MedPC files holding one coded TIME.EVENTCODE array."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        session_header: dict,
        clock_ticks_per_second: int,
        variable_name: str = "A",
        event_configuration: dict | None = None,
        metadata_key: str = "medpc",
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
            ex. {"Start Date": "10/06/22", "Subject": "cohort10-M3.3"} where a cohort's animals were pooled into one
            file and the subject is needed as well
        clock_ticks_per_second : int
            The rate of the program's clock: 500 for a 2 ms clock, 200 for a 5 ms one. A coded array stores its
            times in clock ticks and the file does not carry the rate, so the wrong value silently scales every
            timestamp in the session.
        variable_name : str, optional
            The MedPC variable holding the coded values, default = "A".
        event_configuration : dict, optional
            Names for the event types, keyed by the event code's zero-padded digits (ex. '011'). Each value takes
            a 'name', which seeds the editable ``event_name``. This is a legend rather than a declaration of what
            to read: every code the array holds becomes an event type whether or not it is named here, and one
            left out is named 'code_<digits>'. A code named here that the file never holds is written as an empty
            table, the type having been declared and never fired. What a code means lives in the MSN program, and
            often in a later version of it whose numbering disagrees with the file, so it cannot be derived.
            ex. {"001": {"name": "lick"}, "011": {"name": "pump_a_on"}}
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata, default = "medpc".
        verbose : bool, optional
            Whether to print verbose output, by default False.
        """
        super().__init__(
            file_path=file_path,
            session_header=session_header,
            clock_ticks_per_second=clock_ticks_per_second,
            variable_name=variable_name,
            event_configuration=event_configuration,
            verbose=verbose,
        )
        self.metadata_key = metadata_key

    def _read_events(self) -> dict[str, _EventsData]:
        """Split each ``TIME.EVENTCODE`` value of the coded array and group the times by their code."""
        variable_name = self.source_data["variable_name"]
        clock_ticks_per_second = self.source_data["clock_ticks_per_second"]

        session_dict = self._read_session(
            medpc_name_to_info_dict={variable_name: {"name": variable_name, "is_array": True}}
        )
        packed = self._get_variable_array(session_dict=session_dict, medpc_name=variable_name)
        # The integer part is the time in clock ticks and the three fractional digits are the event code. The
        # values are read as floats, so the code is recovered by rounding rather than by comparing fractions.
        ticks = np.floor(packed)
        codes = np.round((packed - ticks) * 1000).astype(int)
        timestamps = ticks / clock_ticks_per_second

        # Every code the file holds becomes an event type, in the order the codes first occur, whether or not the
        # legend names it: the legend gives a code a name, and a file is not read less completely for lacking one.
        events_data_dict = {}
        for code in dict.fromkeys(codes.tolist()):
            event_type_source_id = f"{code:03d}"
            events_data_dict[event_type_source_id] = _EventsData(
                event_type_source_id=event_type_source_id, timestamps=timestamps[codes == code]
            )
        # A code the legend names but the file never holds is a type that was declared and never fired, written as
        # an empty table the way a declared per-array variable holding no events is.
        for event_type_source_id in self._code_to_info_dict():
            if event_type_source_id not in events_data_dict:
                events_data_dict[event_type_source_id] = _EventsData(
                    event_type_source_id=event_type_source_id, timestamps=np.array([], dtype=float)
                )
        return events_data_dict

    def _code_to_info_dict(self) -> dict:
        """Return the legend keyed by the code's zero-padded digits, as the event types are."""
        event_configuration = self.source_data["event_configuration"] or {}
        return {f"{int(code):03d}": info_dict for code, info_dict in event_configuration.items()}

    def _event_name(self, event_type_source_id: str) -> str:
        """Return the ``event_name`` seeded for one event type."""
        info_dict = self._code_to_info_dict().get(event_type_source_id, {})
        return info_dict.get("name", f"code_{event_type_source_id}")


def _to_integer_where_whole(values: np.ndarray) -> np.ndarray:
    """Cast a value array read as floats to integers where every value is whole.

    MedPC writes every array as decimals, so a trial type reads as ``[3.0, 1.0, ...]``. Casting those to integers
    is what lets the metadata's ``column_categories`` be keyed by the code as the program writes it (``{1: "water"}``
    rather than ``{1.0: "water"}``), and it keeps the written column's dtype honest about what it holds.
    """
    if len(values) > 0 and np.all(np.mod(values, 1) == 0):
        return values.astype(int)
    return values


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
