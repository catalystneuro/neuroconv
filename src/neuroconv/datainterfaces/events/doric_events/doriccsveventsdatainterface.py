"""Interface for discrete events (digital IO) from Doric Neuroscience Studio CSV exports."""

import numpy as np
from pydantic import FilePath, validate_call

from neuroconv.utils import DeepDict

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools.events import validate_event_specs
from ....tools.signal_processing import discretize_trace


class DoricCSVEventsInterface(BaseEventsInterface):
    """Convert discrete events from a Doric Neuroscience Studio CSV export to NWB.

    A DoricStudio CSV export stores its channels under a grouped two-row header: the first row names
    each channel's group (e.g. ``Analog In. | Ch.1``, ``Digital I/O | Ch.1``) and the second row names
    each column (e.g. ``Time(s)``, ``DI/O-1``). The digital IO lines (the columns whose group is
    ``Digital I/O``) are sampled ``0``/``1`` traces on the shared ``Time(s)`` clock. This interface
    edge-detects each digital line and writes one ``pynwb.event.EventsTable`` per line into
    ``nwbfile.events``. How each line's transitions become events is set per line by ``event_specs``;
    by default every line is read as a ``high_period`` (each rising edge is an event onset, its duration
    the span to the next falling edge). A line that never toggles is skipped.

    This reads the DoricStudio CSV export only; the ``.doric`` HDF5 layouts are handled by
    :class:`.DoricEventsInterface`. The CSV export carries no session start time, so the user must
    supply ``NWBFile/session_start_time`` via editable metadata.
    """

    keywords = ("events", "Doric")
    display_name = "DoricCSVEvents"
    info = "Data Interface for converting discrete events (digital IO) from Doric Neuroscience Studio CSV exports."
    associated_suffixes = ("csv",)
    # The reading a digital line defaults to when event_specs does not set one: the lossless durative
    # reading (onset at the rising edge, duration to the falling edge, for an active-high line).
    _default_detect = "high_period"

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        event_specs: dict | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the DoricCSVEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the DoricStudio CSV export.
        event_specs : dict, optional
            Per digital line, how its transitions become events, keyed by the line's column name
            (e.g. ``{"DI/O-1": {"detect": "high_period"}}``). ``detect`` is one of ``"rising"`` /
            ``"falling"`` (a point event at each edge) or ``"high_period"`` / ``"low_period"`` (a
            durative event, onset at one edge and duration to the next opposite edge), default
            ``"high_period"`` (lossless for an active-high line; use ``"low_period"`` for an
            active-low line). If None (default), every digital line in the file is read as a
            ``high_period``. When given, only the named lines are read (selection by inclusion).
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata.
            If None (default), ``"doric_events"`` is used.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            file_path=file_path,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "doric_events"
        self._time_column, digital_columns = self._discover_columns(self.source_data["file_path"])
        # available_lines: source_id (the column name, e.g. "DI/O-1") -> its (group, name) column handle.
        self._available_lines = {str(column[1]): column for column in digital_columns}
        self._resolved_specs = self._resolve_event_specs(event_specs)

    @staticmethod
    def _read_doric_csv(file_path):
        """Read the DoricStudio two-row-header CSV into a DataFrame with ``(group, name)`` MultiIndex columns.

        DoricStudio writes a trailing comma on the header rows, so the header has one more field than the
        data. Reading the two header rows and the data separately (each a consistent width) sidesteps
        pandas' header/data length-mismatch warning; the MultiIndex is then trimmed to the data's column
        count, dropping the phantom trailing column that comma leaves behind.
        """
        import pandas as pd

        header_rows = pd.read_csv(file_path, header=None, nrows=2, dtype=str)  # the (group, name) header rows
        data = pd.read_csv(file_path, header=None, skiprows=2)  # data only -> no header/data length mismatch
        width = data.shape[1]
        data.columns = pd.MultiIndex.from_arrays([header_rows.iloc[0, :width], header_rows.iloc[1, :width]])
        return data

    @staticmethod
    def _discover_columns(file_path):
        """Return ``(time_column, [digital_columns])`` from the CSV's grouped two-row header.

        The columns are ``(group, name)`` pairs. The time column is the one whose name holds ``Time``
        (the shared ``Time(s)`` clock); the digital lines are the columns whose group is ``Digital I/O``.
        Analog columns (``Analog In.``/``Analog Out.``) and the trailing empty column are ignored. Each
        digital column's name (e.g. ``DI/O-1``) is its ``event_type_source_id`` (identity-in-header).
        """
        import pandas as pd

        header_rows = pd.read_csv(file_path, header=None, nrows=2, dtype=str)  # header only -> no length warning
        columns = list(zip(header_rows.iloc[0], header_rows.iloc[1]))
        time_columns = [column for column in columns if "time" in str(column[1]).lower()]
        digital_columns = [column for column in columns if "digital" in str(column[0]).lower()]
        time_column = time_columns[0] if time_columns else None
        return time_column, digital_columns

    def _resolve_event_specs(self, event_specs: dict | None) -> dict:
        """Turn ``event_specs`` into resolved fields ``{event_type_source_id: {"detect", "column"}}``.

        ``None`` produces the code default (:meth:`_default_event_specs`); a user dict is first validated
        (:func:`~neuroconv.tools.events.validate_event_specs`, which raises). Both are then parsed into
        the internal shape here. Each digital line's column name (e.g. ``DI/O-1``) is its
        ``event_type_source_id`` (identity-in-header).
        """
        if event_specs is None:
            event_specs = self._default_event_specs()
        else:
            validate_event_specs(event_specs, self._available_lines)
        return {
            source_id: {"detect": entry.get("detect", self._default_detect), "column": self._available_lines[source_id]}
            for source_id, entry in event_specs.items()
        }

    def _default_event_specs(self) -> dict:
        """The code default (no user ``event_specs``): every digital line with the default ``detect``.

        Trusted (not user input), so it skips validation and flows straight into the parse; a line that
        never toggles is skipped later in :meth:`_get_events_data_dict`.
        """
        return {source_id: {"detect": self._default_detect} for source_id in self._available_lines}

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the DoricCSVEventsInterface.

        The DoricStudio CSV export carries no session start time, so ``NWBFile/session_start_time`` is
        not populated here; the user must supply it via editable metadata.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()

        # Identity-in-header: each digital column name is its own event type. The column name is kept as
        # the event_type_source_id, but the human-facing event_name drops the "/" (an NWB object name
        # cannot contain a slash), so "DI/O-1" seeds a table named "DIO-1". Only lines that carry at
        # least one event appear (a constant line is skipped), matching _get_events_data_dict.
        for event_type_source_id in self._get_events_data_dict():
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = {
                "event_name": event_type_source_id.replace("/", "")
            }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation by edge-detecting each digital line, cached.

        Each selected digital line becomes one :class:`_EventsData` keyed by its ``event_type_source_id``
        (the column name): its trace is edge-detected per the line's ``detect`` (via
        :func:`discretize_trace`) into onset frames and, for a durative reading, per-event durations. The
        onset timestamps are read from the shared ``Time(s)`` column; durations (in frames) are scaled to
        seconds by the file's sampling period. A line with no event (constant, or never opening) is
        skipped, so the empty state never reaches the writer.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        dataframe = self._read_doric_csv(self.source_data["file_path"])
        time = dataframe[self._time_column].to_numpy(dtype="float64")
        frame_period = float(np.median(np.diff(time)))  # regular DoricStudio clock; duration frames -> seconds

        events_data_dict = {}
        for event_type_source_id, spec in self._resolved_specs.items():
            data = dataframe[spec["column"]].to_numpy(dtype="float64")
            # A digital line is a densely sampled 0/1 trace; threshold=0.5 discretizes it strictly.
            onset_frames, duration_frames = discretize_trace(data, spec["detect"], threshold=0.5)
            if onset_frames.size == 0:
                continue  # a line with no matching edge has no event; skip it entirely
            onsets = time[onset_frames]
            durations = None if duration_frames is None else duration_frames * frame_period
            events_data_dict[event_type_source_id] = _EventsData(
                event_type_source_id=event_type_source_id, timestamps=onsets, durations=durations
            )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
