"""Base Pydantic models for the ZarrDatasetConfiguration."""

import warnings
from typing import Any, ClassVar, Literal

import zarr
from hdmf import Container
from packaging.version import Version
from pydantic import Field, InstanceOf, model_validator
from typing_extensions import Self

from ._base_dataset_io import _DEFAULT_GZIP_LEVEL, DatasetIOConfiguration

# The Zarr backend requires zarr 3, and Python 3.13 and older resolve zarr 2, where `ZarrBackendConfiguration`
# raises before any codec is built. These classes only exist in zarr 3, so under zarr 2 they stand in as `object`
# to keep this module importable.
if Version(zarr.__version__).major >= 3:
    from zarr.abc.codec import ArrayArrayCodec, BytesBytesCodec
    from zarr.codecs import BloscCodec, GzipCodec, ZstdCodec
    from zarr.codecs.numcodecs import BZ2, LZ4, LZMA, Delta, Fletcher32, JenkinsLookup3, PackBits, Shuffle, Zlib
else:
    ArrayArrayCodec = BytesBytesCodec = BloscCodec = GzipCodec = ZstdCodec = object
    BZ2 = LZ4 = LZMA = Delta = Fletcher32 = JenkinsLookup3 = PackBits = Shuffle = Zlib = object

# Split by the zarr 3 codec stage: a compression method is a bytes-to-bytes codec and goes in `compressors`, a
# filter method is an array-to-array codec and goes in `filters`. Gzip, Blosc and Zstd are the native zarr 3 codecs,
# readable by implementations without numcodecs.
AVAILABLE_ZARR_COMPRESSION_METHODS = {
    "blosc": BloscCodec,
    "bz2": BZ2,
    "gzip": GzipCodec,
    "lz4": LZ4,
    "lzma": LZMA,
    "zlib": Zlib,
    "zstd": ZstdCodec,
}

AVAILABLE_ZARR_FILTER_METHODS = {
    "delta": Delta,
}

# ======================================================================================================
# Deprecated in v0.11.0, to be removed in v0.12.0.
#
# Every codec name used to be accepted in both `compressors` and `filters`, including the value transform
# `packbits` and the checksums `fletcher32` and `jenkins_lookup3`, which are neither. Until v0.12.0 both
# fields still accept them, with a FutureWarning for a name in the wrong one, and `get_data_io_kwargs()`
# places each codec in the stage its class belongs to. `categorize` has no zarr 3 codec and is gone. At
# v0.12.0 delete this map, type `compressors` against AVAILABLE_ZARR_COMPRESSION_METHODS and `filters`
# against AVAILABLE_ZARR_FILTER_METHODS, and resolve each through its own map.
# ======================================================================================================
_ZARR_CODECS_ACCEPTED_UNTIL_V0_12 = {
    **AVAILABLE_ZARR_COMPRESSION_METHODS,
    **AVAILABLE_ZARR_FILTER_METHODS,
    "fletcher32": Fletcher32,
    "jenkins_lookup3": JenkinsLookup3,
    "packbits": PackBits,
}
# ======================================================================================================
# End of the block deprecated in v0.11.0, to be removed in v0.12.0.
# ======================================================================================================


class ZarrDatasetIOConfiguration(DatasetIOConfiguration):
    """A data model for configuring options about an object that will become a Zarr Dataset in the file."""

    # Shuffle rearranges bytes rather than compressing them, so it can never be the compression method of a
    # dataset. It is a bytes-to-bytes codec and runs in `compressors`, ahead of the compression method.
    _pure_filter_names: ClassVar[tuple[str, ...]] = ("shuffle",)

    compressors: (
        list[Literal[(*_pure_filter_names, *_ZARR_CODECS_ACCEPTED_UNTIL_V0_12.keys())] | InstanceOf[BytesBytesCodec]]
        | None
    ) = Field(
        default=["gzip"],  # TODO: would like this to be 'auto'
        description=(
            "The ordered collection of codecs to apply to this dataset after it is serialized to bytes. "
            "Each element can be either a string that matches an available method on your system, "
            "or an instantiated zarr bytes-to-bytes codec. "
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
    filters: (
        list[Literal[(*_pure_filter_names, *_ZARR_CODECS_ACCEPTED_UNTIL_V0_12.keys())] | InstanceOf[ArrayArrayCodec]]
        | None
    ) = Field(
        default=None,
        description=(
            "The ordered collection of codecs to apply to this dataset's values before it is serialized to bytes. "
            "Each element can be either a string that matches an available method on your system, "
            "or an instantiated zarr array-to-array codec. "
            "Set to `None` to disable filtering."
        ),
    )
    filter_options: list[dict[str, Any]] | None = Field(
        default=None, description="The optional parameters to use for each specified filter."
    )

    def __str__(self) -> str:  # Inherited docstring from parent. noqa: D105
        string = super().__str__()
        if self.filters is not None:
            string += f"\n  filters : {self.filters}"
        if self.filter_options is not None:
            string += f"\n  filter options : {self.filter_options}"
        if self.filters is not None or self.filter_options is not None:
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

        if any(filter_method == "shuffle" for filter_method in self.filters):
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

    # ==================================================================================================
    # Deprecated in v0.11.0, to be removed in v0.12.0. See `_ZARR_CODECS_ACCEPTED_UNTIL_V0_12`.
    # ==================================================================================================

    @model_validator(mode="after")
    def warn_on_codecs_outside_their_map(self) -> Self:
        """Accept a codec name in the field it does not belong to for one release cycle."""
        misplaced_compressors = [
            compressor
            for compressor in self.compressors or []
            if isinstance(compressor, str)
            and compressor not in (*self._pure_filter_names, *AVAILABLE_ZARR_COMPRESSION_METHODS)
        ]
        if misplaced_compressors:
            warnings.warn(
                f"Naming {misplaced_compressors} in `compressors` is deprecated and will be removed in v0.12.0. "
                f"The compression methods are {list(AVAILABLE_ZARR_COMPRESSION_METHODS)}, and the filter methods, "
                f"which belong in `filters`, are {list(AVAILABLE_ZARR_FILTER_METHODS)}.",
                FutureWarning,
                stacklevel=2,
            )

        # 'shuffle' in `filters` has its own deprecation above.
        misplaced_filters = [
            filter_method
            for filter_method in self.filters or []
            if isinstance(filter_method, str)
            and filter_method not in (*self._pure_filter_names, *AVAILABLE_ZARR_FILTER_METHODS)
        ]
        if misplaced_filters:
            warnings.warn(
                f"Naming {misplaced_filters} in `filters` is deprecated and will be removed in v0.12.0. "
                f"The filter methods are {list(AVAILABLE_ZARR_FILTER_METHODS)}, and the compression methods, "
                f"which belong in `compressors`, are {list(AVAILABLE_ZARR_COMPRESSION_METHODS)}.",
                FutureWarning,
                stacklevel=2,
            )

        return self

    # ==================================================================================================
    # End of the block deprecated in v0.11.0, to be removed in v0.12.0.
    # ==================================================================================================

    def _instantiate_codec(self, codec, codec_options: dict[str, Any] | None):
        if not isinstance(codec, str):
            return codec

        codec_options = dict(codec_options or dict())
        if codec == "gzip":
            codec_options.setdefault("level", _DEFAULT_GZIP_LEVEL)

        codec_class = Shuffle if codec == "shuffle" else _ZARR_CODECS_ACCEPTED_UNTIL_V0_12[codec]
        return codec_class(**codec_options)

    def get_data_io_kwargs(self) -> dict[str, Any]:
        filters = self.filters or []
        filter_options = self.filter_options or [None] * len(filters)
        compressors = self.compressors or []
        compressor_options = self.compressor_options or [None] * len(compressors)
        codecs = [
            self._instantiate_codec(codec, codec_options)
            for codec, codec_options in zip([*filters, *compressors], [*filter_options, *compressor_options])
        ]

        # Each codec goes to the stage its class runs in, which also places a name deprecated in the other field.
        array_codecs = [codec for codec in codecs if isinstance(codec, ArrayArrayCodec)]
        bytes_codecs = [codec for codec in codecs if isinstance(codec, BytesBytesCodec)]

        return dict(chunks=self.chunk_shape, filters=array_codecs or None, compressors=bytes_codecs or False)

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
        zarr_array = getattr(neurodata_object, dataset_name)
        compressors = list(zarr_array.compressors)
        filters = list(zarr_array.filters)

        return cls(**kwargs, compressors=compressors or None, filters=filters or None)
