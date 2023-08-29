"""Collection of helper functions related to configuration of datasets dependent on backend."""
from typing import Any, Dict, Iterable, Literal, Tuple, Type

import h5py
import hdf5plugin
import zarr
from hdmf.data_utils import DataIO
from nwbinspector.utils import is_module_installed
from pydantic import BaseModel, root_validator


class ConfigurableDataset(BaseModel):
    """A data model for summarizing information about an object that will become a HDF5 or Zarr Dataset in the file."""

    object_id: str
    object_name: str
    parent: str
    field: Literal["data", "timestamps"]
    maxshape: Tuple[int, ...]
    dtype: str  # Think about how to constrain/specify this more

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


class DatasetConfiguration(BaseModel):
    """A data model for configruing options about an object that will become a HDF5 or Zarr Dataset in the file."""

    object_id: str
    object_name: str
    parent: str
    field: Literal["data", "timestamps"]
    chunk_shape: Tuple[int, ...]
    buffer_shape: Tuple[int, ...]
    maxshape: Tuple[int, ...]
    compression_method: str
    compression_options: Dict[str, Any]
    dtype: str  # Think about how to constrain/specify this more

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


class BackendConfiguration(BaseModel):
    """A model for matching collections of DatasetConfigurations specific to a backend with its name and DataIO."""

    backend_type: Literal["hdf5", "zarr"]
    data_io: Type[DataIO]
    dataset_configurations: Iterable[DatasetConfiguration]


_available_hdf5_filters = set(h5py.filters.decode) - set(("shuffle", "fletcher32", "scaleoffset"))
if is_module_installed(module_name="hdf5plugin"):
    _available_hdf5_filters = _available_hdf5_filters | set(
        (filter_.filter_name for filter_ in hdf5plugin.get_filters())
    )
AVAILABLE_HDF5_COMPRESSION_METHODS = Literal[tuple(_available_hdf5_filters)]


class HDF5DatasetConfiguration(BaseModel):
    """A data model for configruing options about an object that will become a HDF5 Dataset in the file."""

    object_id: str
    object_name: str
    parent: str
    field: Literal["data", "timestamps"]
    chunk_shape: Tuple[int, ...]
    buffer_shape: Tuple[int, ...]
    maxshape: Tuple[int, ...]
    compression_method: AVAILABLE_HDF5_COMPRESSION_METHODS = "gzip"
    # TODO: actually provide better schematic rendering of options. Only support defaults in GUIDE for now
    # Looks like they'll have to be hand-typed however... Can try parsing the google docstrings but no annotation typing
    compression_options: Dict[str, Any]
    dtype: str  # Think about how to constrain/specify this more


_available_zarr_filters = set(zarr.codec_registry.keys()) - set(("json2", "pickle"))
AVAILABLE_ZARR_COMPRESSION_METHODS = Literal[tuple(_available_zarr_filters)]


class ZarrDatasetConfiguration(BaseModel):
    """A data model for configruing options about an object that will become a Zarr Dataset in the file."""

    object_id: str
    object_name: str
    parent: str
    field: Literal["data", "timestamps"]
    chunk_shape: Tuple[int, ...]
    buffer_shape: Tuple[int, ...]
    maxshape: Tuple[int, ...]
    filter_methods: Tuple[AVAILABLE_ZARR_COMPRESSION_METHODS, ...]
    filter_options: Tuple[Dict[str, Any]]
    compression_method: AVAILABLE_ZARR_COMPRESSION_METHODS
    # TODO: actually provide better schematic rendering of options. Only support defaults in GUIDE for now
    # Looks like they'll have to be hand-typed however... Can try parsing the google docstrings but no annotation typing
    compression_option: Dict[str, Any]
    dtype: str  # Think about how to constrain/specify this more

    @root_validator()
    def verify_filter_methods_and_options_match(cls, values: Dict[str, Any]):
        filter_methods = values.get("filter_methods")
        filter_options = values.get("filter_options")

        len_filter_methods = len(filter_methods)
        len_filter_options = len(filter_options)
        if len_filter_methods != len_filter_options:
            raise ValueError(
                "Length mismatch between `filter_methods` ({len_filter_methods} methods specified) and "
                "`filter_options` ({len_filter_options} options found)! These two must match one-to-one."
            )
        return values
