"""Base Pydantic models for the ZarrDatasetConfiguration."""
from typing import Any, Dict, List, Literal, Type, Union

import numcodecs
import psutil
import zarr
from hdmf_zarr import ZarrDataIO
from pydantic import Field, root_validator

from ._base_models import BackendConfiguration, DatasetConfiguration

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
            "msgpack2",  # think more on if we want to include this for variable length string datasets
            "adler32",  # checksum
            "crc32",  # checksum
            "fixedscaleoffset",  # enforced indrectly by HDMF/PyNWB data types
            "base64",  # unsure what this would ever be used for
            "n5_wrapper",  # different data format
        )
    )
    - set(  # Forbidding lossy codecs for now, but they could be allowed in the future with warnings?
        ("astype", "bitround", "quantize")  # (Users can always initialize and pass explicitly via code)
    )
)
# TODO: would like to eventually (as separate feature) add an 'auto' method to Zarr
# to harness the wider range of potential methods that are ideal for certain dtypes or structures
# E.g., 'packbits' for boolean (logical) VectorData columns
# | set(("auto",))
AVAILABLE_ZARR_COMPRESSION_METHODS = tuple(_available_zarr_filters)


class ZarrDatasetConfiguration(DatasetConfiguration):
    """A data model for configuring options about an object that will become a Zarr Dataset in the file."""

    # TODO: When using Pydantic v2, replace with `model_config = ConfigDict(...)`
    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True

    compression_method: Union[Literal[AVAILABLE_ZARR_COMPRESSION_METHODS], numcodecs.abc.Codec, None] = Field(
        default="gzip",  # TODO: would like this to be 'auto'
        description=(
            "The specified compression method to apply to this dataset. "
            "Can be either a string that matches an available method on your system, "
            "or an instantiated numcodec.Codec object."
            "Set to `None` to disable compression."
        ),
    )
    # TODO: actually provide better schematic rendering of options. Only support defaults in GUIDE for now.
    # Looks like they'll have to be hand-typed however... Can try parsing the numpy docstrings - no annotation typing.
    compression_options: Union[Dict[str, Any], None] = Field(
        default=None, description="The optional parameters to use for the specified compression method."
    )
    filter_methods: Union[List[Union[Literal[AVAILABLE_ZARR_COMPRESSION_METHODS], numcodecs.abc.Codec]], None] = Field(
        default=None,
        description=(
            "The ordered collection of filtering methods to apply to this dataset prior to compression. "
            "Each element can be either a string that matches an available method on your system, "
            "or an instantiated numcodec.Codec object."
            "Set to `None` to disable filtering."
        ),
    )
    filter_options: Union[List[Dict[str, Any]], None] = Field(
        default=None, description="The optional parameters to use for each specified filter method."
    )

    def __str__(self) -> str:
        string = super().__str__()
        if self.filter_methods is not None:
            string += f"\n  filter_methods: {self.filter_methods}"
        if self.filter_options is not None:
            string += f"\n  filter_options: {self.filter_options}"

        return string

    @root_validator
    def validate_filter_methods_and_options_length_match(cls, values: Dict[str, Any]):
        filter_methods = values["filter_methods"]
        filter_options = values["filter_options"]

        if filter_methods is None and filter_options is not None:
            raise ValueError(f"`filter_methods` is `None` but `filter_options` is not (received {filter_options})!")
        elif filter_options is None:
            return values

        len_filter_methods = len(filter_methods)
        len_filter_options = len(filter_options)
        if len_filter_methods != len_filter_options:
            raise ValueError(
                f"Length mismatch between `filter_methods` ({len_filter_methods} methods specified) and "
                f"`filter_options` ({len_filter_options} options found)! These two must match one-to-one."
            )

        return values

    def get_data_io_keyword_arguments(self) -> Dict[str, Any]:
        filters = None
        if self.filter_methods:
            filters = list()
            all_filter_options = self.filter_options or [dict() for _ in self.filter_methods]
            for filter_method, filter_options in zip(self.filter_methods, all_filter_options):
                if isinstance(filter_method, str):
                    filters.append(zarr.codec_registry[filter_method](**filter_options))
                elif isinstance(filter_method, numcodecs.abc.Codec):
                    filters.append(filter_method)

        if isinstance(self.compression_method, str):
            compressor = zarr.codec_registry[self.compression_method](**self.compression_options)
        if isinstance(self.compression_method, numcodecs.abc.Codec):
            compressor = self.compression_method
        elif self.compression_method is None:
            compressor = False

        return dict(chunks=self.chunk_shape, filters=filters, compressor=compressor)


class ZarrBackendConfiguration(BackendConfiguration):
    """A model for matching collections of DatasetConfigurations specific to the Zarr backend."""

    backend: Literal["zarr"] = Field(
        default="zarr", description="The name of the backend used to configure the NWBFile."
    )
    data_io_class: Type[ZarrDataIO] = Field(
        default=ZarrDataIO, description="The DataIO class that is specific to Zarr."
    )
    dataset_configurations: Dict[str, ZarrDatasetConfiguration] = Field(
        description=(
            "A mapping from object locations to their ZarrDatasetConfiguration specification that contains all "
            "information for writing the datasets to disk using the Zarr backend."
        )
    )
    number_of_jobs: int = Field(
        description="Number of jobs to use in parallel during write. Negative slicing conforms with the pattern of indexing `list(range(total_number_of_cpu))[number_of_jobs]`; for example, `-1` uses all available CPU, `-2` uses all except one, etc.",
        ge=-psutil.cpu_count(),  # TODO: should we specify logical=False in cpu_count?
        le=psutil.cpu_count(),
        default=-2,  # -2 translates to 'all CPU except for one'
    )
