from ._metadata_and_file_helpers import (
    add_device_from_metadata,
    get_default_nwbfile_metadata,
    get_module,
    make_nwbfile_from_metadata,
    make_or_load_nwbfile,
)
from ._models._base_models import DatasetConfiguration, DatasetInfo
from ._models._hdf5_models import HDF5BackendConfiguration, HDF5DatasetConfiguration, AVAILABLE_HDF5_COMPRESSION_METHODS
from ._models._zarr_models import ZarrBackendConfiguration, ZarrDatasetConfiguration, AVAILABLE_ZARR_COMPRESSION_METHODS

BACKEND_TO_DATASET_CONFIGURATION = dict(hdf5=HDF5DatasetConfiguration, zarr=ZarrDatasetConfiguration)
BACKEND_TO_CONFIGURATION = dict(hdf5=HDF5BackendConfiguration, zarr=ZarrBackendConfiguration)
