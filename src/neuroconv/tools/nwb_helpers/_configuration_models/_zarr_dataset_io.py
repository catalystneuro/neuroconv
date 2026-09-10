"""Base Pydantic models for the ZarrDatasetConfiguration."""

import warnings
from typing import Any, ClassVar, Literal

from hdmf import Container
from pydantic import Field, InstanceOf, PositiveInt, model_validator
from typing_extensions import Self
from zarr.abc.codec import ArrayArrayCodec, BytesBytesCodec
from zarr.codecs import BloscCodec, GzipCodec, ZstdCodec
from zarr.codecs.numcodecs import BZ2, LZ4, LZMA, Shuffle, Zlib

from ._base_dataset_io import _DEFAULT_GZIP_LEVEL, DatasetIOConfiguration

# Curated mapping of string names to zarr v3 BytesBytesCodec classes.
# Prefer native zarr codecs where available; fall back to numcodecs wrappers otherwise.
AVAILABLE_ZARR_COMPRESSION_METHODS: dict[str, type[BytesBytesCodec]] = {
    "gzip": GzipCodec,
    "blosc": BloscCodec,
    "zstd": ZstdCodec,
    "bz2": BZ2,
    "lzma": LZMA,
    "zlib": Zlib,
    "lz4": LZ4,
}

# Curated mapping of string names to zarr v3 ArrayArrayCodec classes for filters.
AVAILABLE_ZARR_FILTER_METHODS: dict[str, type[ArrayArrayCodec]] = {
    "delta": __import__("zarr.codecs.numcodecs", fromlist=["Delta"]).Delta,
}


class ZarrDatasetIOConfiguration(DatasetIOConfiguration):
    """A data model for configuring options about an object that will become a Zarr Dataset in the file."""

    # Shuffle rearranges bytes rather than compressing them, so it can never be the compression method of a
    # dataset. It is listed separately here so _compressor_index() can skip it when finding the main compressor.
    _pure_filter_names: ClassVar[tuple[str, ...]] = ("shuffle",)

    compressors: (
        list[Literal[(*_pure_filter_names, *AVAILABLE_ZARR_COMPRESSION_METHODS.keys())] | InstanceOf[BytesBytesCodec]]
        | None
    ) = Field(
        default=["gzip"],
        description=(
            "The ordered collection of codecs to apply to this dataset after it is serialized to bytes. "
            "Each element can be either a string that matches an available method on your system, "
            "or an instantiated zarr BytesBytesCodec object (e.g. zarr.codecs.GzipCodec(level=5)). "
            "A filter such as 'shuffle' composes with a compression method rather than replacing one, so both "
            "live in this list. "
            "Set to `None` to disable compression."
        ),
    )
    compressor_options: list[dict[str, Any] | None] | None = Field(
        default=None, description="The optional parameters to use for each specified compressor."
    )
    filters: list[Literal[tuple(AVAILABLE_ZARR_FILTER_METHODS.keys())] | InstanceOf[ArrayArrayCodec]] | None = Field(
        default=None,
        description=(
            "The ordered collection of codecs to apply to this dataset's values before it is serialized to bytes. "
            "Each element can be either a string that matches an available method on your system, "
            "or an instantiated zarr ArrayArrayCodec object (e.g. zarr.codecs.numcodecs.Delta()). "
            "Set to `None` to disable filtering."
        ),
    )
    filter_options: list[dict[str, Any]] | None = Field(
        default=None, description="The optional parameters to use for each specified filter."
    )
    shard_shape: tuple[PositiveInt, ...] | None = Field(
        default=None,
        description=(
            "The specified shape to use for sharding the dataset. "
            "Each shard contains one or more chunks. When set, each axis must be >= the corresponding "
            "chunk_shape axis, and chunk axes must evenly divide shard axes. "
            "Set to `None` to disable sharding (default)."
        ),
    )

    def __str__(self) -> str:  # Inherited docstring from parent. noqa: D105
        string = super().__str__()
        if self.filters is not None:
            string += f"\n  filters : {self.filters}"
        if self.filter_options is not None:
            string += f"\n  filter options : {self.filter_options}"
        if self.filters is not None or self.filter_options is not None:
            string += "\n"
        if self.shard_shape is not None:
            string += f"\n  shard shape : {self.shard_shape}\n"

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
    def validate_filters_and_options_length_match(cls, values: dict[str, Any]):
        filters = values.get("filters", None)
        filter_options = values.get("filter_options", None)

        if filters is None and filter_options is not None:
            raise ValueError(f"`filters` is `None` but `filter_options` is not `None` (received `{filter_options=}`)!")
        elif filter_options is None:
            return values

        len_filters = len(filters)
        len_filter_options = len(filter_options)
        if len_filters != len_filter_options:
            raise ValueError(
                f"Length mismatch between `filters` ({len_filters} specified) and "
                f"`filter_options` ({len_filter_options} options found)! `filters` and `filter_options` should "
                "be the same length."
            )

        return values

    @model_validator(mode="after")
    def validate_shard_shape(self) -> Self:
        if self.shard_shape is None or self.chunk_shape is None:
            return self

        if len(self.shard_shape) != len(self.chunk_shape):
            raise ValueError(
                f"Length of shard_shape ({len(self.shard_shape)}) does not match "
                f"chunk_shape ({len(self.chunk_shape)}) for dataset at location '{self.location_in_file}'!"
            )

        if any(shard_axis < chunk_axis for shard_axis, chunk_axis in zip(self.shard_shape, self.chunk_shape)):
            raise ValueError(
                f"Some dimensions of the shard_shape {self.shard_shape} are smaller than the "
                f"chunk_shape {self.chunk_shape} for dataset at location '{self.location_in_file}'!"
            )

        if any(shard_axis % chunk_axis != 0 for shard_axis, chunk_axis in zip(self.shard_shape, self.chunk_shape)):
            raise ValueError(
                f"Some dimensions of the chunk_shape {self.chunk_shape} do not evenly divide the "
                f"shard_shape {self.shard_shape} for dataset at location '{self.location_in_file}'!"
            )

        return self

    # ==================================================================================================
    # Deprecated in v0.10.2, to be removed in v0.12.0.
    #
    # Two things are deprecated here, both of them about `filters` saying what zarr says.
    #
    # `filter_methods` and `filters` are the same field under two names, and the second is the one
    # `zarr.Array` uses for the codecs applied to a dataset's values.
    #
    # `filters` holds the codecs that transform values, such as `delta`. `shuffle` transforms the bytes
    # those values serialize to, which is a different slot in the vocabulary this model speaks, and since
    # the `timestamps` default puts it in `compressors` a dataset that names it in both applies it twice.
    #
    # Deleting this block at v0.12.0 leaves `filters` under one name, holding value codecs alone.
    # ==================================================================================================

    _FILTER_METHODS_DEPRECATION_MESSAGE: ClassVar[str] = (
        "`filter_methods` is deprecated and will be removed in v0.12.0. Use `filters` instead, which is what "
        "`zarr.Array` calls the codecs applied to a dataset's values."
    )

    @property
    def filter_methods(self):
        """
        The codecs applied to this dataset's values.

        .. deprecated:: 0.10.2
            `filter_methods` is deprecated and will be removed in v0.12.0. Use `filters` instead.
        """
        warnings.warn(self._FILTER_METHODS_DEPRECATION_MESSAGE, FutureWarning, stacklevel=2)
        return self.filters

    @filter_methods.setter
    def filter_methods(self, filter_methods) -> None:
        warnings.warn(self._FILTER_METHODS_DEPRECATION_MESSAGE, FutureWarning, stacklevel=2)
        self.filters = filter_methods

    @model_validator(mode="before")
    def translate_deprecated_filter_methods(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Accept the deprecated `filter_methods` spelling for one release cycle."""
        if not isinstance(values, dict) or "filter_methods" not in values:
            return values
        if "filters" in values:
            raise ValueError(
                "Both the deprecated `filter_methods` and the new `filters` were specified. Use only `filters`."
            )

        warnings.warn(cls._FILTER_METHODS_DEPRECATION_MESSAGE, FutureWarning, stacklevel=2)
        values["filters"] = values.pop("filter_methods")
        return values

    @model_validator(mode="after")
    def warn_on_shuffle_in_filters(self) -> Self:
        """Accept the deprecated spelling of shuffle as a filter method for one release cycle."""
        if not self.filters:
            return self

        if any(filter_method == "shuffle" or isinstance(filter_method, Shuffle) for filter_method in self.filters):
            warnings.warn(
                "Naming 'shuffle' in `filters` is deprecated and will be removed in v0.12.0. It rearranges "
                "the serialized bytes rather than the values, so it belongs in `compressors`, as in "
                '`compressors=["shuffle", "gzip"]`.',
                FutureWarning,
                stacklevel=2,
            )

        return self

    # ==================================================================================================
    # End of the block deprecated in v0.10.2, to be removed in v0.12.0.
    # ==================================================================================================

    def _instantiate_codec(self, codec, codec_options: dict[str, Any] | None):
        if isinstance(codec, (BytesBytesCodec, ArrayArrayCodec)):
            return codec

        codec_options = dict(codec_options or {})
        if codec == "gzip":
            codec_options.setdefault("level", _DEFAULT_GZIP_LEVEL)

        # Shuffle defaults `elementsize` to 4 regardless of dtype, so on wider types it transposes the
        # wrong byte planes. The configuration knows the dtype so we fill it in here.
        if codec == "shuffle" and "elementsize" not in codec_options:
            codec_options["elementsize"] = self.dtype.itemsize

        if codec == "shuffle":
            return Shuffle(**codec_options)

        if codec in AVAILABLE_ZARR_FILTER_METHODS:
            return AVAILABLE_ZARR_FILTER_METHODS[codec](**codec_options)

        return AVAILABLE_ZARR_COMPRESSION_METHODS[codec](**codec_options)

    def get_data_io_kwargs(self) -> dict[str, Any]:
        filters = None
        if self.filters:
            all_filter_options = self.filter_options or [dict() for _ in self.filters]
            filters = [
                self._instantiate_codec(filter_method, filter_options)
                for filter_method, filter_options in zip(self.filters, all_filter_options)
            ]

        # hdmf-zarr currently uses a zarr v2-style interface (single compressor + filters list).
        # Non-main-compressors (like shuffle) ride in filters until hdmf-zarr adopts the zarr v3 pipeline API.
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

        return dict(chunks=self.chunk_shape, filters=filters, compressor=compressor, shards=self.shard_shape)

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
        dataset = getattr(neurodata_object, dataset_name)
        # zarr v3: .compressors is a tuple of BytesBytesCodec; .filters is a tuple of ArrayArrayCodec
        compressors_on_disk = dataset.compressors
        filters_on_disk = dataset.filters

        return cls(
            **kwargs,
            compressors=list(compressors_on_disk) if compressors_on_disk else None,
            filters=list(filters_on_disk) if filters_on_disk else None,
        )
