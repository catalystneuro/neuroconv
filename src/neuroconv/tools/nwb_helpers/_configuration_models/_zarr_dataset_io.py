"""Base Pydantic models for the ZarrDatasetConfiguration."""

import warnings
from typing import Any, ClassVar, Literal

import numcodecs
import zarr
from hdmf import Container
from numcodecs import Shuffle
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
        "shuffle",  # not a compression method; reachable as an entry of `compressors`
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

    # Shuffle rearranges bytes rather than compressing them, so it can never be the compression method of a
    # dataset. Zarr v2 has nowhere but `filters` to store it, which is where `get_data_io_kwargs()` puts it.
    _pure_filter_names: ClassVar[tuple[str, ...]] = ("shuffle",)

    compressors: (
        list[
            Literal[(*_pure_filter_names, *AVAILABLE_ZARR_COMPRESSION_METHODS.keys())] | InstanceOf[numcodecs.abc.Codec]
        ]
        | None
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
    filters: (
        list[
            Literal[(*_pure_filter_names, *AVAILABLE_ZARR_COMPRESSION_METHODS.keys())] | InstanceOf[numcodecs.abc.Codec]
        ]
        | None
    ) = Field(
        default=None,
        description=(
            "The ordered collection of codecs to apply to this dataset's values before it is serialized to bytes. "
            "Each element can be either a string that matches an available method on your system, "
            "or an instantiated numcodec.Codec object."
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
        if self.filters:
            all_filter_options = self.filter_options or [dict() for _ in self.filters]
            filters = [
                self._instantiate_codec(filter_method, filter_options)
                for filter_method, filter_options in zip(self.filters, all_filter_options)
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
        filters = list(getattr(neurodata_object, dataset_name).filters or [])

        # Shuffle lives in `compressors` in this model and in `filters` on disk, since Zarr v2 has nowhere
        # else to put it, so it is moved back here. Without this a file this library wrote reports a
        # different configuration than the one that wrote it.
        shuffle_methods = [filter_method for filter_method in filters if isinstance(filter_method, Shuffle)]
        filters = [filter_method for filter_method in filters if not isinstance(filter_method, Shuffle)]

        compressors = ["shuffle" for _ in shuffle_methods]
        compressor_options = [dict(elementsize=shuffle.elementsize) for shuffle in shuffle_methods]
        if compression_method is not None:
            compressors.append(compression_method)
            compressor_options.append(None)

        return cls(
            **kwargs,
            compressors=compressors or None,
            compressor_options=compressor_options if any(compressor_options) else None,
            filters=filters or None,
        )
