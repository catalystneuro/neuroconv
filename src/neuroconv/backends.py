from dataclasses import dataclass

from pynwb import NWBHDF5IO
from hdmf.backends.io import HDMFIO
from hdmf.backends.hdf5.h5tools import H5DataIO
from hdmf.data_utils import DataIO

from hdmf_zarr.nwb import NWBZarrIO
from hdmf_zarr.utils import ZarrDataIO


@dataclass
class BackendConfig:
    nwb_io: HDMFIO
    data_io: DataIO
    data_io_defaults: dict


backends = dict(
    hdf5=BackendConfig(
        nwb_io=NWBHDF5IO,
        data_io=H5DataIO,
        data_io_defaults=dict(compression="gzip", compression_opts=4),
    ),
    zarr=BackendConfig(
        nwb_io=NWBZarrIO,
        data_io=ZarrDataIO,
        data_io_defaults=dict(),
    )
)