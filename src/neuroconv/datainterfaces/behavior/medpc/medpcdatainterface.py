import numpy as np
import pandas as pd
from hdmf.backends.hdf5.h5_utils import H5DataIO
from ndx_events import Events
from pynwb.behavior import BehavioralEpochs, IntervalSeries
from pynwb.file import NWBFile

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools import nwb_helpers
from neuroconv.utils import DeepDict

from .medpc_helpers import read_medpc_file


class MedPCInterface(BaseDataInterface):
    """Data Interface for MedPC output files"""

    keywords = ["behavior"]

    def __init__(
        self,
        file_path: str,
        session_conditions: dict,
        start_variable: str,
        metadata_medpc_name_to_info_dict: dict,
        verbose: bool = True,
    ):
        """Initialize MedpcInterface.

        Parameters
        ----------
        file_path : str
            Path to the MedPC file.
        session_conditions : dict
            The conditions that define the session. The keys are the names of the single-line variables (ex. 'Start Date')
            and the values are the values of those variables for the desired session (ex. '11/09/18').
        start_variable : str
            The name of the variable that starts the session (ex. 'Start Date').
        metadata_medpc_name_to_info_dict : dict
            A dictionary mapping the names of the desired variables in the MedPC file
            to an info dictionary with the names of the variables in the metadata and their types.
            ex. {"Start Date": {"name": "start_date", "type": "date"}}
        verbose : bool, optional
            Whether to print verbose output, by default True
        """
        super().__init__(
            file_path=file_path,
            session_conditions=session_conditions,
            start_variable=start_variable,
            metadata_medpc_name_to_info_dict=metadata_medpc_name_to_info_dict,
            verbose=verbose,
        )

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

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict) -> None:
        medpc_name_to_info_dict = metadata["MedPC"]["medpc_name_to_info_dict"]
        session_dict = read_medpc_file(
            file_path=self.source_data["file_path"],
            medpc_name_to_info_dict=medpc_name_to_info_dict,
            session_conditions=self.source_data["session_conditions"],
            start_variable=self.source_data["start_variable"],
        )

        # Add behavior data to nwbfile
        behavior_module = nwb_helpers.get_module(
            nwbfile=nwbfile,
            name="behavior",
            description="Operant behavioral data from MedPC.",
        )

        for event_dict in metadata["MedPC"]["Events"]:
            name = event_dict["name"]
            description = event_dict["description"]
            event_data = session_dict[name]
            if len(event_data) > 0:
                event = Events(
                    name=name,
                    description=description,
                    timestamps=H5DataIO(event_data, compression=True),
                )
                behavior_module.add(event)
        for interval_dict in metadata["MedPC"]["IntervalSeries"]:
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
                timestamps=H5DataIO(interval_times, compression=True),
                data=H5DataIO(data, compression=True),
            )
            behavioral_epochs = BehavioralEpochs(name="behavioral_epochs")
            behavioral_epochs.add_interval_series(interval)
            behavior_module.add(behavioral_epochs)
