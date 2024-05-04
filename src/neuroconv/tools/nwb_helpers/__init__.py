"""Collection of Pydantic models and helper functions for configuring dataset IO parameters for different backends."""

# Mark these imports as private to avoid polluting the namespace; only used in global BACKEND_NWB_IO mapping
from hdmf_zarr import NWBZarrIO as _NWBZarrIO
from pynwb import NWBHDF5IO as _NWBHDF5IO

from ._backend_configuration import get_default_backend_configuration
from ._configuration_models._base_backend import BackendConfiguration
from ._configuration_models._base_dataset_io import DatasetIOConfiguration
from ._configuration_models._hdf5_backend import HDF5BackendConfiguration
from ._configuration_models._hdf5_dataset_io import (
    AVAILABLE_HDF5_COMPRESSION_METHODS,
    HDF5DatasetIOConfiguration,
)
from ._configuration_models._zarr_backend import ZarrBackendConfiguration
from ._configuration_models._zarr_dataset_io import (
    AVAILABLE_ZARR_COMPRESSION_METHODS,
    ZarrDatasetIOConfiguration,
)
from ._configure_backend import configure_backend
from ._dataset_configuration import get_default_dataset_io_configurations
from ._metadata_and_file_helpers import (
    add_device_from_metadata,
    get_default_nwbfile_metadata,
    get_module,
    make_nwbfile_from_metadata,
    make_or_load_nwbfile,
)

BACKEND_CONFIGURATIONS = dict(hdf5=HDF5BackendConfiguration, zarr=ZarrBackendConfiguration)
DATASET_IO_CONFIGURATIONS = dict(hdf5=HDF5DatasetIOConfiguration, zarr=ZarrDatasetIOConfiguration)
BACKEND_NWB_IO = dict(hdf5=_NWBHDF5IO, zarr=_NWBZarrIO)

__all__ = [
    "AVAILABLE_HDF5_COMPRESSION_METHODS",
    "AVAILABLE_ZARR_COMPRESSION_METHODS",
    "BACKEND_CONFIGURATIONS",
    "DATASET_IO_CONFIGURATIONS",
    "BACKEND_NWB_IO",
    "BackendConfiguration",
    "HDF5BackendConfiguration",
    "ZarrBackendConfiguration",
    "DatasetIOConfiguration",
    "HDF5DatasetIOConfiguration",
    "ZarrDatasetIOConfiguration",
    "get_default_backend_configuration",
    "get_default_dataset_io_configurations",
    "configure_backend",
    "get_default_dataset_io_configurations",
    "get_default_backend_configuration",
    "add_device_from_metadata",
    "get_default_nwbfile_metadata",
    "get_module",
    "make_nwbfile_from_metadata",
    "make_or_load_nwbfile",
]
