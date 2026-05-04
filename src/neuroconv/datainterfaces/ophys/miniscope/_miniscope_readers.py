"""Private V4-only Miniscope format readers used by the Miniscope interfaces.

These helpers replace the format-parsing functions previously imported from
``ndx_miniscope.utils``. ndx-miniscope remains neuroconv's source for NWB
constructors (``Miniscope`` type, ``add_miniscope_device``,
``add_miniscope_image_series``) but no longer for raw-file parsing.

V3 Miniscope support (``settings_and_notes.dat``, ``timestamp.dat``) is not
covered here; the current neuroconv test fixtures are V4-only.
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ....tools import get_package


def _raise_if_miniscope_v3_format(folder_path: str) -> None:
    """Raise a ``NotImplementedError`` if ``folder_path`` contains legacy V3 Miniscope files.

    V3 data is produced by the legacy Miniscope-DAQ-Software (C#/Windows, pre-2020)
    and uses ``settings_and_notes.dat`` + ``timestamp.dat``. The modern QT DAQ
    software (V4, December 2019 onward) uses ``metaData.json`` + ``timeStamps.csv``
    and is the only layout neuroconv currently supports.

    If a user shows up with V3 data, we want a clear error that points them at
    the issue tracker rather than a confusing downstream parse failure.
    """
    folder = Path(folder_path)
    v3_markers = list(folder.rglob("settings_and_notes.dat")) + list(folder.rglob("timestamp.dat"))
    if v3_markers:
        raise NotImplementedError(
            "This folder looks like a legacy Miniscope V3 recording "
            f"(found {v3_markers[0].name} under {folder}). "
            "neuroconv only supports the V4 format produced by the Miniscope-DAQ-QT-Software "
            "(metaData.json + timeStamps.csv). "
            "If you would like V3 support added, please open an issue at "
            "https://github.com/catalystneuro/neuroconv/issues and, if possible, share a "
            "small sample recording so we can add it with proper test coverage."
        )


def _read_miniscope_config(folder_path: str) -> dict:
    """Read a Miniscope V4 ``metaData.json`` into a device metadata dict.

    The ``deviceName`` field (with spaces stripped) becomes ``name``.
    ``deviceDirectory`` and ``deviceID`` are discarded.
    """
    file_path = Path(folder_path) / "metaData.json"
    with open(file_path, encoding="utf-8") as f:
        miniscope_config = json.load(f)
    assert "deviceName" in miniscope_config, "'deviceName' field is missing from the configuration file."
    device_name = miniscope_config.pop("deviceName").replace(" ", "")
    miniscope_config["name"] = device_name
    miniscope_config.pop("deviceDirectory", None)
    miniscope_config.pop("deviceID", None)
    return miniscope_config


def _get_recording_start_times(folder_path: str) -> list[datetime]:
    """Return the start times of each recording subfolder under ``folder_path``.

    Thin wrapper over
    ``roiextractors.extractors.miniscopeimagingextractor.miniscope_utils.get_recording_start_times_for_multi_recordings``,
    which converts ``msec`` to microseconds correctly.
    """
    from roiextractors.extractors.miniscopeimagingextractor.miniscope_utils import (
        get_recording_start_times_for_multi_recordings,
    )

    return get_recording_start_times_for_multi_recordings(folder_path=folder_path)


def _get_fused_timestamps(folder_path: str, file_pattern: str) -> np.ndarray:
    """Concatenate ``timeStamps.csv`` rows across subfolders into one array.

    Each chunk is shifted so that chunk ``i`` starts at
    ``recording_start_times[i] - recording_start_times[0]``, producing a
    continuous timeline across back-to-back recordings.

    ``file_pattern`` is matched with ``rglob`` under ``folder_path``.
    """
    natsort = get_package(package_name="natsort", installation_instructions="pip install natsort")

    timestamps_file_paths = natsort.natsorted(list(Path(folder_path).rglob(file_pattern)))
    assert timestamps_file_paths, f"The Miniscope timestamps are missing from '{folder_path}'."

    recording_start_times = _get_recording_start_times(folder_path=folder_path)

    timestamps = []
    for file_index, file_path in enumerate(timestamps_file_paths):
        timestamps_per_file = pd.read_csv(file_path)["Time Stamp (ms)"].values.astype(float)
        timestamps_per_file /= 1000
        if timestamps_per_file[0] < 0.0:
            timestamps_per_file += abs(timestamps_per_file[0])

        if recording_start_times:
            offset = (recording_start_times[file_index] - recording_start_times[0]).total_seconds()
            timestamps_per_file += offset

        timestamps.extend(timestamps_per_file)

    return np.array(timestamps)


def _get_starting_frames(folder_path: str, video_file_pattern: str) -> list[int]:
    """Return cumulative starting frame indices for the ``.avi`` files in ``folder_path``.

    The first entry is always ``0``; subsequent entries are the total frame
    counts of all preceding files, so the list can be passed as
    ``starting_frame`` to an NWB ``ImageSeries`` with external files.
    """
    cv2 = get_package(package_name="cv2", installation_instructions="pip install opencv-python-headless")
    natsort = get_package(package_name="natsort", installation_instructions="pip install natsort")

    behavior_video_file_paths = natsort.natsorted(list(Path(folder_path).glob(video_file_pattern)))
    assert behavior_video_file_paths, f"Could not find the video files in '{folder_path}'."

    starting_frames = [0]
    for video_file_path in behavior_video_file_paths[:-1]:
        video_capture = cv2.VideoCapture(str(video_file_path))
        num_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
        starting_frames.append(starting_frames[-1] + num_frames)

    return starting_frames
