import warnings
from datetime import datetime, timezone

import numpy as np
from pydantic import DirectoryPath, validate_call
from pynwb.file import NWBFile

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools import get_package, nwb_helpers
from neuroconv.utils import DeepDict

from ...ophys.tdt_fp._tdt_mixin import TDTLoadMixin


class TDTEventsInterface(TDTLoadMixin, BaseDataInterface):
    """Data Interface for converting discrete events (epocs) from a TDT output folder.

    The TDT tank stores discrete events as epocs (e.g. camera TTL pulses, port entries, nose pokes).
    This interface reads those epocs via ``tdt.read_block`` and writes each selected epoc as an
    ``ndx_events.Events`` object (onset timestamps only) into a behavior ProcessingModule.
    """

    keywords = ("behavior", "events", "TDT")
    display_name = "TDTEvents"
    info = "Data Interface for converting discrete events (epocs) from TDT files."
    associated_suffixes = ("Tbk", "Tdx", "tev", "tin", "tsq")

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        event_names: list[str] | None = None,
        verbose: bool = False,
    ):
        """Initialize the TDTEventsInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder containing the TDT data.
        event_names : list[str], optional
            The names of the TDT epocs to store as events. If None (default), every epoc in the
            tank is stored.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "event_names",
                "verbose",
            ]
            num_positional_args_before_args = 1  # folder_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to TDTEventsInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            event_names = positional_values.get("event_names", event_names)
            verbose = positional_values.get("verbose", verbose)

        super().__init__(
            folder_path=folder_path,
            event_names=event_names,
            verbose=verbose,
        )
        # This import is to assure that ndx_events is in the global namespace when a pynwb.io object is created
        import ndx_events  # noqa: F401

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the TDTEventsInterface.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        tdt_photometry = self.load(evtype=["scalars"])  # This evtype quickly loads info without loading all the data.
        start_timestamp = tdt_photometry.info.start_date.timestamp()
        session_start_datetime = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
        metadata["NWBFile"]["session_start_time"] = session_start_datetime.isoformat()

        event_names = self.source_data["event_names"]
        if event_names is None:
            event_names = list(self.load(evtype=["epocs"]).epocs.keys())
        metadata["Behavior"]["TDTEvents"]["Events"] = [
            {
                "epoc_name": epoc_name,
                "name": epoc_name,
                "description": f"Onset times of the TDT epoc '{epoc_name}'.",
            }
            for epoc_name in event_names
        ]
        return metadata

    def get_metadata_schema(self) -> dict:
        """
        Get the metadata schema for the TDTEventsInterface.

        Returns
        -------
        dict
            The metadata schema for this interface.
        """
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Behavior"] = {
            "type": "object",
            "properties": {
                "TDTEvents": {
                    "type": "object",
                    "properties": {
                        "module_name": {"type": "string"},
                        "module_description": {"type": "string"},
                        "Events": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["epoc_name", "name", "description"],
                                "properties": {
                                    "epoc_name": {"type": "string"},
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
        """Add the selected TDT epocs to the NWBFile as ``ndx_events.Events`` objects.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the events to.
        metadata : dict
            Metadata dictionary. Each entry in ``metadata["Behavior"]["TDTEvents"]["Events"]`` maps a
            TDT epoc (``epoc_name``) to an ``Events`` object's ``name`` and ``description``.
        """
        ndx_events = get_package(package_name="ndx_events", installation_instructions="pip install ndx-events==0.2.2")

        events_metadata = metadata["Behavior"]["TDTEvents"]["Events"]
        event_object_names = [event_dict["name"] for event_dict in events_metadata]
        assert len(event_object_names) == len(set(event_object_names)), (
            f"Duplicate Events 'name' values found in metadata: {event_object_names}. "
            "Each Events object must have a unique name."
        )

        module_name = metadata["Behavior"]["TDTEvents"].get("module_name", "behavior")
        module_description = metadata["Behavior"]["TDTEvents"].get(
            "module_description", "Discrete events extracted from TDT epocs."
        )
        behavior_module = nwb_helpers.get_module(
            nwbfile=nwbfile,
            name=module_name,
            description=module_description,
        )

        tdt_photometry = self.load(evtype=["epocs"])
        available_epocs = list(tdt_photometry.epocs.keys())
        for event_dict in events_metadata:
            epoc_name = event_dict["epoc_name"]
            assert (
                epoc_name in available_epocs
            ), f"Epoc '{epoc_name}' not found in the TDT tank. Available epocs: {available_epocs}."
            onset = np.asarray(tdt_photometry.epocs[epoc_name].onset)
            if len(onset) == 0:
                continue
            events = ndx_events.Events(
                name=event_dict["name"],
                description=event_dict["description"],
                timestamps=onset,
            )
            behavior_module.add(events)
