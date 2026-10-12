"""Collection of helper functions related to configuration of datasets dependent on backend."""

from typing import Literal

from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, NWBFile

from ._configuration_models._hdf5_backend import HDF5BackendConfiguration
from ._configuration_models._zarr_backend import ZarrBackendConfiguration

BACKEND_CONFIGURATIONS = dict(hdf5=HDF5BackendConfiguration, zarr=ZarrBackendConfiguration)
BACKEND_NWB_IO = dict(hdf5=NWBHDF5IO, zarr=NWBZarrIO)


def get_default_backend_configuration(
    nwbfile: NWBFile, backend: Literal["hdf5", "zarr"]
) -> HDF5BackendConfiguration | ZarrBackendConfiguration:
    """Fill a default backend configuration to serve as a starting point for further customization."""

    BackendConfigurationClass = BACKEND_CONFIGURATIONS[backend]
    return BackendConfigurationClass.from_nwbfile_with_defaults(nwbfile=nwbfile)


def get_existing_backend_configuration(nwbfile: NWBFile) -> HDF5BackendConfiguration | ZarrBackendConfiguration:
    """Fill an existing backend configuration to serve as a starting point for further customization.

    Parameters
    ----------
    nwbfile : NWBFile
        The NWBFile object to extract the backend configuration from. The nwbfile must have been read from an io object
        to work properly.

    Returns
    -------
    HDF5BackendConfiguration | ZarrBackendConfiguration
        The backend configuration extracted from the nwbfile.
    """
    read_io = nwbfile.read_io
    for backend, io in BACKEND_NWB_IO.items():
        if isinstance(read_io, io):
            break
    BackendConfigurationClass = BACKEND_CONFIGURATIONS[backend]
    return BackendConfigurationClass.from_nwbfile_with_existing(nwbfile=nwbfile)
