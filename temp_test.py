import os
import shutil
from pathlib import Path

import numpy as np
from hdmf_zarr import ZarrDataIO
from hdmf_zarr.nwb import NWBZarrIO
from pynwb import NWBHDF5IO, H5DataIO, TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import repack_nwbfile


def write_nwbfile(nwbfile_path: Path, backend: str = "hdf5"):
    """Temp"""
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
    """Temp"""
    backend = "zarr"
    if backend == "hdf5":
        nwbfile_path = Path("temp.nwb")
        repacked_nwbfile_path = Path("repacked_temp.nwb")
    else:
        nwbfile_path = Path("temp.nwb.zarr")
        repacked_nwbfile_path = Path("repacked_temp.nwb.zarr")
    if repacked_nwbfile_path.exists():
        if repacked_nwbfile_path.is_dir():
            shutil.rmtree(repacked_nwbfile_path)
        else:
            os.remove(repacked_nwbfile_path)
    if not nwbfile_path.exists():
        write_nwbfile(nwbfile_path, backend=backend)

    backend_configuration_changes = {"acquisition/test_timeseries/data": dict(chunk_shape=(2,))}
    repack_nwbfile(
        nwbfile_path=str(nwbfile_path),
        export_nwbfile_path=str(repacked_nwbfile_path),
        backend=backend,
        backend_configuration_changes=backend_configuration_changes,
        use_default_backend_configuration=True,
    )

    with NWBZarrIO(str(repacked_nwbfile_path), mode="r") as io:
        nwbfile = io.read()
        print(f'{nwbfile.acquisition["test_timeseries"].data.chunks = }')


if __name__ == "__main__":
    main()
