"""Base Pydantic models for the ZarrDatasetConfiguration."""

from typing import Any, Literal, Union

import numcodecs
import zarr
from pydantic import Field, InstanceOf, model_validator

from ._base_dataset_io import DatasetIOConfiguration

_base_zarr_codecs = set(zarr.codec_registry.keys())
_lossy_zarr_codecs = set(("astype", "bitround", "quantize"))

# These filters do nothing for us, or are things that ought to be implemented at lower HDMF levels
# or indirectly using HDMF data structures
_excluded_zarr_codecs = set(
    (
        "json2",  # no data savings
        "pickle",  # no data savings
        "vlen-utf8",  # enforced by HDMF
        "vlen-array",  # enforced by HDMF
        "vlen-bytes",  # enforced by HDMF
        "msgpack2",  # think more on if we want to include this for variable length string datasets
        "adler32",  # checksum
        "crc32",  # checksum
        "fixedscaleoffset",  # enforced indirectly by HDMF/PyNWB data types
        "base64",  # unsure what this would ever be used for
        "n5_wrapper",  # different data format
    )
)

# Forbidding lossy codecs for now, but they could be allowed in the future with warnings?
# (Users can always initialize and pass explicitly via code)
_available_zarr_codecs = set(_base_zarr_codecs - _lossy_zarr_codecs - _excluded_zarr_codecs)

# TODO: would like to eventually (as separate feature) add an 'auto' method to Zarr
# to harness the wider range of potential methods that are ideal for certain dtypes or structures
# E.g., 'packbits' for boolean (logical) VectorData columns
# | set(("auto",))
AVAILABLE_ZARR_COMPRESSION_METHODS = {
    codec_name: zarr.codec_registry[codec_name] for codec_name in _available_zarr_codecs
}


class ZarrDatasetIOConfiguration(DatasetIOConfiguration):
    """A data model for configuring options about an object that will become a Zarr Dataset in the file."""

    compression_method: Union[
        Literal[tuple(AVAILABLE_ZARR_COMPRESSION_METHODS.keys())], InstanceOf[numcodecs.abc.Codec], None
    ] = Field(
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
    compression_options: Union[dict[str, Any], None] = Field(
        default=None, description="The optional parameters to use for the specified compression method."
    )
    filter_methods: Union[
        list[Union[Literal[tuple(AVAILABLE_ZARR_COMPRESSION_METHODS.keys())], InstanceOf[numcodecs.abc.Codec]]], None
    ] = Field(
        default=None,
        description=(
            "The ordered collection of filtering methods to apply to this dataset prior to compression. "
            "Each element can be either a string that matches an available method on your system, "
            "or an instantiated numcodec.Codec object."
            "Set to `None` to disable filtering."
        ),
    )
    filter_options: Union[list[dict[str, Any]], None] = Field(
        default=None, description="The optional parameters to use for each specified filter method."
    )

    def __str__(self) -> str:  # Inherited docstring from parent. noqa: D105
        string = super().__str__()
        if self.filter_methods is not None:
            string += f"\n  filter methods : {self.filter_methods}"
        if self.filter_options is not None:
            string += f"\n  filter options : {self.filter_options}"
        if self.filter_methods is not None or self.filter_options is not None:
            string += "\n"

        return string

    @model_validator(mode="before")
    def validate_filter_methods_and_options_length_match(cls, values: dict[str, Any]):
        filter_methods = values.get("filter_methods", None)
        filter_options = values.get("filter_options", None)

        if filter_methods is None and filter_options is not None:
            raise ValueError(
                f"`filter_methods` is `None` but `filter_options` is not `None` (received `{filter_options=}`)!"
            )
        elif filter_options is None:
            return values

        len_filter_methods = len(filter_methods)
        len_filter_options = len(filter_options)
        if len_filter_methods != len_filter_options:
            raise ValueError(
                f"Length mismatch between `filter_methods` ({len_filter_methods} methods specified) and "
                f"`filter_options` ({len_filter_options} options found)! `filter_methods` and `filter_options` should "
                "be the same length."
            )

        return values

    def get_data_io_kwargs(self) -> dict[str, Any]:
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
            compression_options = self.compression_options or dict()
            compressor = zarr.codec_registry[self.compression_method](**compression_options)
        if isinstance(self.compression_method, numcodecs.abc.Codec):
            compressor = self.compression_method
        elif self.compression_method is None:
            compressor = False

        return dict(chunks=self.chunk_shape, filters=filters, compressor=compressor)
