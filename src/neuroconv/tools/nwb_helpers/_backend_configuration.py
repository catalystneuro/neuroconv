"""Collection of helper functions related to configuration of datasets dependent on backend."""

from typing import Literal, Union

from pynwb import NWBFile

from ._configuration_models._hdf5_backend import HDF5BackendConfiguration
from ._configuration_models._zarr_backend import ZarrBackendConfiguration

BACKEND_CONFIGURATIONS = dict(hdf5=HDF5BackendConfiguration, zarr=ZarrBackendConfiguration)


def get_default_backend_configuration(
    nwbfile: NWBFile, backend: Literal["hdf5", "zarr"]
) -> Union[HDF5BackendConfiguration, ZarrBackendConfiguration]:
    """
    Fill a default backend configuration to serve as a starting point for further customization.

    Parameters
    ----------
    nwbfile : NWBFile
        The NWB file to create a backend configuration for.
    backend : {'hdf5', 'zarr'}
        The backend type to configure.

    Returns
    -------
    Union[HDF5BackendConfiguration, ZarrBackendConfiguration]
        A backend configuration object with default settings based on the specified backend type.
    """

    BackendConfigurationClass = BACKEND_CONFIGURATIONS[backend]
    return BackendConfigurationClass.from_nwbfile(nwbfile=nwbfile)
