"""Authors: Cody Baker, Alessio Buccino."""
from pathlib import Path
import numpy as np
import uuid
from datetime import datetime
from warnings import warn
from tempfile import mkdtemp
from shutil import rmtree
from time import perf_counter
from typing import Optional

from pynwb import NWBFile
from pynwb.file import Subject
from spikeextractors import RecordingExtractor, SubRecordingExtractor

from .json_schema import dict_deep_update
from .spike_interface import write_recording


def get_module(nwbfile: NWBFile, name: str, description: str = None):
    """Check if processing module exists. If not, create it. Then return module."""
    if name in nwbfile.processing:
        if description is not None and nwbfile.modules[name].description != description:
            warn(
                "Custom description given to get_module does not match existing module description! "
                "Ignoring custom description."
            )
        return nwbfile.processing[name]
    else:
        if description is None:
            description = "No description."
        return nwbfile.create_processing_module(name=name, description=description)


def get_default_nwbfile_metadata():
    """
    Return structure with defaulted metadata values required for a NWBFile.

    These standard defaults are
        metadata["NWBFile"]["session_description"] = "no description"
        metadata["NWBFile"]["session_description"] = datetime(1970, 1, 1)

    Proper conversions should override these fields prior to calling NWBConverter.run_conversion()
    """
    metadata = dict(
        NWBFile=dict(
            session_description="no description",
            session_start_time=datetime(1970, 1, 1).isoformat(),
            identifier=str(uuid.uuid4()),
        )
    )
    return metadata


def make_nwbfile_from_metadata(metadata: dict):
    """Make NWBFile from available metadata."""
    metadata = dict_deep_update(get_default_nwbfile_metadata(), metadata)
    nwbfile_kwargs = metadata["NWBFile"]
    if "Subject" in metadata:
        # convert ISO 8601 string to datetime
        if "date_of_birth" in metadata["Subject"] and isinstance(metadata["Subject"]["date_of_birth"], str):
            metadata["Subject"]["date_of_birth"] = datetime.fromisoformat(metadata["Subject"]["date_of_birth"])
        nwbfile_kwargs.update(subject=Subject(**metadata["Subject"]))
    # convert ISO 8601 string to datetime
    if isinstance(nwbfile_kwargs.get("session_start_time", None), str):
        nwbfile_kwargs["session_start_time"] = datetime.fromisoformat(metadata["NWBFile"]["session_start_time"])
    return NWBFile(**nwbfile_kwargs)


def check_regular_timestamps(ts):
    """Check whether rate should be used instead of timestamps."""
    time_tol_decimals = 9
    uniq_diff_ts = np.unique(np.diff(ts).round(decimals=time_tol_decimals))
    return len(uniq_diff_ts) == 1


def estimate_recording_conversion_time(
    recording: RecordingExtractor, mb_threshold: float = 100.0, write_kwargs: Optional[dict] = None
) -> (float, float):
    """
    Test the write speed of recording data to NWB on this system.

    recording : RecordingExtractor
        The recording object to be written.
    mb_threshold : float
        Maximum amount of data to test with. Defaults to 100, which is just over 2 seconds of standard SpikeGLX data.

    Returns
    -------
    total_time : float
        Estimate of total time (in minutes) to write all data based on speed estimate and known total data size.
    speed : float
        Speed of the conversion in MB/s.
    """
    if write_kwargs is None:
        write_kwargs = dict()

    temp_dir = Path(mkdtemp())
    test_nwbfile_path = temp_dir / "recording_speed_test.nwb"

    num_channels = recording.get_num_channels()
    itemsize = recording.get_dtype().itemsize
    total_mb = recording.get_num_frames() * num_channels * itemsize / 1e6
    if total_mb > mb_threshold:
        truncation = (mb_threshold * 1e6) // (num_channels * itemsize)
        test_recording = SubRecordingExtractor(parent_recording=recording, end_frame=truncation)
    else:
        test_recording = recording

    actual_test_mb = test_recording.get_num_frames() * num_channels * itemsize / 1e6
    start = perf_counter()
    write_recording(recording=test_recording, save_path=test_nwbfile_path, overwrite=True, **write_kwargs)
    end = perf_counter()
    delta = end - start
    speed = actual_test_mb / delta
    total_time = (total_mb / speed) / 60

    rmtree(temp_dir)
    return total_time, speed
