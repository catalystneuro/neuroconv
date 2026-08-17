import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from neuroconv.utils import DeepDict

from ..baseeventsinterface import BaseEventsInterface, _EventsData

# The reader is shared with the deprecated MedPCInterface, which still owns it; it moves into this package
# when that interface is removed.
from ...behavior.medpc.medpc_helpers import read_medpc_file


class MedPCEventsInterface(BaseEventsInterface):
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

    Different sessions are usually separated by a blank line or two, so the session to read is picked out by
    ``session_conditions``.

    Where an event type's identity lives is decided by the MSN program that wrote the file, so this interface takes
    either of the two layouts:

    - **Per-array** (``medpc_name_to_info_dict``): each lettered array is one event type holding that type's onset
      times in seconds. An entry that names a ``durations_name`` is durative and takes its per-event durations from
      a second array, and one that names ``value_names`` carries a per-event value from each array it names as a
      column of the event type's table.
    - **Packed-code** (``packed_code_configuration``): one array holds every event as a ``TIME.EVENTCODE`` value,
      whose integer part is the time in clock ticks and whose fractional digits are the code of the event type.
      Each distinct code becomes its own event type.

    Each event type is written as a ``pynwb.event.EventsTable`` into ``nwbfile.events``. This replaces
    :class:`~neuroconv.datainterfaces.behavior.medpc.medpcdatainterface.MedPCInterface`, which writes the same
    events as ``ndx-events`` objects and ``IntervalSeries`` into the behavior processing module and is deprecated.
    """

    keywords = ("events", "behavior", "MedPC")
    display_name = "MedPCEvents"
    info = "Interface for the discrete events of MedPC output files."
    associated_suffixes = (".txt",)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        session_conditions: dict,
        start_variable: str,
        medpc_name_to_info_dict: dict | None = None,
        packed_code_configuration: dict | None = None,
        metadata_key: str = "medpc",
        verbose: bool = False,
    ):
        """
        Initialize MedPCEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the MedPC file.
        session_conditions : dict
            The conditions that define the session. The keys are the names of the single-line variables (ex. 'Start Date')
            and the values are the values of those variables for the desired session (ex. '11/09/18').
        start_variable : str
            The name of the variable that starts the session (ex. 'Start Date').
        medpc_name_to_info_dict : dict, optional
            The event types of a per-array file, keyed by the name of the MedPC variable holding their onset times
            (ex. 'A'). That name is the event type's identifier, the handle ``get_event_times`` takes and the key of
            its metadata entry. Each value is an info dictionary with a required 'name', which seeds the editable
            ``event_name``, an optional 'durations_name' naming the MedPC variable that holds the per-event
            durations in seconds, which makes the type durative, and an optional 'value_names' mapping a MedPC
            variable holding one value per event to the name of the column it is written as. A value column is
            seeded bare, so relabelling its raw codes and saying what they mean is done in the metadata through
            ``column_categories``.
            ex. {"G": {"name": "port_entries", "durations_name": "E"}}
            ex. {"S": {"name": "cs_presentations", "value_names": {"K": "cs_type"}}}
        packed_code_configuration : dict, optional
            The configuration of a packed-code file, whose events are all held in one array of ``TIME.EVENTCODE``
            values. Takes a required 'clock_ticks_per_second' (the rate of the program's clock, ex. 500 for a 2 ms
            clock), an optional 'variable_name' naming the array to read (default 'A'), and an optional
            'code_to_info_dict' mapping an event code to an info dictionary with a 'name'. Every code found in the
            file becomes an event type identified by its zero-padded digits (ex. '011'), named after the legend
            where one is given and 'code_<digits>' where none is.
            ex. {"clock_ticks_per_second": 500, "code_to_info_dict": {"001": {"name": "lick"}}}
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata, default = "medpc".
        verbose : bool, optional
            Whether to print verbose output, by default False.
        """
        if (medpc_name_to_info_dict is None) == (packed_code_configuration is None):
            raise ValueError(
                "Pass exactly one of `medpc_name_to_info_dict` (one lettered array per event type) or "
                "`packed_code_configuration` (one array of TIME.EVENTCODE values); the MSN program that wrote the "
                "file decides which layout it is in."
            )
        for medpc_name, info_dict in (medpc_name_to_info_dict or {}).items():
            if "name" not in info_dict:
                raise ValueError(
                    f"The entry for the MedPC variable '{medpc_name}' has no 'name', which seeds the event type's "
                    f"editable event_name. Pass {{'name': ...}} for every variable that holds events."
                )
        if packed_code_configuration is not None and "clock_ticks_per_second" not in packed_code_configuration:
            raise ValueError(
                "`packed_code_configuration` must state 'clock_ticks_per_second', the rate of the program's clock "
                "(500 for a 2 ms clock, 200 for a 5 ms one). A packed-code file stores its times in clock ticks and "
                "does not carry the rate, so the wrong value silently scales every timestamp."
            )

        super().__init__(
            file_path=file_path,
            session_conditions=session_conditions,
            start_variable=start_variable,
            medpc_name_to_info_dict=medpc_name_to_info_dict,
            packed_code_configuration=packed_code_configuration,
            verbose=verbose,
        )
        self.metadata_key = metadata_key

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the MedPCEventsInterface.

        ``NWBFile/session_start_time`` is intentionally left unset: the session's 'Start Date' and 'Start Time' are
        single-line variables of the source file, which this interface does not read, so it must be supplied by the
        user via editable metadata. Read them with
        :func:`~neuroconv.datainterfaces.behavior.medpc.medpc_helpers.get_medpc_variables`.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()

        # Declare one entry per event type, seeding each editable event_name from the name the user gave the array
        # (per-array) or its code's legend entry (packed-code), plus one column per value array the type carries.
        # A MedPC file carries no prose of its own, so no description is reported here and a value column's codes
        # are left unlabelled: what an array or a code records lives in the MSN program and in the experimenter's
        # head, and is the user's to add.
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        for event_type_source_id in self._get_events_data_dict():
            entry = {"event_name": self._event_name(event_type_source_id)}
            value_names = self._value_names(event_type_source_id=event_type_source_id)
            if value_names:
                entry["columns"] = {
                    medpc_name: {"column_name": column_name} for medpc_name, column_name in value_names.items()
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
            per-array file, or the code's zero-padded digits for a packed-code one, as
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
                "MedPC variable name (per-array) or by the event code (packed-code), and which arrays hold events "
                "is declared on the interface rather than in the metadata. The deprecated MedPCInterface is what "
                "reads metadata['MedPC']."
            )
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation from the MedPC file, cached after the first call.

        A per-array file yields one :class:`_EventsData` per declared array, keyed by its MedPC variable name; a
        packed-code file yields one per event code found in the packed array, keyed by the code's zero-padded digits.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        if self.source_data["medpc_name_to_info_dict"] is not None:
            self._events_data_dict = self._read_per_array_events()
        else:
            self._events_data_dict = self._read_packed_code_events()
        return self._events_data_dict

    def _read_per_array_events(self) -> dict[str, _EventsData]:
        """Read a per-array file: one event type per declared array, plus the arrays named as its durations and values."""
        medpc_name_to_info_dict = self.source_data["medpc_name_to_info_dict"]

        # Read every array in one pass, keyed by the MedPC variable name itself so the event type's identifier is
        # the source's own handle for it rather than a name that has to be mapped back.
        read_dict = {}
        for medpc_name, info_dict in medpc_name_to_info_dict.items():
            read_dict[medpc_name] = {"name": medpc_name, "is_array": True}
            durations_name = info_dict.get("durations_name")
            if durations_name is not None:
                read_dict[durations_name] = {"name": durations_name, "is_array": True}
            for value_name in info_dict.get("value_names", {}):
                read_dict[value_name] = {"name": value_name, "is_array": True}
        session_dict = self._read_session(medpc_name_to_info_dict=read_dict)

        events_data_dict = {}
        for medpc_name, info_dict in medpc_name_to_info_dict.items():
            timestamps = self._get_variable_array(session_dict=session_dict, medpc_name=medpc_name)
            durations = None
            durations_name = info_dict.get("durations_name")
            if durations_name is not None:
                durations = self._get_variable_array(session_dict=session_dict, medpc_name=durations_name)
                if len(durations) > len(timestamps):
                    raise ValueError(
                        f"The event type '{medpc_name}' has {len(timestamps)} onsets but its durations array "
                        f"'{durations_name}' holds {len(durations)} values, so the two cannot be paired."
                    )
                # A session cut short mid-event leaves its last onsets without an offset, which the writer records
                # as a missing duration rather than dropping the onset.
                missing = len(timestamps) - len(durations)
                if missing > 0:
                    durations = np.concatenate([durations, np.full(shape=missing, fill_value=np.nan)])
            payload = {}
            for value_name in info_dict.get("value_names", {}):
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

    def _read_packed_code_events(self) -> dict[str, _EventsData]:
        """Read a packed-code file: split each ``TIME.EVENTCODE`` value and group the times by their code."""
        packed_code_configuration = self.source_data["packed_code_configuration"]
        variable_name = packed_code_configuration.get("variable_name", "A")
        clock_ticks_per_second = packed_code_configuration["clock_ticks_per_second"]

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
        for event_type_source_id in self._packed_code_to_info_dict():
            if event_type_source_id not in events_data_dict:
                events_data_dict[event_type_source_id] = _EventsData(
                    event_type_source_id=event_type_source_id, timestamps=np.array([], dtype=float)
                )
        return events_data_dict

    def _read_session(self, medpc_name_to_info_dict: dict) -> dict:
        """Read the selected session's variables out of the MedPC file."""
        return read_medpc_file(
            file_path=self.source_data["file_path"],
            medpc_name_to_info_dict=medpc_name_to_info_dict,
            session_conditions=self.source_data["session_conditions"],
            start_variable=self.source_data["start_variable"],
        )

    def _get_variable_array(self, session_dict: dict, medpc_name: str) -> np.ndarray:
        """Return one array variable of the read session, naming it if the session does not hold it."""
        if medpc_name not in session_dict:
            raise ValueError(
                f"The MedPC variable '{medpc_name}' is not in the session selected by "
                f"{self.source_data['session_conditions']} of {self.source_data['file_path']}."
            )
        return session_dict[medpc_name]

    def _packed_code_to_info_dict(self) -> dict:
        """Return the packed-code legend keyed by the code's zero-padded digits, as the event types are."""
        code_to_info_dict = self.source_data["packed_code_configuration"].get("code_to_info_dict") or {}
        return {f"{int(code):03d}": info_dict for code, info_dict in code_to_info_dict.items()}

    def _event_name(self, event_type_source_id: str) -> str:
        """Return the ``event_name`` seeded for one event type."""
        medpc_name_to_info_dict = self.source_data["medpc_name_to_info_dict"]
        if medpc_name_to_info_dict is not None:
            return medpc_name_to_info_dict[event_type_source_id]["name"]
        info_dict = self._packed_code_to_info_dict().get(event_type_source_id, {})
        return info_dict.get("name", f"code_{event_type_source_id}")

    def _value_names(self, event_type_source_id: str) -> dict:
        """Return the value arrays one event type carries, mapping each to the column name it is written as.

        Only a per-array event type can carry values: a packed-code value holds the event's identity and nothing
        else, so its type is timestamp-only.
        """
        medpc_name_to_info_dict = self.source_data["medpc_name_to_info_dict"]
        if medpc_name_to_info_dict is None:
            return {}
        return medpc_name_to_info_dict[event_type_source_id].get("value_names", {})


def _to_integer_where_whole(values: np.ndarray) -> np.ndarray:
    """Cast a value array read as floats to integers where every value is whole.

    MedPC writes every array as decimals, so a trial type reads as ``[3.0, 1.0, ...]``. Casting those to integers
    is what lets the metadata's ``column_categories`` be keyed by the code as the program writes it (``{1: "water"}``
    rather than ``{1.0: "water"}``), and it keeps the written column's dtype honest about what it holds.
    """
    if len(values) > 0 and np.all(np.mod(values, 1) == 0):
        return values.astype(int)
    return values
