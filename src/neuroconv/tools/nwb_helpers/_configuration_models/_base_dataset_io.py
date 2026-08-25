"""Base Pydantic models for DatasetInfo and DatasetConfiguration."""

import math
import warnings
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Literal

import h5py
import numcodecs
import numpy as np
import zarr
from hdmf import Container
from hdmf.build.builders import (
    BaseBuilder,
)
from hdmf.data_utils import GenericDataChunkIterator as HDMFGenericDataChunkIterator
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    InstanceOf,
    PositiveInt,
    model_validator,
)
from pynwb import NWBFile
from pynwb.ecephys import ElectricalSeries
from pynwb.image import ImageSeries
from typing_extensions import Self

from neuroconv.tools.hdmf import get_full_data_shape
from neuroconv.tools.iterative_write import get_electrical_series_chunk_shape
from neuroconv.utils.str_utils import human_readable_size

from ._pydantic_pure_json_schema_generator import PureJSONSchemaGenerator
from ...hdmf import SliceableDataChunkIterator


def _recursively_find_location_in_memory_nwbfile(current_location: str, neurodata_object: Container) -> str:
    """
    Method for determining the location of a neurodata object within an in-memory NWBFile object.

    Distinct from methods from other packages, such as the NWB Inspector, which rely on such files being read from disk.
    """
    parent = neurodata_object.parent
    if isinstance(parent, NWBFile):
        # Items in defined top-level places like acquisition, intervals, etc. do not act as 'containers'
        # in that they do not set the `.parent` attribute; ask if object is in their in-memory dictionaries instead
        for parent_field_name, parent_field_value in parent.fields.items():
            if isinstance(parent_field_value, dict) and neurodata_object.name in parent_field_value:
                return parent_field_name + "/" + neurodata_object.name + "/" + current_location
        return neurodata_object.name + "/" + current_location
    return _recursively_find_location_in_memory_nwbfile(
        current_location=neurodata_object.name + "/" + current_location, neurodata_object=parent
    )


def _find_location_in_memory_nwbfile(neurodata_object: Container, field_name: str) -> str:
    """
    More readable call for the recursive location finder for a field of a neurodata object in an in-memory NWBFile.

    The recursive method forms from the buttom-up using the initial 'current_location' of the field itself.
    """
    return _recursively_find_location_in_memory_nwbfile(current_location=field_name, neurodata_object=neurodata_object)


def _infer_dtype_of_list(list_: list[int | float | list]) -> np.dtype:
    """
    Attempt to infer the dtype of values in an arbitrarily sized and nested list.

    Relies on the ability of the numpy.array call to cast the list as an array so the 'dtype' attribute can be used.
    """
    for item in list_:
        if isinstance(item, list):
            dtype = _infer_dtype_of_list(list_=item)
            if dtype is not None:
                return dtype
        else:
            return np.array([item]).dtype

    raise ValueError("Unable to determine the dtype of values in the list.")


def _infer_dtype(dataset: h5py.Dataset | zarr.Array) -> np.dtype:
    """Attempt to infer the dtype of the contained values of the dataset."""
    if hasattr(dataset, "dtype"):
        if isinstance(dataset.dtype, list):
            data_type = np.dtype(", ".join(dataset.dtype))
            return data_type
        data_type = np.dtype(dataset.dtype)
        return data_type

    if isinstance(dataset, list):
        return _infer_dtype_of_list(list_=dataset)

    # Think more on if there is a better way to handle this fallback
    data_type = np.dtype("object")
    return data_type


class DatasetIOConfiguration(BaseModel, ABC):
    """A data model for configuring options about an object that will become a HDF5 or Zarr Dataset in the file."""

    model_config = ConfigDict(validate_assignment=True)  # Re-validate model on mutation

    # Immutable fields about the dataset
    object_id: str = Field(description="The UUID of the neurodata object containing the dataset.", frozen=True)
    location_in_file: str = Field(
        description=(
            "The location of the this dataset within the in-memory NWBFile relative to the top-level root, "
            "e.g. 'acquisition/ElectricalSeries/data'."
        ),
        frozen=True,
    )
    dataset_name: Literal["data", "timestamps"] = Field(description="The reference name of the dataset.", frozen=True)
    dtype: InstanceOf[np.dtype] = Field(description="The data type of elements of this dataset.", frozen=True)
    full_shape: tuple[int, ...] = Field(description="The maximum shape of the entire dataset.", frozen=True)

    # User specifiable fields
    chunk_shape: tuple[PositiveInt, ...] | None = Field(
        description=(
            "The specified shape to use when chunking the dataset. "
            "For optimized streaming speeds, a total size of around 10 MB is recommended."
        ),
    )
    buffer_shape: tuple[int, ...] | None = Field(
        description=(
            "The specified shape to use when iteratively loading data into memory while writing the dataset. "
            "For optimized writing speeds and minimal RAM usage, a total size of around 1 GB is recommended."
        ),
    )
    compressors: list[str | InstanceOf[h5py._hl.filters.FilterRefBase] | InstanceOf[numcodecs.abc.Codec]] | None = (
        Field(
            description=(
                "The ordered collection of codecs to apply to this dataset after it is serialized to bytes. "
                "A filter such as 'shuffle' composes with a compression method rather than replacing one, so both "
                "live in this list. Set to `None` to disable compression."
            ),
        )
    )
    compressor_options: list[dict[str, Any] | None] | None = Field(
        default=None,
        description=(
            "The optional parameters to use for each specified compressor, positionally matched to `compressors`. "
            "Use `None` for an entry that takes no parameters, such as 'shuffle'."
        ),
    )

    @property
    def full_size_in_bytes(self) -> int:
        """The size the entire source array occupies in memory."""
        return math.prod(self.full_shape) * self.dtype.itemsize

    @property
    def maximum_ram_usage_per_iteration_in_bytes(self) -> int:
        """The RAM a single iteration of the write takes, which is one buffer of the source array."""
        return math.prod(self.buffer_shape) * self.dtype.itemsize

    @property
    def disk_space_usage_per_chunk_in_bytes(self) -> int | None:
        """The uncompressed size of a single chunk, or `None` if the dataset is not chunked."""
        if self.chunk_shape is None:
            return None
        return math.prod(self.chunk_shape) * self.dtype.itemsize

    # Entries of `compressors` that this backend can only express as a filter, never as its compression
    # method. Empty by default: Zarr treats every codec alike, so the compression method is simply the
    # last entry and everything before it is a filter.
    _pure_filter_names: ClassVar[tuple[str, ...]] = ()

    def _compressor_index(self) -> int | None:
        """Index into `compressors` of the entry that is the compression method, or None if there is not one."""
        if self.compressors is None:
            return None
        for index in reversed(range(len(self.compressors))):
            compressor = self.compressors[index]
            if not (isinstance(compressor, str) and compressor in self._pure_filter_names):
                return index
        return None

    def _set_compression(self, compression_method, compression_options: dict[str, Any] | None) -> None:
        """Replace the compression method and its options, leaving any filters that compose with it in place."""
        index = self._compressor_index()

        if compression_method is None:
            if index is not None:
                compressors = list(self.compressors)
                compressors.pop(index)
                compressor_options = None if self.compressor_options is None else list(self.compressor_options)
                if compressor_options is not None:
                    compressor_options.pop(index)
                self.compressors = compressors or None
                self.compressor_options = compressor_options or None
            return

        compressors = list(self.compressors or [])
        compressor_options = list(self.compressor_options or [None] * len(compressors))
        if index is None:
            compressors.append(compression_method)
            compressor_options.append(compression_options)
        else:
            compressors[index] = compression_method
            compressor_options[index] = compression_options
        self.compressors = compressors
        self.compressor_options = (
            compressor_options if any(options is not None for options in compressor_options) else None
        )

    @abstractmethod
    def get_data_io_kwargs(self) -> dict[str, Any]:
        """
        Fetch the properly structured dictionary of input arguments.

        Should be passed directly as dynamic keyword arguments (**kwargs) into a H5DataIO or ZarrDataIO.
        """
        raise NotImplementedError

    def __str__(self) -> str:
        """
        Not overriding __repr__ as this is intended to render only when wrapped in print().

        Reason being two-fold; a standard `repr` is intended to be slightly more machine-readable / a more basic
        representation of the true object state. But then also because an iterable of these objects, such as a
        `list[DatasetConfiguration]`, would print out the nested representations, which only look good when using the
        basic `repr` (that is, this fancy string print-out does not look good when nested in another container).
        """
        string = (
            f"\n{self.location_in_file}"
            f"\n{'-' * len(self.location_in_file)}"
            f"\n  dtype : {self.dtype}"
            f"\n  full shape of source array : {self.full_shape}"
            f"\n  full size of source array : {human_readable_size(self.full_size_in_bytes)}"
            "\n"
            f"\n  buffer shape : {self.buffer_shape}"
            f"\n  expected RAM usage : {human_readable_size(self.maximum_ram_usage_per_iteration_in_bytes)}"
            "\n"
        )
        if self.chunk_shape is not None:
            string += (
                f"\n  chunk shape : {self.chunk_shape}"
                f"\n  disk space usage per chunk : {human_readable_size(self.disk_space_usage_per_chunk_in_bytes)}"
                "\n"
            )
        if self.compressors is not None:
            string += f"\n  compressors : {self.compressors}"
        if self.compressor_options is not None:
            string += f"\n  compressor options : {self.compressor_options}"
        if self.compressors is not None or self.compressor_options is not None:
            string += "\n"
        # TODO: would be cool to include estimate of ratio too (determined via stub file perhaps?)

        return string

    @model_validator(mode="before")
    def validate_all_shapes(cls, values: dict[str, Any]) -> dict[str, Any]:
        location_in_file = values["location_in_file"]
        dataset_name = values["dataset_name"]

        assert (
            dataset_name == location_in_file.split("/")[-1]
        ), f"The `dataset_name` ({dataset_name}) does not match the end of the `location_in_file` ({location_in_file})!"

        full_shape = values["full_shape"]
        chunk_shape = values["chunk_shape"] if values["chunk_shape"] is not None else full_shape
        buffer_shape = values["buffer_shape"] if values["buffer_shape"] is not None else full_shape

        if any(chunk_axis <= 0 for chunk_axis in chunk_shape):
            raise ValueError(
                f"Some dimensions of the {chunk_shape=} are less than or equal to zero for dataset at "
                f"location '{location_in_file}'!"
            )

        # If the buffer shape is None skip the rest of the checks
        if buffer_shape is None:
            return values

        if len(chunk_shape) != len(buffer_shape):
            raise ValueError(
                f"{len(chunk_shape)=} does not match {len(buffer_shape)=} for dataset at location '{location_in_file}'!"
            )

        if len(buffer_shape) != len(full_shape):
            raise ValueError(
                f"{len(buffer_shape)=} does not match {len(full_shape)=} for dataset at location '{location_in_file}'!"
            )
        if any(buffer_axis <= 0 for buffer_axis in buffer_shape):
            raise ValueError(
                f"Some dimensions of the {buffer_shape=} are less than or equal to zero for dataset at "
                f"location '{location_in_file}'!"
            )

        if any(chunk_axis > buffer_axis for chunk_axis, buffer_axis in zip(chunk_shape, buffer_shape)):
            raise ValueError(
                f"Some dimensions of the {chunk_shape=} exceed the {buffer_shape=} for dataset at "
                f"location '{location_in_file}'!"
            )

        if any(buffer_axis > full_axis for buffer_axis, full_axis in zip(buffer_shape, full_shape)):
            raise ValueError(
                f"Some dimensions of the {buffer_shape=} exceed the {full_shape=} for dataset at "
                f"location '{location_in_file}'!"
            )

        if any(
            buffer_axis % chunk_axis != 0
            for chunk_axis, buffer_axis, full_axis in zip(chunk_shape, buffer_shape, full_shape)
            if buffer_axis != full_axis
        ):
            raise ValueError(
                f"Some dimensions of the {chunk_shape=} do not evenly divide the {buffer_shape=} for dataset at "
                f"location '{location_in_file}'!"
            )

        return values

    # Pydantic models have several API calls for retrieving the schema - override all of them to work
    @classmethod
    def schema(cls, **kwargs) -> dict[str, Any]:
        return cls.model_json_schema(**kwargs)

    @classmethod
    def schema_json(cls, **kwargs) -> dict[str, Any]:
        return cls.model_json_schema(**kwargs)

    @classmethod
    def model_json_schema(cls, **kwargs) -> dict[str, Any]:
        assert "mode" not in kwargs, "The 'mode' of this method is fixed to be 'validation' and cannot be changed."
        assert "schema_generator" not in kwargs, "The 'schema_generator' of this method cannot be changed."
        return super().model_json_schema(mode="validation", schema_generator=PureJSONSchemaGenerator, **kwargs)

    @classmethod
    def from_neurodata_object(
        cls,
        neurodata_object: Container,
        dataset_name: Literal["data", "timestamps"],
        builder: BaseBuilder | None = None,
    ) -> Self:
        """
        Construct an instance of a DatasetIOConfiguration for a dataset in a neurodata object in an NWBFile.

        Parameters
        ----------
        neurodata_object : hdmf.Container
            The neurodata object containing the field that will become a dataset when written to disk.
        dataset_name : "data" or "timestamps"
            The name of the field that will become a dataset when written to disk.
            Some neurodata objects can have multiple such fields, such as `pynwb.TimeSeries` which can have both `data`
            and `timestamps`, each of which can be configured separately.
        builder : hdmf.build.builders.BaseBuilder, optional
            The builder object that would be used to construct the NWBFile object. If None, the dataset is assumed to
            NOT have a compound dtype.

        .. deprecated:: 0.8.4
            The `from_neurodata_object` method is deprecated and will be removed on or after June 2026.
            Use `from_neurodata_object_with_defaults` or `from_neurodata_object_with_existing` instead.
        """
        import warnings

        warnings.warn(
            "The 'from_neurodata_object' method is deprecated and will be removed on or after June 2026. "
            "Use 'from_neurodata_object_with_defaults' or 'from_neurodata_object_with_existing' instead.",
            FutureWarning,
            stacklevel=2,
        )
        location_in_file = _find_location_in_memory_nwbfile(neurodata_object=neurodata_object, field_name=dataset_name)
        candidate_dataset = getattr(neurodata_object, dataset_name)
        full_shape = get_full_data_shape(dataset=candidate_dataset, location_in_file=location_in_file, builder=builder)
        dtype = _infer_dtype(dataset=candidate_dataset)

        if isinstance(candidate_dataset, HDMFGenericDataChunkIterator):
            chunk_shape = candidate_dataset.chunk_shape
            buffer_shape = candidate_dataset.buffer_shape
            compression_method = "gzip"

        elif isinstance(neurodata_object, ElectricalSeries) and dataset_name == "data":

            number_of_frames = candidate_dataset.shape[0]
            number_of_channels = candidate_dataset.shape[1]
            dtype = candidate_dataset.dtype

            chunk_shape = get_electrical_series_chunk_shape(
                number_of_channels=number_of_channels, number_of_frames=number_of_frames, dtype=dtype
            )

            buffer_shape = None  # This is the non-iterative path
            compression_method = "gzip"

        elif isinstance(neurodata_object, ImageSeries) and dataset_name == "data":
            from ....tools.iterative_write import (
                get_image_series_chunk_shape,
            )

            num_samples = candidate_dataset.shape[0]
            sample_shape = candidate_dataset.shape[1:]

            chunk_shape = get_image_series_chunk_shape(
                num_samples=num_samples,
                sample_shape=sample_shape,
                dtype=dtype,
            )
            buffer_shape = None  # This is the non-iterative path
            compression_method = "gzip"

        elif dtype != np.dtype("object"):
            chunk_shape = SliceableDataChunkIterator.estimate_default_chunk_shape(
                chunk_mb=10.0, maxshape=full_shape, dtype=np.dtype(dtype)
            )
            buffer_shape = SliceableDataChunkIterator.estimate_default_buffer_shape(
                buffer_gb=0.5,
                chunk_shape=chunk_shape,
                maxshape=full_shape,
                dtype=np.dtype(dtype),
            )
            compression_method = "gzip"
        elif dtype == np.dtype("object"):  # Unclear what default chunking/compression should be for compound objects
            # pandas reads in strings as objects by default: https://pandas.pydata.org/docs/user_guide/text.html
            all_elements_are_strings = all([isinstance(element, str) for element in candidate_dataset[:].flat])
            if all_elements_are_strings:
                dtype = np.array([element for element in candidate_dataset[:].flat]).dtype
                chunk_shape = SliceableDataChunkIterator.estimate_default_chunk_shape(
                    chunk_mb=10.0, maxshape=full_shape, dtype=dtype
                )
                buffer_shape = SliceableDataChunkIterator.estimate_default_buffer_shape(
                    buffer_gb=0.5, chunk_shape=chunk_shape, maxshape=full_shape, dtype=dtype
                )
                compression_method = "gzip"
            else:
                raise NotImplementedError(
                    f"Unable to create a `DatasetIOConfiguration` for the dataset at '{location_in_file}'"
                    f"for neurodata object '{neurodata_object}' of type '{type(neurodata_object)}'!"
                )
                # TODO: Add support for compound objects with non-string elements
                # chunk_shape = full_shape  # validate_all_shapes fails if chunk_shape or buffer_shape is None
                # buffer_shape = full_shape
                # compression_method = None
                # warnings.warn(
                #     f"Default chunking and compression options for compound objects are not optimized. "
                #     f"Consider manually specifying DatasetIOConfiguration for dataset at '{location_in_file}'."
                # )

        return cls(
            object_id=neurodata_object.object_id,
            object_name=neurodata_object.name,
            location_in_file=location_in_file,
            dataset_name=dataset_name,
            full_shape=full_shape,
            dtype=dtype,
            chunk_shape=chunk_shape,
            buffer_shape=buffer_shape,
            compressors=None if compression_method is None else [compression_method],
        )

    @classmethod
    def from_neurodata_object_with_defaults(
        cls,
        neurodata_object: Container,
        dataset_name: Literal["data", "timestamps"],
        builder: BaseBuilder | None = None,
    ) -> Self:
        """
        Construct an instance of a DatasetIOConfiguration with default settings for a dataset in a neurodata object in an NWBFile.

        Parameters
        ----------
        neurodata_object : hdmf.Container
            The neurodata object containing the field that will become a dataset when written to disk.
        dataset_name : "data" or "timestamps"
            The name of the field that will become a dataset when written to disk.
            Some neurodata objects can have multiple such fields, such as `pynwb.TimeSeries` which can have both `data`
            and `timestamps`, each of which can be configured separately.
        builder : hdmf.build.builders.BaseBuilder, optional
            The builder object that would be used to construct the NWBFile object. If None, the dataset is assumed to
            NOT have a compound dtype.
        """
        location_in_file = _find_location_in_memory_nwbfile(neurodata_object=neurodata_object, field_name=dataset_name)
        candidate_dataset = getattr(neurodata_object, dataset_name)
        full_shape = get_full_data_shape(dataset=candidate_dataset, location_in_file=location_in_file, builder=builder)
        dtype = _infer_dtype(dataset=candidate_dataset)

        if isinstance(candidate_dataset, HDMFGenericDataChunkIterator):
            chunk_shape = candidate_dataset.chunk_shape
            buffer_shape = candidate_dataset.buffer_shape
            compression_method = "gzip"

        elif isinstance(neurodata_object, ElectricalSeries) and dataset_name == "data":

            number_of_frames = candidate_dataset.shape[0]
            number_of_channels = candidate_dataset.shape[1]
            dtype = candidate_dataset.dtype

            chunk_shape = get_electrical_series_chunk_shape(
                number_of_channels=number_of_channels, number_of_frames=number_of_frames, dtype=dtype
            )

            buffer_shape = full_shape
            compression_method = "gzip"

        elif isinstance(neurodata_object, ImageSeries) and dataset_name == "data":
            from ....tools.iterative_write import (
                get_image_series_chunk_shape,
            )

            num_samples = candidate_dataset.shape[0]
            sample_shape = candidate_dataset.shape[1:]

            chunk_shape = get_image_series_chunk_shape(
                num_samples=num_samples,
                sample_shape=sample_shape,
                dtype=dtype,
            )
            buffer_shape = full_shape
            compression_method = "gzip"

        elif dtype != np.dtype("object"):
            chunk_shape = SliceableDataChunkIterator.estimate_default_chunk_shape(
                chunk_mb=10.0, maxshape=full_shape, dtype=np.dtype(dtype)
            )
            buffer_shape = SliceableDataChunkIterator.estimate_default_buffer_shape(
                buffer_gb=0.5,
                chunk_shape=chunk_shape,
                maxshape=full_shape,
                dtype=np.dtype(dtype),
            )
            compression_method = "gzip"
        elif dtype == np.dtype("object"):  # Unclear what default chunking/compression should be for compound objects
            # pandas reads in strings as objects by default: https://pandas.pydata.org/docs/user_guide/text.html
            all_elements_are_strings = all([isinstance(element, str) for element in candidate_dataset[:].flat])
            if all_elements_are_strings:
                dtype = np.array([element for element in candidate_dataset[:].flat]).dtype
                chunk_shape = SliceableDataChunkIterator.estimate_default_chunk_shape(
                    chunk_mb=10.0, maxshape=full_shape, dtype=dtype
                )
                buffer_shape = SliceableDataChunkIterator.estimate_default_buffer_shape(
                    buffer_gb=0.5, chunk_shape=chunk_shape, maxshape=full_shape, dtype=dtype
                )
                compression_method = "gzip"
            else:
                raise NotImplementedError(
                    f"Unable to create a `DatasetIOConfiguration` for the dataset at '{location_in_file}'"
                    f"for neurodata object '{neurodata_object}' of type '{type(neurodata_object)}'!"
                )
                # TODO: Add support for compound objects with non-string elements
                # chunk_shape = full_shape  # validate_all_shapes fails if chunk_shape or buffer_shape is None
                # buffer_shape = full_shape
                # compression_method = None
                # warnings.warn(
                #     f"Default chunking and compression options for compound objects are not optimized. "
                #     f"Consider manually specifying DatasetIOConfiguration for dataset at '{location_in_file}'."
                # )

        return cls(
            object_id=neurodata_object.object_id,
            object_name=neurodata_object.name,
            location_in_file=location_in_file,
            dataset_name=dataset_name,
            full_shape=full_shape,
            dtype=dtype,
            chunk_shape=chunk_shape,
            buffer_shape=buffer_shape,
            compressors=None if compression_method is None else [compression_method],
        )

    @classmethod
    @abstractmethod
    def from_neurodata_object_with_existing(
        cls,
        neurodata_object: Container,
        dataset_name: Literal["data", "timestamps"],
    ) -> Self:
        """
        Construct an instance of a DatasetIOConfiguration from existing dataset settings.

        This method extracts compression and chunking configurations from an already-written dataset.
        The neurodata object must have been read from an existing NWB file.

        Parameters
        ----------
        neurodata_object : hdmf.Container
            The neurodata object containing the field that has been read from disk.
        dataset_name : "data" or "timestamps"
            The name of the field that corresponds to the dataset on disk.

        Returns
        -------
        Self
            A DatasetIOConfiguration instance with settings matching the existing dataset.
        """
        raise NotImplementedError

    @staticmethod
    def get_kwargs_from_neurodata_object(
        neurodata_object: Container,
        dataset_name: Literal["data", "timestamps"],
    ) -> dict:
        location_in_file = _find_location_in_memory_nwbfile(neurodata_object=neurodata_object, field_name=dataset_name)
        dataset = DatasetIOConfiguration.get_dataset(neurodata_object=neurodata_object, dataset_name=dataset_name)
        full_shape = dataset.shape
        dtype = _infer_dtype(dataset=dataset)
        chunk_shape = dataset.chunks
        buffer_chunk_shape = chunk_shape or full_shape
        buffer_shape = SliceableDataChunkIterator.estimate_default_buffer_shape(
            buffer_gb=0.5, chunk_shape=buffer_chunk_shape, maxshape=full_shape, dtype=np.dtype(dtype)
        )
        return dict(
            object_id=neurodata_object.object_id,
            object_name=neurodata_object.name,
            location_in_file=location_in_file,
            dataset_name=dataset_name,
            full_shape=full_shape,
            dtype=dtype,
            chunk_shape=chunk_shape,
            buffer_shape=buffer_shape,
        )

    @staticmethod
    def get_dataset(
        neurodata_object: Container,
        dataset_name: Literal["data", "timestamps"],
    ) -> h5py.Dataset | zarr.Array:
        dataset = getattr(neurodata_object, dataset_name)
        while hasattr(dataset, "dataset"):
            dataset = dataset.dataset
        return dataset

    # ==================================================================================================
    # Deprecated in v0.10.1, to be removed in v0.12.0.
    #
    # Everything between this marker and the one closing the block is self-contained: it reads and writes
    # `compressors` and `compressor_options` and nothing outside the block calls into it. Deleting the
    # whole block at v0.12.0 removes `compression_method` and `compression_options` and touches nothing
    # else. The index helper is duplicated here on purpose rather than shared, so that deletion stays a
    # deletion.
    # ==================================================================================================

    _COMPRESSION_METHOD_DEPRECATION_MESSAGE = (
        "`compression_method` is deprecated and will be removed in v0.12.0. Use `compressors` instead."
    )
    _COMPRESSION_OPTIONS_DEPRECATION_MESSAGE = (
        "`compression_options` is deprecated and will be removed in v0.12.0. Use `compressor_options` instead."
    )

    def _deprecated_compression_index(self) -> int | None:
        """Index into `compressors` of the entry that is the compression method, or None if there is not one."""
        if self.compressors is None:
            return None
        for index in reversed(range(len(self.compressors))):
            compressor = self.compressors[index]
            if not (isinstance(compressor, str) and compressor in self._pure_filter_names):
                return index
        return None

    @property
    def compression_method(self):
        """
        The compression method applied to this dataset.

        .. deprecated:: 0.10.1
            `compression_method` is deprecated and will be removed in v0.12.0. Use `compressors` instead.
        """
        warnings.warn(self._COMPRESSION_METHOD_DEPRECATION_MESSAGE, FutureWarning, stacklevel=2)
        index = self._deprecated_compression_index()
        return None if index is None else self.compressors[index]

    @compression_method.setter
    def compression_method(self, compression_method) -> None:
        warnings.warn(self._COMPRESSION_METHOD_DEPRECATION_MESSAGE, FutureWarning, stacklevel=2)
        index = self._deprecated_compression_index()

        if compression_method is None:
            if index is not None:
                compressors = list(self.compressors)
                compressors.pop(index)
                self.compressors = compressors or None
            return

        if index is None:
            self.compressors = list(self.compressors or []) + [compression_method]
            return

        compressors = list(self.compressors)
        compressors[index] = compression_method
        self.compressors = compressors

    @property
    def compression_options(self) -> dict[str, Any] | None:
        """
        The parameters of the compression method applied to this dataset.

        .. deprecated:: 0.10.1
            `compression_options` is deprecated and will be removed in v0.12.0. Use `compressor_options` instead.
        """
        warnings.warn(self._COMPRESSION_OPTIONS_DEPRECATION_MESSAGE, FutureWarning, stacklevel=2)
        index = self._deprecated_compression_index()
        if index is None or self.compressor_options is None:
            return None
        return self.compressor_options[index]

    @compression_options.setter
    def compression_options(self, compression_options: dict[str, Any] | None) -> None:
        warnings.warn(self._COMPRESSION_OPTIONS_DEPRECATION_MESSAGE, FutureWarning, stacklevel=2)
        index = self._deprecated_compression_index()
        if index is None:
            if compression_options is not None:
                raise ValueError(
                    "`compression_options` was set but there is no compression method to apply them to. "
                    "Set `compressors` first."
                )
            return
        compressor_options = list(self.compressor_options or [None] * len(self.compressors))
        compressor_options[index] = compression_options
        self.compressor_options = compressor_options

    @model_validator(mode="before")
    def translate_deprecated_compression_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Accept the deprecated `compression_method` and `compression_options` spellings for one release cycle."""
        if not isinstance(values, dict):
            return values
        has_compression_method = "compression_method" in values
        has_compression_options = "compression_options" in values
        if not (has_compression_method or has_compression_options):
            return values
        if "compressors" in values or "compressor_options" in values:
            raise ValueError(
                "Both the deprecated `compression_method`/`compression_options` and the new "
                "`compressors`/`compressor_options` were specified. Use only `compressors` and `compressor_options`."
            )

        deprecated_names = [
            name
            for name, present in (
                ("compression_method", has_compression_method),
                ("compression_options", has_compression_options),
            )
            if present
        ]
        warnings.warn(
            f"{' and '.join(f'`{name}`' for name in deprecated_names)} "
            f"{'is' if len(deprecated_names) == 1 else 'are'} deprecated and will be removed in v0.12.0. "
            "Use `compressors` and `compressor_options` instead.",
            FutureWarning,
            stacklevel=2,
        )

        compression_method = values.pop("compression_method", None)
        compression_options = values.pop("compression_options", None)
        values["compressors"] = None if compression_method is None else [compression_method]
        values["compressor_options"] = None if compression_options is None else [compression_options]
        return values

    # ==================================================================================================
    # End of the block deprecated in v0.10.1, to be removed in v0.12.0.
    # ==================================================================================================
