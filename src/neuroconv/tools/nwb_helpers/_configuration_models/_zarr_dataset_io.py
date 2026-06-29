"""Base Pydantic models for the ZarrDatasetConfiguration."""

from typing import Any, Literal

from hdmf import Container
from pydantic import Field, InstanceOf, PositiveInt, model_validator
from typing_extensions import Self
from zarr.abc.codec import ArrayArrayCodec, BytesBytesCodec
from zarr.codecs import BloscCodec, GzipCodec, ZstdCodec
from zarr.codecs.numcodecs import BZ2, LZ4, LZMA, Shuffle, Zlib

from ._base_dataset_io import DatasetIOConfiguration

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
    "shuffle": Shuffle,
}

# Curated mapping of string names to zarr v3 ArrayArrayCodec classes for filters.
AVAILABLE_ZARR_FILTER_METHODS: dict[str, type[ArrayArrayCodec]] = {
    "delta": __import__("zarr.codecs.numcodecs", fromlist=["Delta"]).Delta,
}


class ZarrDatasetIOConfiguration(DatasetIOConfiguration):
    """A data model for configuring options about an object that will become a Zarr Dataset in the file."""

    compression_method: (
        Literal[tuple(AVAILABLE_ZARR_COMPRESSION_METHODS.keys())] | InstanceOf[BytesBytesCodec] | None
    ) = Field(
        default="gzip",
        description=(
            "The specified compression method to apply to this dataset. "
            "Can be either a string that matches an available method on your system, "
            "or an instantiated zarr BytesBytesCodec object (e.g. zarr.codecs.GzipCodec(level=5)). "
            "Set to `None` to disable compression."
        ),
    )
    compression_options: dict[str, Any] | None = Field(
        default=None, description="The optional parameters to use for the specified compression method."
    )
    filter_methods: list[Literal[tuple(AVAILABLE_ZARR_FILTER_METHODS.keys())] | InstanceOf[ArrayArrayCodec]] | None = (
        Field(
            default=None,
            description=(
                "The ordered collection of filtering methods to apply to this dataset prior to compression. "
                "Each element can be either a string that matches an available method on your system, "
                "or an instantiated zarr ArrayArrayCodec object (e.g. zarr.codecs.numcodecs.Delta()). "
                "Set to `None` to disable filtering."
            ),
        )
    )
    filter_options: list[dict[str, Any]] | None = Field(
        default=None, description="The optional parameters to use for each specified filter method."
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
        if self.filter_methods is not None:
            string += f"\n  filter methods : {self.filter_methods}"
        if self.filter_options is not None:
            string += f"\n  filter options : {self.filter_options}"
        if self.filter_methods is not None or self.filter_options is not None:
            string += "\n"
        if self.shard_shape is not None:
            string += f"\n  shard shape : {self.shard_shape}\n"

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

    def get_data_io_kwargs(self) -> dict[str, Any]:
        filters = None
        if self.filter_methods:
            filters = list()
            all_filter_options = self.filter_options or [dict() for _ in self.filter_methods]
            for filter_method, filter_options in zip(self.filter_methods, all_filter_options):
                if isinstance(filter_method, str):
                    filters.append(AVAILABLE_ZARR_FILTER_METHODS[filter_method](**filter_options))
                elif isinstance(filter_method, ArrayArrayCodec):
                    filters.append(filter_method)

        if isinstance(self.compression_method, str):
            compression_options = self.compression_options or dict()
            compressor = AVAILABLE_ZARR_COMPRESSION_METHODS[self.compression_method](**compression_options)
        elif isinstance(self.compression_method, BytesBytesCodec):
            compressor = self.compression_method
        elif self.compression_method is None:
            compressor = False

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
        dataset = getattr(neurodata_object, dataset_name)
        # zarr v3: .compressors is a tuple of BytesBytesCodec; take first or None
        compressors = dataset.compressors
        compression_method = compressors[0] if compressors else None
        # zarr v3: .filters is a tuple of ArrayArrayCodec
        filters = dataset.filters
        filter_methods = list(filters) if filters else None
        return cls(
            **kwargs,
            compression_method=compression_method,
            filter_methods=filter_methods,
        )
