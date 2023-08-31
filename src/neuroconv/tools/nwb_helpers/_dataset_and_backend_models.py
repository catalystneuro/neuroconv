"""Collection of helper functions related to configuration of datasets dependent on backend."""
from typing import Any, Dict, Literal, Tuple, Type, Union

import h5py
import hdf5plugin
import psutil
import zarr
from hdmf.data_utils import DataIO
from hdmf_zarr import NWBZarrIO
from nwbinspector.utils import is_module_installed
from pydantic import BaseModel, Field, root_validator
from pynwb import NWBHDF5IO


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


class DatasetConfiguration(ConfigurableDataset):
    """A data model for configruing options about an object that will become a HDF5 or Zarr Dataset in the file."""

    chunk_shape: Tuple[int, ...]
    buffer_shape: Tuple[int, ...]
    compression_method: Union[str, None]  # Backend configurations should specify Literals; None means no compression
    compression_options: Union[Dict[str, Any], None] = None


class BackendConfiguration(BaseModel):
    """A model for matching collections of DatasetConfigurations specific to a backend with its name and DataIO."""

    backend_type: Literal["hdf5", "zarr"]
    data_io: Type[DataIO]  # Auto-set by __init__
    dataset_configurations: Dict[ConfigurableDataset, DatasetConfiguration]

    def __init__(
        self,
        backend_type: Literal["hdf5", "zarr"],
        dataset_configurations: Dict[ConfigurableDataset, DatasetConfiguration],
    ):
        backend_to_data_io = dict(hdf5=NWBHDF5IO, zarr=NWBZarrIO)
        data_io = backend_to_data_io[backend_type]
        super().__init__(
            backend_to_data_io=backend_to_data_io, data_io=data_io, dataset_configurations=dataset_configurations
        )


class HDF5BackendConfiguration(BackendConfiguration):
    """A model for matching collections of DatasetConfigurations specific to the HDF5 backend."""

    pass  # No extra arguments exposed to HDF5 backend


class ZarrBackendConfiguration(BackendConfiguration):
    """A model for matching collections of DatasetConfigurations specific to the Zarr backend."""

    number_of_jobs: int = Field(
        description="Number of jobs to use in parallel during write.",
        ge=psutil.cpu_count(),  # TODO: should we specify logical=False in cpu_count?
        le=psutil.cpu_count(),
        default=-2,  # -2 translates to 'all CPU except for one'
    )


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
            "json2",
            "pickle",
            "astype",
            "vlen-utf8",
            "vlen-array",
            "vlen-bytes",
            "adler32",
            "crc32",
            "fixedscaleoffset",
            "msgpack2",
            "base64",
            "n5_wrapper",
        )
    )
    - set(  # Forbidding lossy codecs for now, but they could be allowed in the future with warnings
        ("bitround", "quantize")
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
    def verify_filter_methods_and_options_match(cls, values: Dict[str, Any]):
        filter_methods = values.get("filter_methods")
        filter_options = values.get("filter_options")

        len_filter_methods = len(filter_methods)
        len_filter_options = len(filter_options)
        if len_filter_methods != len_filter_options:
            raise ValueError(
                f"Length mismatch between `filter_methods` ({len_filter_methods} methods specified) and "
                f"`filter_options` ({len_filter_options} options found)! These two must match one-to-one."
            )
        return values
