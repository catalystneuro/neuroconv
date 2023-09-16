from ._metadata_and_file_helpers import (
    add_device_from_metadata,
    get_default_nwbfile_metadata,
    get_module,
    make_nwbfile_from_metadata,
    make_or_load_nwbfile,
)
from ._models._base_dataset_models import (
    DatasetConfiguration,
    DatasetInfo,
    HDF5DatasetConfiguration,
    ZarrDatasetConfiguration,
)
from ._models._hdf5_dataset_models import HDF5DatasetConfiguration, AVAILABLE_HDF5_COMPRESSION_METHODS
from ._models._zarr_dataset_models import ZarrDatasetConfiguration, AVAILABLE_ZARR_COMPRESSION_METHODS

BACKEND_TO_DATASET_CONFIGURATION = dict(hdf5=HDF5DatasetConfiguration, zarr=ZarrDatasetConfiguration)
