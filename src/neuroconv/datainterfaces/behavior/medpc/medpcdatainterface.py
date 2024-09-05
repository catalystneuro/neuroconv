from typing import Optional

import numpy as np
from pydantic import FilePath, validate_call
from pynwb.behavior import BehavioralEpochs, IntervalSeries
from pynwb.file import NWBFile

from neuroconv.basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from neuroconv.tools import get_package, nwb_helpers
from neuroconv.utils import DeepDict

from .medpc_helpers import read_medpc_file


class MedPCInterface(BaseTemporalAlignmentInterface):
    """
    Data Interface for MedPC output files.

    The output files from MedPC are raw text files that contain behavioral data from the operant box sessions such as
    lever presses, reward port entries, nose pokes, etc. The output text files format this data into a series of
    colon-separated variables that are either single-line (for metadata) or multi-line (for arrays). The multi-line
    variables keep a colon-separated index of the array every 5 elements.  For example, a single variable might look like::

        Start Date: 11/09/18

    while a multi-line variable might look like::

        A:
            0:      175.150      270.750      762.050      762.900     1042.600
            5:     1567.800     1774.950     2448.450     2454.050     2552.800
            10:     2620.550     2726.250

    Different sessions are usually separated by a blank line or two.

    This data is parsed by the MedPCInterface and added to the NWBFile as Events and IntervalSeries objects in the
    behavior module.
    """

    keywords = ("behavior",)
    display_name = "MedPC"
    info = "Interface for handling MedPC output files."
    associated_suffixes = (".txt",)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        session_conditions: dict,
        start_variable: str,
        metadata_medpc_name_to_info_dict: dict,
        aligned_timestamp_names: Optional[list[str]] = None,
        verbose: bool = True,
    ):
        """
        Initialize MedpcInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the MedPC file.
        session_conditions : dict
            The conditions that define the session. The keys are the names of the single-line variables (ex. 'Start Date')
            and the values are the values of those variables for the desired session (ex. '11/09/18').
        start_variable : str
            The name of the variable that starts the session (ex. 'Start Date').
        metadata_medpc_name_to_info_dict : dict
            A dictionary mapping the names of the desired variables in the MedPC file
            to an info dictionary with the names of the variables in the metadata and whether or not they are arrays.
            ex. {"Start Date": {"name": "start_date", "is_array": False}}
        aligned_timestamp_names : list, optional
            The names of the variables that are externally aligned timestamps,
            which should be retrieved from self.timestamps_dict instead of the MedPC output file.
        verbose : bool, optional
            Whether to print verbose output, by default True
        """
        if aligned_timestamp_names is None:
            aligned_timestamp_names = []
        super().__init__(
            file_path=file_path,
            session_conditions=session_conditions,
            start_variable=start_variable,
            metadata_medpc_name_to_info_dict=metadata_medpc_name_to_info_dict,
            aligned_timestamp_names=aligned_timestamp_names,
            verbose=verbose,
        )
        self.timestamps_dict = {}

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        session_dict = read_medpc_file(
            file_path=self.source_data["file_path"],
            medpc_name_to_info_dict=self.source_data["metadata_medpc_name_to_info_dict"],
            session_conditions=self.source_data["session_conditions"],
            start_variable=self.source_data["start_variable"],
        )
        for k, v in session_dict.items():
            metadata["MedPC"][k] = v

        return metadata

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        medpc_name_to_info_dict = self.source_data["metadata_medpc_name_to_info_dict"]
        metadata_schema["properties"]["MedPC"] = {
            "type": "object",
            "properties": {info_dict["name"]: {"type": "string"} for info_dict in medpc_name_to_info_dict.values()},
        }
        return metadata_schema

    def get_original_timestamps(self, medpc_name_to_info_dict: dict) -> dict[str, np.ndarray]:
        """
        Retrieve the original unaltered timestamps dictionary for the data in this interface.

        This function retrieves the data on-demand by re-reading the medpc file.

        Parameters
        ----------
        medpc_name_to_info_dict : dict
            A dictionary mapping the names of the desired variables in the MedPC file
            to an info dictionary with the names of the variables in the metadata and whether or not they are arrays.
            ex. {"A": {"name": "left_nose_poke_times", "is_array": True}}

        Returns
        -------
        timestamps_dict: dict
            A dictionary mapping the names of the variables to the original medpc timestamps.
        """
        timestamps_dict = read_medpc_file(
            file_path=self.source_data["file_path"],
            medpc_name_to_info_dict=medpc_name_to_info_dict,
            session_conditions=self.source_data["session_conditions"],
            start_variable=self.source_data["start_variable"],
        )
        return timestamps_dict

    def get_timestamps(self) -> dict[str, np.ndarray]:
        """
        Retrieve the timestamps dictionary for the data in this interface.

        Returns
        -------
        timestamps_dict: dict
            A dictionary mapping the names of the variables to the timestamps.
        """
        return self.timestamps_dict

    def set_aligned_timestamps(self, aligned_timestamps_dict: dict[str, np.ndarray]) -> None:
        """
        Replace all timestamps for this interface with those aligned to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_timestamps_dict : dict
            A dictionary mapping the names of the variables to the synchronized timestamps for data in this interface.
        """
        self.timestamps_dict = aligned_timestamps_dict

    def set_aligned_starting_time(self, aligned_starting_time: float, medpc_name_to_info_dict: dict) -> None:
        """
        Align the starting time for this interface relative to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_starting_time : float
            The starting time for all temporal data in this interface.
        medpc_name_to_info_dict : dict
            A dictionary mapping the names of the desired variables in the MedPC file
            to an info dictionary with the names of the variables in the metadata and whether or not they are arrays.
            ex. {"A": {"name": "left_nose_poke_times", "is_array": True}}
        """
        original_timestamps_dict = self.get_original_timestamps(medpc_name_to_info_dict=medpc_name_to_info_dict)
        aligned_timestamps_dict = {}
        for name, original_timestamps in original_timestamps_dict.items():
            aligned_timestamps_dict[name] = original_timestamps + aligned_starting_time
        self.set_aligned_timestamps(aligned_timestamps_dict=aligned_timestamps_dict)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
    ) -> None:
        ndx_events = get_package(package_name="ndx_events", installation_instructions="pip install ndx-events")
        medpc_name_to_info_dict = metadata["MedPC"].get("medpc_name_to_info_dict", None)
        assert medpc_name_to_info_dict is not None, "medpc_name_to_info_dict must be provided in metadata"
        info_name_to_medpc_name = {
            info_dict["name"]: medpc_name for medpc_name, info_dict in medpc_name_to_info_dict.items()
        }
        for name in self.source_data["aligned_timestamp_names"]:
            medpc_name = info_name_to_medpc_name[name]
            medpc_name_to_info_dict.pop(medpc_name)
        session_dict = read_medpc_file(
            file_path=self.source_data["file_path"],
            medpc_name_to_info_dict=medpc_name_to_info_dict,
            session_conditions=self.source_data["session_conditions"],
            start_variable=self.source_data["start_variable"],
        )
        aligned_timestamps_dict = self.get_timestamps()
        for name, aligned_timestamps in aligned_timestamps_dict.items():
            session_dict[name] = aligned_timestamps

        # Add behavior data to nwbfile
        module_name = metadata["MedPC"].get("module_name", "behavior")
        module_description = metadata["MedPC"].get("module_description", "Behavioral data from MedPC output files.")
        behavior_module = nwb_helpers.get_module(
            nwbfile=nwbfile,
            name=module_name,
            description=module_description,
        )

        event_dicts = metadata["MedPC"].get("Events", [])
        for event_dict in event_dicts:
            name = event_dict["name"]
            description = event_dict["description"]
            event_data = session_dict[name]
            if len(event_data) > 0:
                event = ndx_events.Events(
                    name=name,
                    description=description,
                    timestamps=event_data,
                )
                behavior_module.add(event)
        interval_dicts = metadata["MedPC"].get("IntervalSeries", [])
        for interval_dict in interval_dicts:
            name = interval_dict["name"]
            description = interval_dict["description"]
            onset_name = interval_dict["onset_name"]
            duration_name = interval_dict["duration_name"]
            onset_data = session_dict[onset_name]
            duration_data = session_dict[duration_name]
            if len(onset_data) == 0:
                continue
            assert not len(duration_data) == 0, f"Duration data for {name} is empty!"

            interval_times, data = [], []
            for onset_time, duration in zip(onset_data, duration_data):
                interval_times.append(onset_time)
                data.append(1)
                interval_times.append(onset_time + duration)
                data.append(-1)
            interval = IntervalSeries(
                name=name,
                description=description,
                timestamps=interval_times,
                data=data,
            )
            behavioral_epochs = BehavioralEpochs(name="behavioral_epochs")
            behavioral_epochs.add_interval_series(interval)
            behavior_module.add(behavioral_epochs)
