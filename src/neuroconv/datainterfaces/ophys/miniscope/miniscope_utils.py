import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from natsort import natsorted
from ndx_miniscope import Miniscope
from pynwb import NWBFile

from neuroconv.datainterfaces.behavior.video.video_utils import VideoCaptureContext
from neuroconv.utils import FolderPathType


def get_recording_start_times(folder_path: FolderPathType) -> List[datetime]:
    folder_path = Path(folder_path)
    miniscope_config_files = natsorted(list(folder_path.glob(f"*/metaData.json")))

    recording_start_times = []
    for config_file in miniscope_config_files:
        with open(config_file, newline="") as f:
            config = json.loads(f.read())

        start_time = config["recordingStartTime"]
        assert "recordingStartTime" in config, "The configuration file should contain 'recordingStartTime'."
        recording_start_times.append(
            datetime(
                year=start_time["year"],
                month=start_time["month"],
                day=start_time["day"],
                hour=start_time["hour"],
                minute=start_time["minute"],
                second=start_time["second"],
                microsecond=start_time["msec"],
            )
        )
    return recording_start_times


def get_starting_frames(folder_path: FolderPathType):
    folder_path = Path(folder_path)
    behav_avi_file_paths = natsorted(list(folder_path.glob("*/BehavCam*/*.avi")))
    starting_frames = [0]
    for video_file in behav_avi_file_paths[:-1]:
        with VideoCaptureContext(file_path=str(video_file)) as video_obj:
            num_frames = video_obj.get_video_frame_count()
            starting_frames.append(starting_frames[-1] + num_frames)

    return starting_frames


def get_timestamps(folder_path: FolderPathType, file_pattern: Optional[str] = "Miniscope/timeStamps.csv") -> np.ndarray:
    folder_path = Path(folder_path)
    timestamps_files = natsorted(list(Path(folder_path).rglob(file_pattern)))
    assert timestamps_files, f"The Miniscope timestamps ('timeSramps.csv') are missing from '{folder_path}'."

    recording_start_times = get_recording_start_times(folder_path=folder_path)
    timestamps = []
    for file_ind, file_path in enumerate(timestamps_files):
        timestamps_per_file = pd.read_csv(file_path)["Time Stamp (ms)"].values.astype(float)
        timestamps_per_file /= 1000
        # shift when the first timestamp is negative
        if timestamps_per_file[0] < 0.0:
            timestamps_per_file += abs(timestamps_per_file[0])

        offset = (recording_start_times[file_ind] - recording_start_times[0]).total_seconds()
        timestamps_per_file += offset
        timestamps.extend(timestamps_per_file)

    return np.array(timestamps)


def add_miniscope_device(nwbfile: NWBFile, metadata: dict) -> NWBFile:
    device_metadata = metadata["Ophys"]["Device"][0]

    device_name = device_metadata["name"]
    if device_name not in nwbfile.devices:
        device = Miniscope(**device_metadata)
        nwbfile.add_device(device)

    return nwbfile
