"""Authors: Cody Baker, Alessio Buccino."""
import numpy as np
import uuid
from datetime import datetime
from warnings import warn

from pynwb import NWBFile, NWBHDF5IO
from pynwb.file import Subject

from .json_schema import dict_deep_update


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


def check_sorted(data):
    """Check whether the specified data is in sorted order."""
    dd = data[:]
    if not np.all(dd == np.sort(dd)):
        print(data.name + " is not ordered")


def check_binary(data):
    """Check whether the data is binary."""
    if len(np.unique(data[:])) == 2:
        print(data.name + " is binary. Consider making it boolean.")


def check_time_dim(time_series):
    """Check whether the time series is properly oriented for NWB."""
    if hasattr(time_series, "timestamps") and time_series.timestamps is not None:
        if not len(time_series.data) == len(time_series.timestamps):
            print(time_series.name + "data and timestamp length mismatch")
    else:
        shape = time_series.data.shape
        if len(shape) > 1:
            if not shape[0] == max(shape):
                print(time_series.name + " time is not the longest dimension")


def check_constant_rate(time_series):
    """Check whether the time series has a constant rate."""
    if hasattr(time_series, "timestamps") and time_series.timestamps is not None:
        if check_regular_timestamps(ts=time_series):
            print(time_series.name + " sampling rate is constant. " "Consider using rate instead of timestamps")


def auto_qc(fpath):
    """Perform an automatic quality check on the NWBFile."""
    with NWBHDF5IO(path=fpath, mode="r", load_namespaces=True) as io:
        nwb = io.read()

        # trials
        print("trials:")
        check_sorted(nwb.trials["start_time"])
        check_sorted(nwb.trials["stop_time"])

        for col in nwb.trials.columns:
            if col.data.dtype == np.dtype("O"):
                check_binary(col)
