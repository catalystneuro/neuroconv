from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools import get_package
from neuroconv.utils import DeepDict


class CSVEventsInterface(BaseDataInterface):
    """Data Interface for converting discrete events from a single CSV file.

    This is a general-purpose CSV events reader: the caller points at one CSV file and names the
    column holding the event timestamps (``timestamps_column``) and, optionally, the column that
    tells the event types apart (``event_type_column``).

    Two layouts are supported:

    - **A single event type** (``event_type_column=None``): every row is one occurrence of the same
      event, and the file becomes one ``ndx_events.Events`` object named
      after the file stem.
    - **Several event types in one file** (``event_type_column`` set): each row carries a label in
      that column, and the file becomes one ``ndx_events.LabeledEvents`` object named after the file
      stem -- the timestamps plus a per-event integer code into the label vocabulary. This
      mirrors how ``TDTEventsInterface`` writes a labeled (strobe) store.

    Columns other than ``timestamps_column`` and ``event_type_column`` are ignored; only timestamps
    (and, for the labeled case, the event labels) are written.

    Notes
    -----
    CSV recordings carry no embedded recording-start timestamp, so :meth:`get_metadata` does NOT
    populate ``NWBFile/session_start_time``. The user must supply it via editable metadata.
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
            The column, if any, that names the type of each event. Pass a column name or index when
            the file holds several event types told apart by that column, so that the file is written
            as a single ``LabeledEvents`` with one label per distinct value. Pass None when the file
            is a single event type with no such column, in which case the file is written as a plain
            ``Events`` named after the file stem.
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
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "csv_events"
        self._read_kwargs = read_kwargs or dict()
        # This import is to assure that ndx_events is in the global namespace when a pynwb.io object is created
        import ndx_events  # noqa: F401

    def _read_timestamps_and_labels(self) -> tuple[np.ndarray, np.ndarray | None]:
        """Read the timestamps and, when ``event_type_column`` is set, the per-event labels.

        Both arrays are in file order (the labeled case is written as a single ``LabeledEvents``, so
        the rows are not grouped). Returns ``(timestamps, None)`` when there is no event-type column.
        Rows whose timestamp is missing (``NaN``) are dropped, since ``ndx_events`` has no
        representation for a missing timestamp.
        """
        timestamps_column = self.source_data["timestamps_column"]
        event_type_column = self.source_data["event_type_column"]
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
        # Coerce the timestamps column to numbers directly: keep_default_na=False leaves a blank
        # timestamp cell as the literal '', so recover the missing values here (blank or non-numeric
        # -> NaN) independent of the na settings the label column relies on.
        timestamps = pd.to_numeric(dataframe[timestamps_column], errors="coerce").to_numpy(dtype="float64")
        labels = None if event_type_column is None else dataframe[event_type_column].to_numpy()
        # Drop rows with a missing timestamp, keeping the labels aligned.
        valid = ~np.isnan(timestamps)
        timestamps = timestamps[valid]
        if labels is not None:
            labels = labels[valid]
        return timestamps, labels

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

        _, labels = self._read_timestamps_and_labels()
        file_stem = Path(self.source_data["file_path"]).stem
        column = {
            "column_name": file_stem,
            "description": f"Timestamps of the '{file_stem}' events from CSV.",
        }
        if labels is not None:
            event_type_column = self.source_data["event_type_column"]
            column["description"] = (
                f"Timestamps of the '{file_stem}' events from CSV, labeled by the " f"'{event_type_column}' column."
            )
            # A label per distinct value (first-appearance order), seeding LabeledEvents. The map is
            # raw value -> display label; the user can rename the display labels in editable metadata.
            column["column_categories"] = {"labels": {str(value): str(value) for value in pd.unique(labels)}}
        metadata["Events"][self.metadata_key]["event_columns"][file_stem] = column
        return metadata

    def get_metadata_schema(self) -> dict:
        """
        Get the metadata schema for the CSVEventsInterface.

        Returns
        -------
        dict
            The metadata schema for this interface.
        """
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Events"] = {
            "type": "object",
            "additionalProperties": {  # keyed by metadata_key
                "type": "object",
                "properties": {
                    "event_columns": {
                        "type": "object",
                        "additionalProperties": {  # keyed by event-type id (the file stem)
                            "type": "object",
                            "required": ["column_name", "description"],
                            "properties": {
                                "column_name": {"type": "string"},
                                "description": {"type": "string"},
                                # Present only for a labeled file: the column's value vocabulary.
                                "column_categories": {
                                    "type": "object",
                                    "properties": {
                                        # maps each raw label value to a display label
                                        "labels": {"type": "object", "additionalProperties": {"type": "string"}},
                                        "meanings": {"type": "object", "additionalProperties": {"type": "string"}},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }
        return metadata_schema

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict) -> None:
        """Add the events to the NWBFile as an ``ndx_events.Events`` or ``LabeledEvents`` object.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the events to.
        metadata : dict
            Metadata dictionary. The single entry in
            ``metadata["Events"][metadata_key]["event_columns"]`` holds the output object's
            ``column_name`` and ``description``. A ``column_categories["labels"]`` map (raw value ->
            display label) marks the file as labeled and is written as ``LabeledEvents``; its absence
            writes a plain ``Events``.
        """
        ndx_events = get_package(package_name="ndx_events", installation_instructions="pip install ndx-events==0.2.2")

        event_columns = metadata["Events"][self.metadata_key]["event_columns"]
        event_object_names = [column["column_name"] for column in event_columns.values()]
        assert len(event_object_names) == len(set(event_object_names)), (
            f"Duplicate Events 'column_name' values found in metadata: {event_object_names}. "
            "Each Events object must have a unique name."
        )

        timestamps, labels = self._read_timestamps_and_labels()
        for column in event_columns.values():
            if len(timestamps) == 0:
                continue
            if "column_categories" in column:
                # Labeled file -> LabeledEvents. The vocabulary order is the insertion order of the
                # editable labels map seeded by get_metadata (first appearance in the file).
                labels_map = column["column_categories"]["labels"]
                vocabulary = list(labels_map)
                value_to_index = {value: index for index, value in enumerate(vocabulary)}
                data = np.array([value_to_index[str(label)] for label in labels], dtype=np.uint32)
                events = ndx_events.LabeledEvents(
                    name=column["column_name"],
                    description=column["description"],
                    timestamps=np.asarray(timestamps),
                    data=data,
                    labels=[labels_map[value] for value in vocabulary],
                )
            else:
                events = ndx_events.Events(
                    name=column["column_name"],
                    description=column["description"],
                    timestamps=np.asarray(timestamps),
                )
            nwbfile.add_acquisition(events)
