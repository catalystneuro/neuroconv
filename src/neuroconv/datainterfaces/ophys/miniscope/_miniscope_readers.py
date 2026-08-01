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


def _config_to_miniscope_device_metadata(miniscope_config: dict) -> dict:
    """Map a V4 device configuration onto a ``metadata["Devices"]`` entry of type ``Miniscope``.

    ``miniscope_config`` is a config as returned by :func:`_read_miniscope_config` (a device folder's
    ``metaData.json``) or an entry of ``devices[miniscopes]`` in the User Config, plus a ``name``.

    Only the fields the ndx-miniscope schema declares can be set on the device. A setting the DAQ
    recorded that the schema has no field for (``ewl``, the electrowetting lens position, is the one
    every V4 file carries) is named in the description rather than dropped without trace.
    """
    # Fields of the ndx-miniscope ``Miniscope`` type, grouped by the dtype its schema declares. The DAQ
    # writes several of them with a different type than the schema asks for (``gain: 3.5``, ``gain: 16``,
    # ``frameRate: 50`` are all real values), so each is coerced here instead of being passed through.
    text_fields = ("compression", "deviceType", "frameRate", "gain")
    integer_fields = ("excitation", "framesPerFile", "led0", "msCamExposure")
    # Identifiers rather than acquisition settings; they say nothing about the device itself.
    # ``deviceName`` is the device's own name, which the caller passes as ``name``.
    ignored_fields = ("deviceDirectory", "deviceID", "deviceName")

    device_metadata = {"type": "Miniscope", "name": miniscope_config["name"]}

    for field in text_fields:
        if field in miniscope_config:
            device_metadata[field] = str(miniscope_config[field])
    for field in integer_fields:
        if field in miniscope_config:
            device_metadata[field] = int(miniscope_config[field])

    mapped_fields = {"name", "ROI", *text_fields, *integer_fields, *ignored_fields}
    unmapped_settings = {key: value for key, value in miniscope_config.items() if key not in mapped_fields}

    region_of_interest = miniscope_config.get("ROI")
    if region_of_interest is not None:
        # The schema types ROI as the (height, width) of the saved frame, so where that frame sits on
        # the sensor ('leftEdge', 'topEdge') has no field of its own either.
        device_metadata["ROI"] = [region_of_interest["height"], region_of_interest["width"]]
        offsets = {f"ROI.{key}": value for key, value in region_of_interest.items() if key not in ("height", "width")}
        unmapped_settings.update(offsets)

    if unmapped_settings:
        settings = ", ".join(f"{key}: {value}" for key, value in sorted(unmapped_settings.items()))
        device_metadata["description"] = (
            "Settings recorded by the Miniscope DAQ software that the ndx-miniscope schema "
            f"has no field for: {settings}."
        )

    return device_metadata


def _config_to_miniscope_device_model_metadata(miniscope_config: dict) -> dict | None:
    """Map a V4 device configuration onto a ``metadata["DeviceModels"]`` entry, or ``None``.

    ``deviceType`` is the hardware design the DAQ was configured for (``Miniscope_V4_BNO``), which is a
    model rather than a property of the individual scope, so it is written as the ``DeviceModel`` that
    pynwb 4 asks for. The manufacturer NWB requires of a model is not something the DAQ records, and is
    filled where the model is built.
    """
    device_type = miniscope_config.get("deviceType")
    if device_type is None:
        return None

    return {"name": str(device_type)}


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


def _get_device_folder_timestamps(folder_path: str) -> np.ndarray:
    """Read the ``timeStamps.csv`` of a single V4 device folder as seconds.

    The DAQ writes the first frame with a negative timestamp because that frame is captured before
    the recording start marker. Following the upstream guidance the first sample is zeroed, rather
    than shifting the whole series by it, which would displace every later frame.
    """
    timestamps_file_path = Path(folder_path) / "timeStamps.csv"
    assert timestamps_file_path.is_file(), f"The timestamps file is missing from '{folder_path}'."

    timestamps = pd.read_csv(timestamps_file_path)["Time Stamp (ms)"].to_numpy(dtype=float) / 1000.0
    if timestamps.size and timestamps[0] < 0.0:
        timestamps[0] = 0.0

    return timestamps


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
