"""Collection of helper functions related to configuration of datasets dependent on backend."""

from typing import Literal, Union

from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, NWBFile

from ._configuration_models._hdf5_backend import HDF5BackendConfiguration
from ._configuration_models._zarr_backend import ZarrBackendConfiguration

BACKEND_CONFIGURATIONS = dict(hdf5=HDF5BackendConfiguration, zarr=ZarrBackendConfiguration)


def get_default_backend_configuration(
    nwbfile: NWBFile, backend: Literal["hdf5", "zarr"]
) -> Union[HDF5BackendConfiguration, ZarrBackendConfiguration]:
    """Fill a default backend configuration to serve as a starting point for further customization."""

    BackendConfigurationClass = BACKEND_CONFIGURATIONS[backend]
    return BackendConfigurationClass.from_nwbfile(nwbfile=nwbfile)


def get_existing_backend_configuration(nwbfile: NWBFile) -> Union[HDF5BackendConfiguration, ZarrBackendConfiguration]:
    """Fill an existing backend configuration to serve as a starting point for further customization."""

    read_io = nwbfile.read_io
    if isinstance(read_io, NWBHDF5IO):
        backend = "hdf5"
    elif isinstance(read_io, NWBZarrIO):
        backend = "zarr"
    else:
        raise ValueError(f"The backend of the NWBFile from io {read_io} is not recognized.")
    BackendConfigurationClass = BACKEND_CONFIGURATIONS[backend]
    return BackendConfigurationClass.from_nwbfile(nwbfile=nwbfile, use_default_dataset_io_configurations=False)
