import os
from pathlib import Path

import numpy as np
from pynwb import NWBHDF5IO, H5DataIO, TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers._configuration_models._hdf5_backend import (
    HDF5BackendConfiguration,
)


def write_nwbfile(nwbfile_path: Path):
    if nwbfile_path.exists():
        os.remove(nwbfile_path)
    nwbfile = mock_NWBFile()
    timestamps = np.arange(10.0)
    data = np.arange(100, 200, 10)
    time_series_with_timestamps = TimeSeries(
        name="test_timeseries",
        description="an example time series",
        data=H5DataIO(data=data, compression="gzip", chunks=(1,), compression_opts=2),
        unit="m",
        timestamps=timestamps,
    )
    nwbfile.add_acquisition(time_series_with_timestamps)
    with NWBHDF5IO(nwbfile_path, mode="w") as io:
        io.write(nwbfile)


def main():
    nwbfile_path = Path("/Volumes/T7/CatalystNeuro/temp.nwb")
    write_nwbfile(nwbfile_path)
    with NWBHDF5IO(nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        hdf5_backend_config = HDF5BackendConfiguration.from_existing_nwbfile(nwbfile)
        print(hdf5_backend_config)


if __name__ == "__main__":
    main()
