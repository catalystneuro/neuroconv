from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import DirectoryPath, validate_call
from pynwb.file import NWBFile

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools import get_package, nwb_helpers
from neuroconv.utils import DeepDict


class CSVEventsInterface(BaseDataInterface):
    """Data Interface for converting discrete events (TTLs) from CSV files.

    This CSV format is a raw acquisition format, with one CSV per event stream. Each event CSV has a
    single ``timestamps`` column holding the onset times (seconds) of a discrete event (e.g. a TTL
    pulse train), and is named after its stream (``<event_name>.csv``). This interface reads those
    event CSVs and writes each as an ``ndx_events.Events`` object (onset timestamps only) into a
    behavior ProcessingModule.

    Notes
    -----
    CSV recordings carry no embedded recording-start timestamp, so :meth:`get_metadata` does NOT
    populate ``NWBFile/session_start_time``. The user must supply it via editable metadata.
    """

    keywords = ("behavior", "events", "CSV")
    display_name = "CSVEvents"
    info = "Data Interface for converting discrete events (TTLs) from CSV files."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        event_names: list[str] | None = None,
        verbose: bool = False,
    ):
        """Initialize the CSVEventsInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder containing the per-stream event CSV files.
        event_names : list[str], optional
            The names of the event CSVs (file stems) to store as events. If None (default), every
            single-column event CSV in the folder is stored.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            folder_path=folder_path,
            event_names=event_names,
            verbose=verbose,
        )
        # This import is to assure that ndx_events is in the global namespace when a pynwb.io object is created
        import ndx_events  # noqa: F401

    def _event_csv_path(self, event_name: str) -> Path:
        """Get the path to the CSV file backing the given event."""
        return Path(self.source_data["folder_path"]) / f"{event_name}.csv"

    def _get_event_names(self) -> list[str]:
        """Get the names of the event CSVs (single ``timestamps`` column) in the folder.

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

        event_names = self.source_data["event_names"]
        if event_names is None:
            event_names = self._get_event_names()
        metadata["Behavior"]["CSVEvents"]["Events"] = [
            {
                "file_name": event_name,
                "name": event_name,
                "description": f"Onset times of the '{event_name}' events from CSV.",
            }
            for event_name in event_names
        ]
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
        metadata_schema["properties"]["Behavior"] = {
            "type": "object",
            "properties": {
                "CSVEvents": {
                    "type": "object",
                    "properties": {
                        "module_name": {"type": "string"},
                        "module_description": {"type": "string"},
                        "Events": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["file_name", "name", "description"],
                                "properties": {
                                    "file_name": {"type": "string"},
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                },
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
            Metadata dictionary. Each entry in ``metadata["Behavior"]["CSVEvents"]["Events"]`` maps an
            event CSV (``file_name``) to an ``Events`` object's ``name`` and ``description``.
        """
        ndx_events = get_package(package_name="ndx_events", installation_instructions="pip install ndx-events==0.2.2")

        events_metadata = metadata["Behavior"]["CSVEvents"]["Events"]
        event_object_names = [event_dict["name"] for event_dict in events_metadata]
        assert len(event_object_names) == len(set(event_object_names)), (
            f"Duplicate Events 'name' values found in metadata: {event_object_names}. "
            "Each Events object must have a unique name."
        )

        module_name = metadata["Behavior"]["CSVEvents"].get("module_name", "behavior")
        module_description = metadata["Behavior"]["CSVEvents"].get(
            "module_description", "Discrete events extracted from CSV."
        )
        behavior_module = nwb_helpers.get_module(
            nwbfile=nwbfile,
            name=module_name,
            description=module_description,
        )

        for event_dict in events_metadata:
            file_name = event_dict["file_name"]
            timestamps = pd.read_csv(self._event_csv_path(file_name))["timestamps"].to_numpy()
            if len(timestamps) == 0:
                continue
            events = ndx_events.Events(
                name=event_dict["name"],
                description=event_dict["description"],
                timestamps=np.asarray(timestamps),
            )
            behavior_module.add(events)
