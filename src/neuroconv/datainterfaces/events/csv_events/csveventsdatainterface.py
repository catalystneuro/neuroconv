from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import DirectoryPath, validate_call
from pynwb.file import NWBFile

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools import get_package
from neuroconv.utils import DeepDict


class CSVEventsInterface(BaseDataInterface):
    """Data Interface for converting discrete events (TTLs) from CSV files.

    This CSV format is a raw acquisition format, with one CSV per event stream. Each event CSV has a
    single ``timestamps`` column holding the onset times (seconds) of a discrete event (e.g. a TTL
    pulse train), and is named after its stream (``<event_name>.csv``). This interface reads those
    event CSVs and writes each as an ``ndx_events.Events`` object (onset timestamps only) into
    ``nwbfile.acquisition``. Acquisition is used because these CSV streams are raw acquired markers
    (TTLs, sync pulses) whose interpretation is not necessarily behavioral.

    Notes
    -----
    CSV recordings carry no embedded recording-start timestamp, so :meth:`get_metadata` does NOT
    populate ``NWBFile/session_start_time``. The user must supply it via editable metadata.
    """

    keywords = ("events", "CSV")
    display_name = "CSVEvents"
    info = "Data Interface for converting discrete events (TTLs) from CSV files."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        exclude_events: list[str] | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the CSVEventsInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder containing the per-stream event CSV files.
        exclude_events : list[str], optional
            The names (file stems) of the event CSVs to skip. If None (default), every single-column
            event CSV in the folder is stored.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata.
            If None (default), ``"csv_events"`` is used.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            folder_path=folder_path,
            exclude_events=exclude_events,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "csv_events"
        # This import is to assure that ndx_events is in the global namespace when a pynwb.io object is created
        import ndx_events  # noqa: F401

    def _event_csv_path(self, event_name: str) -> Path:
        """Get the path to the CSV file backing the given event."""
        return Path(self.source_data["folder_path"]) / f"{event_name}.csv"

    def _get_event_names(self) -> list[str]:
        """Get the names (file stems) of the event CSVs (single ``timestamps`` column) in the folder.

        Data CSVs (with a ``data`` column, e.g. fiber photometry signal/control streams) are
        excluded -- those belong to a separate fiber photometry interface.
        """
        event_names = []
        for path in sorted(Path(self.source_data["folder_path"]).glob("*.csv")):
            columns = [column.lower() for column in pd.read_csv(path, nrows=0).columns]
            if columns == ["timestamps"]:
                event_names.append(path.stem)
        return event_names

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

        exclude_events = self.source_data["exclude_events"] or []
        included_events = [event_name for event_name in self._get_event_names() if event_name not in exclude_events]
        for event_name in included_events:
            metadata["Events"][self.metadata_key]["event_columns"][event_name] = {
                "column_name": event_name,
                "description": f"Onset times of the '{event_name}' events from CSV.",
            }
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
                        "additionalProperties": {  # keyed by event CSV file stem (event_type_id)
                            "type": "object",
                            "required": ["column_name", "description"],
                            "properties": {
                                "column_name": {"type": "string"},
                                "description": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
        return metadata_schema

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict) -> None:
        """Add the selected event CSVs to the NWBFile as ``ndx_events.Events`` objects.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the events to.
        metadata : dict
            Metadata dictionary. Each entry in ``metadata["Events"][metadata_key]["event_columns"]``
            is keyed by the event CSV file stem (``event_type_id``) and holds the output ``Events``
            object's ``column_name`` and ``description``.
        """
        ndx_events = get_package(package_name="ndx_events", installation_instructions="pip install ndx-events==0.2.2")

        event_columns = metadata["Events"][self.metadata_key]["event_columns"]
        event_object_names = [column["column_name"] for column in event_columns.values()]
        assert len(event_object_names) == len(set(event_object_names)), (
            f"Duplicate Events 'column_name' values found in metadata: {event_object_names}. "
            "Each Events object must have a unique name."
        )

        for file_name, column in event_columns.items():
            # float_precision="round_trip" uses an exact, platform-independent float parser; pandas's
            # default C parser rounds the final ULP differently across platforms (Linux/Windows vs macOS).
            timestamps = pd.read_csv(self._event_csv_path(file_name), float_precision="round_trip")[
                "timestamps"
            ].to_numpy()
            if len(timestamps) == 0:
                continue
            events = ndx_events.Events(
                name=column["column_name"],
                description=column["description"],
                timestamps=np.asarray(timestamps),
            )
            nwbfile.add_acquisition(events)
