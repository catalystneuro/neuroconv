import os
from pathlib import Path

import numpy as np
from hdmf_zarr import ZarrDataIO
from hdmf_zarr.nwb import NWBZarrIO
from pynwb import NWBHDF5IO, H5DataIO, TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers._dataset_configuration import (
    get_existing_dataset_io_configurations,
)


def write_nwbfile(nwbfile_path: Path, backend: str = "hdf5"):
    if nwbfile_path.exists():
        os.remove(nwbfile_path)
    nwbfile = mock_NWBFile()
    timestamps = np.arange(10.0)
    data = np.arange(100, 200, 10)
    if backend == "hdf5":
        data = H5DataIO(data=data, compression="gzip", chunks=(1,), compression_opts=2)
    elif backend == "zarr":
        data = ZarrDataIO(data=data, chunks=(3,), compressor=True)
    time_series_with_timestamps = TimeSeries(
        name="test_timeseries",
        description="an example time series",
        data=data,
        unit="m",
        timestamps=timestamps,
    )
    nwbfile.add_acquisition(time_series_with_timestamps)
    IO = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with IO(str(nwbfile_path), mode="w") as io:
        io.write(nwbfile)


def main():
    nwbfile_path = Path("temp.nwb.zarr")
    repacked_nwbfile_path = Path("repacked_temp.nwb")
    if repacked_nwbfile_path.exists():
        os.remove(repacked_nwbfile_path)
    if not nwbfile_path.exists():
        write_nwbfile(nwbfile_path, backend="zarr")

    with NWBZarrIO(str(nwbfile_path), mode="r") as io:
        nwbfile = io.read()
        dataset_io_configurations = get_existing_dataset_io_configurations(nwbfile=nwbfile, backend="zarr")
        print(next(dataset_io_configurations))
    # backend_configuration_changes = {"acquisition/test_timeseries/data": dict(chunk_shape=(2,))}
    # repack_nwbfile(
    #     nwbfile_path=nwbfile_path,
    #     export_nwbfile_path=repacked_nwbfile_path,
    #     backend="hdf5",
    #     backend_configuration_changes=backend_configuration_changes,
    #     use_default_backend_configuration=False,
    # )

    # with NWBHDF5IO(repacked_nwbfile_path, mode="r") as io:
    #     nwbfile = io.read()
    #     print(f'{nwbfile.acquisition["test_timeseries"].data.chunks = }')


if __name__ == "__main__":
    main()
