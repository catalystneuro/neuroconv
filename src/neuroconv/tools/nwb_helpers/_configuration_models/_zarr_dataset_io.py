"""Base Pydantic models for the ZarrDatasetConfiguration."""

from typing import Any, Literal

import numcodecs
import zarr
from hdmf import Container
from pydantic import Field, InstanceOf, model_validator
from typing_extensions import Self

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
        "pcodec",  # is erroneously imported before numcodecs 0.15, see https://numcodecs.readthedocs.io/en/stable/release.html?utm_source=chatgpt.com#id9
    )
)

# Forbidding lossy codecs for now, but they could be allowed in the future with warnings?
# (Users can always initialize and pass explicitly via code)
_available_zarr_codecs = set(_base_zarr_codecs - _lossy_zarr_codecs - _excluded_zarr_codecs)

AVAILABLE_ZARR_COMPRESSION_METHODS = {
    codec_name: zarr.codec_registry[codec_name] for codec_name in _available_zarr_codecs
}


class ZarrDatasetIOConfiguration(DatasetIOConfiguration):
    """A data model for configuring options about an object that will become a Zarr Dataset in the file."""

    compressors: (
        list[Literal[tuple(AVAILABLE_ZARR_COMPRESSION_METHODS.keys())] | InstanceOf[numcodecs.abc.Codec]] | None
    ) = Field(
        default=["gzip"],  # TODO: would like this to be 'auto'
        description=(
            "The ordered collection of codecs to apply to this dataset after it is serialized to bytes. "
            "Each element can be either a string that matches an available method on your system, "
            "or an instantiated numcodec.Codec object. "
            "A filter such as 'shuffle' composes with a compression method rather than replacing one, so both "
            "live in this list. "
            "Set to `None` to disable compression."
        ),
    )
    # TODO: actually provide better schematic rendering of options. Only support defaults in GUIDE for now.
    # Looks like they'll have to be hand-typed however... Can try parsing the numpy docstrings - no annotation typing.
    compressor_options: list[dict[str, Any] | None] | None = Field(
        default=None, description="The optional parameters to use for each specified compressor."
    )
    filter_methods: (
        list[Literal[tuple(AVAILABLE_ZARR_COMPRESSION_METHODS.keys())] | InstanceOf[numcodecs.abc.Codec]] | None
    ) = Field(
        default=None,
        description=(
            "The ordered collection of filtering methods to apply to this dataset prior to compression. "
            "Each element can be either a string that matches an available method on your system, "
            "or an instantiated numcodec.Codec object."
            "Set to `None` to disable filtering."
        ),
    )
    filter_options: list[dict[str, Any]] | None = Field(
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

    @model_validator(mode="after")
    def validate_compressors_and_options_length_match(self) -> Self:
        if self.compressors is None and self.compressor_options is not None:
            raise ValueError(
                "`compressors` is `None` but `compressor_options` is not `None` "
                f"(received `{self.compressor_options=}`)!"
            )
        if self.compressor_options is None:
            return self

        if len(self.compressors) != len(self.compressor_options):
            raise ValueError(
                f"Length mismatch between `compressors` ({len(self.compressors)} specified) and "
                f"`compressor_options` ({len(self.compressor_options)} found)! `compressors` and "
                "`compressor_options` should be the same length."
            )

        return self

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

    def _instantiate_codec(self, codec, codec_options: dict[str, Any] | None):
        if isinstance(codec, numcodecs.abc.Codec):
            return codec

        codec_options = dict(codec_options or dict())
        # `numcodecs.Shuffle` defaults `elementsize` to 4 whatever the dtype is, so on anything wider it
        # transposes the wrong byte planes and recovers almost nothing. The configuration knows the dtype.
        # TODO: remove once hdmf-zarr moves off `zarr<3.0`, where `Shuffle.evolve_from_array_spec` fills
        # `elementsize` from the array dtype upstream.
        if codec == "shuffle" and "elementsize" not in codec_options:
            codec_options["elementsize"] = self.dtype.itemsize

        return zarr.codec_registry[codec](**codec_options)

    def get_data_io_kwargs(self) -> dict[str, Any]:
        filters = None
        if self.filter_methods:
            all_filter_options = self.filter_options or [dict() for _ in self.filter_methods]
            filters = [
                self._instantiate_codec(filter_method, filter_options)
                for filter_method, filter_options in zip(self.filter_methods, all_filter_options)
            ]

        # Zarr v2 has a single compressor slot, so every other entry of `compressors` has to ride in `filters`.
        # TODO: remove this split once hdmf-zarr moves off `zarr<3.0`, where `compressors` is itself an ordered list.
        compressors = self.compressors or []
        compressor_options = self.compressor_options or [None] * len(compressors)
        compression_index = self._compressor_index()

        for index, (codec, codec_options) in enumerate(zip(compressors, compressor_options)):
            if index == compression_index:
                continue
            filters = (filters or []) + [self._instantiate_codec(codec, codec_options)]

        if compression_index is None:
            compressor = False
        else:
            compressor = self._instantiate_codec(compressors[compression_index], compressor_options[compression_index])

        return dict(chunks=self.chunk_shape, filters=filters, compressor=compressor)

    @classmethod
    def from_neurodata_object_with_existing(
        cls,
        neurodata_object: Container,
        dataset_name: Literal["data", "timestamps"],
    ) -> Self:
        """
        Construct a ZarrDatasetIOConfiguration from existing dataset settings.

        Parameters
        ----------
        neurodata_object : hdmf.Container
            The neurodata object containing the field that has been read from disk.
        dataset_name : "data" or "timestamps"
            The name of the field that corresponds to the dataset on disk.

        Returns
        -------
        Self
            A ZarrDatasetIOConfiguration instance with settings matching the existing dataset.
        """
        kwargs = cls.get_kwargs_from_neurodata_object(
            neurodata_object=neurodata_object,
            dataset_name=dataset_name,
        )
        compression_method = getattr(neurodata_object, dataset_name).compressor
        filter_methods = getattr(neurodata_object, dataset_name).filters
        return cls(
            **kwargs,
            compressors=None if compression_method is None else [compression_method],
            filter_methods=filter_methods,
        )
