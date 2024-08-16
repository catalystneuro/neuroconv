import os
from pathlib import Path

import numpy as np
from pynwb import NWBHDF5IO, H5DataIO, TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import (
    repack_nwbfile,
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
    repacked_nwbfile_path = Path("/Volumes/T7/CatalystNeuro/repacked_temp.nwb")
    if repacked_nwbfile_path.exists():
        os.remove(repacked_nwbfile_path)
    if not nwbfile_path.exists():
        write_nwbfile(nwbfile_path)
    backend_configuration_changes = {"acquisition/test_timeseries/data": dict(chunk_shape=(2,))}
    repack_nwbfile(
        nwbfile_path=nwbfile_path,
        export_nwbfile_path=repacked_nwbfile_path,
        backend="hdf5",
        backend_configuration_changes=backend_configuration_changes,
        use_default_backend_configuration=False,
    )

    with NWBHDF5IO(repacked_nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        print(f'{nwbfile.acquisition["test_timeseries"].data.chunks = }')


if __name__ == "__main__":
    main()
