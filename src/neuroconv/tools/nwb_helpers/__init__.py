from ._dataset_configuration import get_default_dataset_configurations
from ._metadata_and_file_helpers import (
    add_device_from_metadata,
    get_default_nwbfile_metadata,
    get_module,
    make_nwbfile_from_metadata,
    make_or_load_nwbfile,
)
from ._models._base_models import DatasetInfo
from ._models._hdf5_models import (
    AVAILABLE_HDF5_COMPRESSION_METHODS,
    HDF5BackendConfiguration,
    HDF5DatasetConfiguration,
)
from ._models._zarr_models import (
    AVAILABLE_ZARR_COMPRESSION_METHODS,
    ZarrBackendConfiguration,
    ZarrDatasetConfiguration,
)

DATASET_CONFIGURATIONS = dict(hdf5=HDF5DatasetConfiguration, zarr=ZarrDatasetConfiguration)
BACKEND_CONFIGURATIONS = dict(hdf5=HDF5BackendConfiguration, zarr=ZarrBackendConfiguration)
