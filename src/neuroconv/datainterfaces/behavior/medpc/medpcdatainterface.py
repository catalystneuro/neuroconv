import numpy as np
import pandas as pd
from hdmf.backends.hdf5.h5_utils import H5DataIO
from ndx_events import Events
from pynwb.behavior import BehavioralEpochs, IntervalSeries
from pynwb.file import NWBFile

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools import nwb_helpers
from neuroconv.utils import DeepDict

from .medpc_utils import read_medpc_file


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
        from_csv = self.source_data["from_csv"]
        if self.source_data["session_dict"] is None and not from_csv:
            msn = metadata["Behavior"]["msn"]
            medpc_name_to_dict_name = metadata["Behavior"]["msn_to_medpc_name_to_dict_name"][msn]
            dict_name_to_type = {dict_name: np.ndarray for dict_name in medpc_name_to_dict_name.values()}
            session_dict = read_medpc_file(
                file_path=self.source_data["file_path"],
                medpc_name_to_dict_name=medpc_name_to_dict_name,
                dict_name_to_type=dict_name_to_type,
                session_conditions=self.source_data["session_conditions"],
                start_variable=self.source_data["start_variable"],
            )
        elif self.source_data["session_dict"] is None and from_csv:
            csv_name_to_dict_name = {
                "portEntryTs": "port_entry_times",
                "DurationOfPE": "duration_of_port_entry",
                "LeftNoseTs": "left_nose_poke_times",
                "RightNoseTs": "right_nose_poke_times",
                "RightRewardTs": "right_reward_times",
                "LeftRewardTs": "left_reward_times",
            }
            session_dtypes = {
                "Start Date": str,
                "End Date": str,
                "Start Time": str,
                "End Time": str,
                "MSN": str,
                "Experiment": str,
                "Subject": str,
                "Box": str,
            }
            session_df = pd.read_csv(self.source_data["file_path"], dtype=session_dtypes)
            session_dict = {}
            for csv_name, dict_name in csv_name_to_dict_name.items():
                session_dict[dict_name] = np.trim_zeros(session_df[csv_name].dropna().values, trim="b")
        else:
            session_dict = self.source_data["session_dict"]

        # Add behavior data to nwbfile
        behavior_module = nwb_helpers.get_module(
            nwbfile=nwbfile,
            name="behavior",
            description=(
                f"Operant behavioral data from MedPC.\n"
                f"Box = {metadata['Behavior']['box']}\n"
                f"MSN = {metadata['Behavior']['msn']}"
            ),
        )

        # Port Entry
        if (
            len(session_dict["duration_of_port_entry"]) == 0
        ):  # some sessions are missing port entry durations ex. FP Experiments/Behavior/PR/028.392/07-09-20
            if self.verbose:
                print(f"No port entry durations found for {metadata['NWBFile']['session_id']}")
            reward_port_entry_times = Events(
                name="reward_port_entry_times",
                description="Reward port entry times",
                timestamps=H5DataIO(session_dict["port_entry_times"], compression=True),
            )
            behavior_module.add(reward_port_entry_times)
        else:
            port_times, data = [], []
            for port_entry_time, duration in zip(
                session_dict["port_entry_times"], session_dict["duration_of_port_entry"]
            ):
                port_times.append(port_entry_time)
                data.append(1)
                port_times.append(port_entry_time + duration)
                data.append(-1)
            reward_port_intervals = IntervalSeries(
                name="reward_port_intervals",
                description="Interval of time spent in reward port (1 is entry, -1 is exit)",
                timestamps=H5DataIO(port_times, compression=True),
                data=data,
            )
            behavioral_epochs = BehavioralEpochs(name="behavioral_epochs")
            behavioral_epochs.add_interval_series(reward_port_intervals)
            behavior_module.add(behavioral_epochs)

        # Left/Right Nose pokes
        left_nose_poke_times = Events(
            name="left_nose_poke_times",
            description="Left nose poke times",
            timestamps=H5DataIO(session_dict["left_nose_poke_times"], compression=True),
        )
        right_nose_poke_times = Events(
            name="right_nose_poke_times",
            description="Right nose poke times",
            timestamps=H5DataIO(session_dict["right_nose_poke_times"], compression=True),
        )
        behavior_module.add(left_nose_poke_times)
        behavior_module.add(right_nose_poke_times)

        # Left/Right Rewards -- Interleaved for most sessions
        if len(session_dict["left_reward_times"]) > 0:
            left_reward_times = Events(
                name="left_reward_times",
                description="Left Reward times",
                timestamps=H5DataIO(session_dict["left_reward_times"], compression=True),
            )
            behavior_module.add(left_reward_times)
        if len(session_dict["right_reward_times"]) > 0:
            right_reward_times = Events(
                name="right_reward_times",
                description="Right Reward times",
                timestamps=H5DataIO(session_dict["right_reward_times"], compression=True),
            )
            behavior_module.add(right_reward_times)

        # Footshock
        if "footshock_times" in session_dict:
            footshock_times = Events(
                name="footshock_times",
                description="Footshock times",
                timestamps=session_dict["footshock_times"],
            )
            behavior_module.add(footshock_times)
