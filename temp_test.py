import os
from pathlib import Path

import numpy as np
from pynwb import NWBHDF5IO, H5DataIO, TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers._dataset_configuration import (
    get_existing_dataset_io_configurations,
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
        existing_dataset_io_configurations = get_existing_dataset_io_configurations(nwbfile, backend="hdf5")
        for dataset_io_configuration in existing_dataset_io_configurations:
            print(dataset_io_configuration)


if __name__ == "__main__":
    main()
