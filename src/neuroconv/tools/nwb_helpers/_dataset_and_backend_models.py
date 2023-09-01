"""Collection of helper functions related to configuration of datasets dependent on backend."""
from typing import Any, Dict, Literal, Tuple, Type, Union

import h5py
import hdf5plugin
import psutil
import zarr
from hdmf.backends.hdf5 import H5DataIO
from hdmf.container import DataIO
from hdmf_zarr import ZarrDataIO
from nwbinspector.utils import is_module_installed
from pydantic import BaseModel, Field, root_validator


class DatasetInfo(BaseModel):
    object_id: str
    location: str
    maxshape: Tuple[int, ...]
    dtype: str  # Think about how to constrain/specify this more

    class Config:  # noqa: D106
        allow_mutation = False

    def __hash__(self):
        """To allow instances of this class to be used as keys in dictionaries."""
        return hash((type(self),) + tuple(self.__dict__.values()))


class DatasetConfiguration(BaseModel):
    """A data model for configruing options about an object that will become a HDF5 or Zarr Dataset in the file."""

    dataset_info: DatasetInfo
    chunk_shape: Tuple[int, ...]
    buffer_shape: Tuple[int, ...]
    compression_method: Union[str, None]  # Backend configurations should specify Literals; None means no compression
    compression_options: Union[Dict[str, Any], None] = None

    def __str__(self) -> str:
        """Not overriding __repr__ as this is intended to render only when wrapped in print()."""
        string = (
            f"{self.object_name} of {self.parent}\n"
            + f"{'-' * (len(self.object_name) + 4 + len(self.parent))}\n"
            + f"  {self.field}\n"
            + f"    maxshape: {self.maxshape}\n"
            + f"    dtype: {self.dtype}"
        )
        return string


_available_hdf5_filters = set(h5py.filters.decode) - set(("shuffle", "fletcher32", "scaleoffset"))
if is_module_installed(module_name="hdf5plugin"):
    _available_hdf5_filters = _available_hdf5_filters | set(
        (filter_.filter_name for filter_ in hdf5plugin.get_filters())
    )
AVAILABLE_HDF5_COMPRESSION_METHODS = Literal[tuple(_available_hdf5_filters)]


class HDF5DatasetConfiguration(DatasetConfiguration):
    """A data model for configruing options about an object that will become a HDF5 Dataset in the file."""

    compression_method: Union[AVAILABLE_HDF5_COMPRESSION_METHODS, None] = "gzip"
    # TODO: actually provide better schematic rendering of options. Only support defaults in GUIDE for now
    # Looks like they'll have to be hand-typed however... Can try parsing the google docstrings but no annotation typing
    compression_options: Union[Dict[str, Any], None] = None


_available_zarr_filters = (
    set(zarr.codec_registry.keys())
    - set(
        # These filters do nothing for us, or are things that ought to be implemented at lower HDMF levels
        # or indirectly using HDMF data structures
        (
            "json2",  # no data savings
            "pickle",  # no data savings
            "vlen-utf8",  # enforced by HDMF
            "vlen-array",  # enforced by HDMF
            "vlen-bytes",  # enforced by HDMF
            "adler32",  # checksum
            "crc32",  # checksum
            "fixedscaleoffset",  # enforced indrectly by HDMF/PyNWB data types
            "base64",  # unsure what this would ever be used for
            "n5_wrapper",  # different data format
        )
    )
    - set(  # Forbidding lossy codecs for now, but they could be allowed in the future with warnings
        ("astype", "bitround", "quantize")
    )
)
# TODO: would like to eventually (as separate feature) add an 'auto' method to Zarr
# to harness the wider range of potential methods that are ideal for certain dtypes or structures
# E.g., 'packbits' for boolean (logical) VectorData columns
# | set(("auto",))
AVAILABLE_ZARR_COMPRESSION_METHODS = Literal[tuple(_available_zarr_filters)]


class ZarrDatasetConfiguration(DatasetConfiguration):
    """A data model for configruing options about an object that will become a Zarr Dataset in the file."""

    filter_methods: Union[Tuple[AVAILABLE_ZARR_COMPRESSION_METHODS, ...], None] = None
    filter_options: Union[Tuple[Dict[str, Any]], None] = None
    compression_method: Union[AVAILABLE_ZARR_COMPRESSION_METHODS, None] = "gzip"  # TODO: would like this to be 'auto'
    # TODO: actually provide better schematic rendering of options. Only support defaults in GUIDE for now
    # Looks like they'll have to be hand-typed however... Can try parsing the google docstrings but no annotation typing
    compression_options: Union[Dict[str, Any], None] = None

    @root_validator()
    def validate_filter_methods_and_options_match(cls, values: Dict[str, Any]):
        filter_methods = values["filter_methods"]
        filter_options = values["filter_options"]

        if filter_methods is None and filter_options is not None:
            raise ValueError(f"`filter_methods` is `None` but `filter_options` is not ({filter_options})!")
        elif filter_methods is None and filter_options is None:
            return values

        len_filter_methods = len(filter_methods)
        len_filter_options = len(filter_options)
        if len_filter_methods != len_filter_options:
            raise ValueError(
                f"Length mismatch between `filter_methods` ({len_filter_methods} methods specified) and "
                f"`filter_options` ({len_filter_options} options found)! These two must match one-to-one."
            )

        return values

    # think about extra validation that msgpack2 compression only ideal for datasets of vlen strings


class BackendConfiguration(BaseModel):
    """A model for matching collections of DatasetConfigurations specific to the HDF5 backend."""

    backend: Literal["hdf5", "zarr"]
    data_io: Type[DataIO]
    dataset_configurations: Dict[str, DatasetConfiguration]  # str is location field of DatasetConfiguration

    def __str__(self) -> str:
        """Not overriding __repr__ as this is intended to render only when wrapped in print()."""
        string = (
            f"Configurable datasets identified using the {self.backend} backend\n"
            f"{'-' * (43 + len(self.backend) + 8)}\n"
        )

        for dataset_configuration in self.dataset_configurations.values():
            dataset_info = dataset_configuration.dataset_info
            string += (
                f"{dataset_info.location}\n"
                f"    maxshape : {dataset_info.maxshape}\n"
                f"    dtype : {dataset_info.dtype}\n\n"
                f"    chunk shape : {dataset_configuration.chunk_shape}\n"
                f"    buffer shape : {dataset_configuration.buffer_shape}\n"
                f"    compression method : {dataset_configuration.compression_method}\n"
                f"    compression options : {dataset_configuration.compression_options}\n\n\n"
            )

        return string


class HDF5BackendConfiguration(BackendConfiguration):
    """A model for matching collections of DatasetConfigurations specific to the HDF5 backend."""

    backend: Literal["hdf5"] = "hdf5"
    data_io: Type[H5DataIO] = H5DataIO
    dataset_configurations: Dict[str, HDF5DatasetConfiguration]  # str is location field of DatasetConfiguration


class ZarrBackendConfiguration(BackendConfiguration):
    """A model for matching collections of DatasetConfigurations specific to the Zarr backend."""

    backend: Literal["zarr"] = "zarr"
    data_io: Type[ZarrDataIO] = ZarrDataIO
    dataset_configurations: Dict[str, ZarrDatasetConfiguration]  # str is location field of DatasetConfiguration
    number_of_jobs: int = Field(
        description="Number of jobs to use in parallel during write.",
        ge=-psutil.cpu_count(),  # TODO: should we specify logical=False in cpu_count?
        le=psutil.cpu_count(),
        default=-2,  # -2 translates to 'all CPU except for one'
    )

    def __str__(self) -> str:
        """Not overriding __repr__ as this is intended to render only when wrapped in print()."""
        string = (
            f"Configurable datasets identified using the {self.backend} backend\n"
            f"{'-' * (43 + len(self.backend) + 8)}\n"
        )

        for dataset_configuration in self.dataset_configurations.values():
            dataset_info = dataset_configuration.dataset_info
            string += (
                f"{dataset_info.location}\n"
                f"    maxshape : {dataset_info.maxshape}\n"
                f"    dtype : {dataset_info.dtype}\n\n"
                f"    chunk shape : {dataset_configuration.chunk_shape}\n"
                f"    buffer shape : {dataset_configuration.buffer_shape}\n"
                f"    compression method : {dataset_configuration.compression_method}\n"
                f"    compression options : {dataset_configuration.compression_options}\n"
                f"    filter methods : {dataset_configuration.filter_methods}\n"
                f"    filter options : {dataset_configuration.filter_options}\n\n\n"
            )

        return string


BACKEND_TO_DATASET_CONFIGURATION = dict(hdf5=HDF5DatasetConfiguration, zarr=ZarrDatasetConfiguration)
BACKEND_TO_CONFIGURATION = dict(hdf5=HDF5BackendConfiguration, zarr=ZarrBackendConfiguration)
