import warnings
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import FilePath, validate_call

from neuroconv.utils import DeepDict

from ..baseeventsinterface import BaseEventsInterface, _EventsData


class CSVEventsInterface(BaseEventsInterface):
    """Data Interface for converting discrete events from a single CSV file.

    This is a general-purpose CSV events reader: the caller points at one CSV file and assigns each
    column a role. Every row is one event occurrence at ``timestamps_column`` (seconds); the other
    roles are optional:

    - ``event_type_column`` -- the column, if any, whose value names the *type* of each event. Each
      distinct value becomes its own event type and, by default, its own ``pynwb.event.EventsTable``.
      Merging several types into one table with an ``event_type`` discriminator column is opt-in by
      pointing their ``table_metadata_key`` at a shared key in the editable metadata.
    - ``value_columns`` -- columns carried along as per-event values (payload). Each becomes a value
      column named after its source header, carrying the raw cell values.
    - ``durations_column`` -- a column of per-event durations (seconds), making the events durative
      (written to the table's ``duration`` column). A blank cell becomes ``NaN`` (a missing offset).

    Columns without an assigned role are ignored.

    Notes
    -----
    CSV recordings carry no embedded recording-start timestamp, so :meth:`get_metadata` does NOT
    populate ``NWBFile/session_start_time``. The user must supply it via editable metadata.

    Two source layouts are anticipated but not yet supported: a *wide* format that spreads one event
    type per timestamp column (this interface reads the long/tidy format, one timestamp column plus an
    event-type column), and an *onset/offset* duration style that names a stop-time column and derives
    each duration from it (use ``durations_column`` with the duration precomputed instead).
    """

    keywords = ("events", "CSV")
    display_name = "CSVEvents"
    info = "Data Interface for converting discrete events from a single CSV file."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        timestamps_column: str | int,
        event_type_column: str | int | None,
        value_columns: list[str | int] | None = None,
        durations_column: str | int | None = None,
        metadata_key: str | None = None,
        read_kwargs: dict | None = None,
        verbose: bool = False,
    ):
        """Initialize the CSVEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            The path to the CSV file holding the events.
        timestamps_column : str or int
            The column holding the event timestamps (seconds). A column name for a CSV with a header
            row, or a positional index (0-based) for a header-less CSV.
        event_type_column : str, int, or None
            The column, if any, that names the type of each event. Pass a column name or index when the
            file holds several event types told apart by that column: each distinct value becomes its
            own event type (and, by default, its own ``EventsTable``). Pass None when the file is a
            single event type, in which case it is written as one table named after the file stem.
        value_columns : list of (str or int), optional
            The columns, if any, carried along as per-event values. Each becomes a value column on the
            event table(s), named after its source header and carrying the raw cell values. Default None
            ignores every column except the timestamp, event-type, and duration columns.
        durations_column : str, int, or None, optional
            The column, if any, holding per-event durations (seconds). When set, the events are durative
            and each duration is written to the table's ``duration`` column; a blank cell becomes
            ``NaN``. Default None writes point (timestamp-only) events.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata.
            If None (default), ``"csv_events"`` is used.
        read_kwargs : dict, optional
            Additional keyword arguments forwarded to ``pandas.read_csv``, used to handle format
            quirks such as ``sep``, ``encoding``, ``decimal``, or ``skiprows``. Any value given here
            overrides the interface's own defaults (``header``, ``float_precision``, and
            ``keep_default_na=False`` -- the latter keeps label tokens such as ``'None'``, ``'NA'``,
            or ``'null'`` from collapsing into a single missing label). Default is None.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            file_path=file_path,
            timestamps_column=timestamps_column,
            event_type_column=event_type_column,
            value_columns=value_columns,
            durations_column=durations_column,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "csv_events"
        self._read_kwargs = read_kwargs or dict()

        # Each column may fill only one role; a column given for two roles is a construction mistake.
        roles = [
            timestamps_column,
            event_type_column,
            durations_column,
            *(value_columns or []),
        ]
        roles = [role for role in roles if role is not None]
        assert len(roles) == len(
            set(roles)
        ), f"Each column may fill only one role, but the same column was assigned more than once: {roles}."

    def _read_source(
        self,
    ) -> tuple[np.ndarray, np.ndarray | None, dict[str, np.ndarray], np.ndarray | None]:
        """Read the timestamps and every role column configured on this interface.

        Returns ``(timestamps, labels, values, durations)``: the event onset times, the per-event
        event-type labels (``None`` when ``event_type_column`` is not set), a dict of per-event value
        arrays keyed by ``value_columns`` (empty when none are set), and the per-event durations
        (``None`` when ``durations_column`` is not set). Rows whose timestamp is missing (``NaN``) are
        dropped, and the label / value / duration arrays are filtered in lockstep so every returned
        array stays row-aligned.
        """
        timestamps_column = self.source_data["timestamps_column"]
        event_type_column = self.source_data["event_type_column"]
        durations_column = self.source_data["durations_column"]
        value_columns = self.source_data["value_columns"] or []
        # An int column specifier means a header-less file (positional columns); a str means a header row.
        header = None if isinstance(timestamps_column, int) else 0
        # float_precision="round_trip" uses an exact, platform-independent float parser; pandas's
        # default C parser rounds the final ULP differently across platforms (Linux/Windows vs macOS).
        # keep_default_na=False reads label tokens ('None', 'NA', 'null', a blank cell, ...) literally
        # instead of collapsing them all into a single NaN label. Caller-supplied read_kwargs override
        # these defaults.
        read_kwargs = {
            "header": header,
            "float_precision": "round_trip",
            "keep_default_na": False,
            **self._read_kwargs,
        }
        dataframe = pd.read_csv(self.source_data["file_path"], **read_kwargs)
        # Coerce the numeric columns directly: keep_default_na=False leaves a blank cell as the literal
        # '', so recover the missing values here (blank or non-numeric -> NaN) independent of the na
        # settings the label / value columns rely on.
        timestamps = pd.to_numeric(dataframe[timestamps_column], errors="coerce").to_numpy(dtype="float64")
        labels = None if event_type_column is None else dataframe[event_type_column].to_numpy()
        durations = (
            pd.to_numeric(dataframe[durations_column], errors="coerce").to_numpy(dtype="float64")
            if durations_column is not None
            else None
        )
        values = {column: dataframe[column].to_numpy() for column in value_columns}

        # Drop rows with a missing timestamp, keeping every other role column aligned.
        valid = ~np.isnan(timestamps)
        number_dropped = int((~valid).sum())
        if number_dropped > 0:
            file_path = self.source_data["file_path"]
            warnings.warn(
                f"Dropped {number_dropped} row(s) with a missing timestamp from '{file_path}'.",
                UserWarning,
                stacklevel=2,
            )
        timestamps = timestamps[valid]
        if labels is not None:
            labels = labels[valid]
        if durations is not None:
            durations = durations[valid]
        values = {column: array[valid] for column, array in values.items()}
        return timestamps, labels, values, durations

    def _value_columns_metadata(self) -> dict:
        """Build the shared ``columns`` block (one entry per ``value_columns`` column) seeded on every
        event type, each declaring its ``column_name`` (the source header)."""
        columns = {}
        for column in self.source_data["value_columns"] or []:
            column_source_id = str(column)
            columns[column_source_id] = {"column_name": column_source_id}
        return columns

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the CSVEventsInterface.

        ``NWBFile/session_start_time`` is intentionally left unset: CSV recordings carry no embedded
        recording-start timestamp, so it must be supplied by the user via editable metadata.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()

        timestamps, labels, _, _ = self._read_source()
        columns = self._value_columns_metadata()
        event_types = metadata["Events"][self.metadata_key]["event_types"]

        # Declare the structure the CSV carries: which event types exist, their source-derived names,
        # and any value columns' names.
        if labels is None:
            # A single event type named after the file stem; skip an empty file so no phantom type is seeded.
            if len(timestamps) > 0:
                file_stem = Path(self.source_data["file_path"]).stem
                entry = {"event_name": file_stem}
                if columns:
                    entry["columns"] = deepcopy(columns)
                event_types[file_stem] = entry
        else:
            # One event type per distinct label value (first-appearance order); the value seeds the
            # editable event_name and, by default, its own table.
            for value in pd.unique(labels):
                event_type_source_id = str(value)
                entry = {"event_name": event_type_source_id}
                if columns:
                    entry["columns"] = deepcopy(columns)
                event_types[event_type_source_id] = entry
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation from the CSV rows, cached after the first call.

        A single-type file (no ``event_type_column``) yields one :class:`_EventsData` keyed by the file
        stem. A labeled file yields one record per distinct label value, each carrying that value's rows.
        ``value_columns`` become the payload field-map and ``durations_column`` the per-event durations;
        an event type that drops to zero rows is skipped (the record forbids empty timestamps).
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        timestamps, labels, values, durations = self._read_source()
        value_columns = self.source_data["value_columns"] or []

        events_data_dict = {}
        if labels is None:
            if len(timestamps) > 0:
                file_stem = Path(self.source_data["file_path"]).stem
                payload = {str(column): values[column] for column in value_columns}
                events_data_dict[file_stem] = _EventsData(
                    event_type_source_id=file_stem,
                    timestamps=timestamps,
                    durations=durations,
                    payload=payload,
                )
        else:
            for value in pd.unique(labels):
                event_type_source_id = str(value)
                mask = labels == value
                if not mask.any():
                    continue
                payload = {str(column): values[column][mask] for column in value_columns}
                events_data_dict[event_type_source_id] = _EventsData(
                    event_type_source_id=event_type_source_id,
                    timestamps=timestamps[mask],
                    durations=durations[mask] if durations is not None else None,
                    payload=payload,
                )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
