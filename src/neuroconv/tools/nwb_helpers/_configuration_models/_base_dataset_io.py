"""Base Pydantic models for DatasetInfo and DatasetConfiguration."""

import math
from abc import ABC, abstractmethod
from typing import Any, Literal, Union

import h5py
import numcodecs
import numpy as np
import zarr
from hdmf import Container
from hdmf.data_utils import GenericDataChunkIterator
from hdmf.utils import get_data_shape
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    InstanceOf,
    PositiveInt,
    model_validator,
)
from pynwb import NWBFile
from typing_extensions import Self

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


def _infer_dtype_of_list(list_: list[Union[int, float, list]]) -> np.dtype:
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


def _infer_dtype(dataset: Union[h5py.Dataset, zarr.Array]) -> np.dtype:
    """Attempt to infer the dtype of the contained values of the dataset."""
    if hasattr(dataset, "dtype"):
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
    chunk_shape: Union[tuple[PositiveInt, ...], None] = Field(
        description=(
            "The specified shape to use when chunking the dataset. "
            "For optimized streaming speeds, a total size of around 10 MB is recommended."
        ),
    )
    buffer_shape: Union[tuple[int, ...], None] = Field(
        description=(
            "The specified shape to use when iteratively loading data into memory while writing the dataset. "
            "For optimized writing speeds and minimal RAM usage, a total size of around 1 GB is recommended."
        ),
    )
    compression_method: Union[
        str, InstanceOf[h5py._hl.filters.FilterRefBase], InstanceOf[numcodecs.abc.Codec], None
    ] = Field(
        description="The specified compression method to apply to this dataset. Set to `None` to disable compression.",
    )
    compression_options: Union[dict[str, Any], None] = Field(
        default=None, description="The optional parameters to use for the specified compression method."
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
        size_in_bytes = math.prod(self.full_shape) * self.dtype.itemsize
        maximum_ram_usage_per_iteration_in_bytes = math.prod(self.buffer_shape) * self.dtype.itemsize
        disk_space_usage_per_chunk_in_bytes = math.prod(self.chunk_shape) * self.dtype.itemsize

        string = (
            f"\n{self.location_in_file}"
            f"\n{'-' * len(self.location_in_file)}"
            f"\n  dtype : {self.dtype}"
            f"\n  full shape of source array : {self.full_shape}"
            f"\n  full size of source array : {human_readable_size(size_in_bytes)}"
            "\n"
            f"\n  buffer shape : {self.buffer_shape}"
            f"\n  expected RAM usage : {human_readable_size(maximum_ram_usage_per_iteration_in_bytes)}"
            "\n"
            f"\n  chunk shape : {self.chunk_shape}"
            f"\n  disk space usage per chunk : {human_readable_size(disk_space_usage_per_chunk_in_bytes)}"
            "\n"
        )
        if self.compression_method is not None:
            string += f"\n  compression method : {self.compression_method}"
        if self.compression_options is not None:
            string += f"\n  compression options : {self.compression_options}"
        if self.compression_method is not None or self.compression_options is not None:
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

        chunk_shape = values["chunk_shape"]
        buffer_shape = values["buffer_shape"]
        full_shape = values["full_shape"]

        if len(chunk_shape) != len(buffer_shape):
            raise ValueError(
                f"{len(chunk_shape)=} does not match {len(buffer_shape)=} for dataset at location '{location_in_file}'!"
            )
        if len(buffer_shape) != len(full_shape):
            raise ValueError(
                f"{len(buffer_shape)=} does not match {len(full_shape)=} for dataset at location '{location_in_file}'!"
            )

        if any(chunk_axis <= 0 for chunk_axis in chunk_shape):
            raise ValueError(
                f"Some dimensions of the {chunk_shape=} are less than or equal to zero for dataset at "
                f"location '{location_in_file}'!"
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
    def from_neurodata_object(cls, neurodata_object: Container, dataset_name: Literal["data", "timestamps"]) -> Self:
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
        """
        location_in_file = _find_location_in_memory_nwbfile(neurodata_object=neurodata_object, field_name=dataset_name)

        candidate_dataset = getattr(neurodata_object, dataset_name)
        full_shape = get_data_shape(data=candidate_dataset)
        dtype = _infer_dtype(dataset=candidate_dataset)

        if isinstance(candidate_dataset, GenericDataChunkIterator):
            chunk_shape = candidate_dataset.chunk_shape
            buffer_shape = candidate_dataset.buffer_shape
            compression_method = "gzip"
        elif dtype != np.dtype("object"):
            chunk_shape = SliceableDataChunkIterator.estimate_default_chunk_shape(
                chunk_mb=10.0, maxshape=full_shape, dtype=np.dtype(dtype)
            )
            buffer_shape = SliceableDataChunkIterator.estimate_default_buffer_shape(
                buffer_gb=0.5, chunk_shape=chunk_shape, maxshape=full_shape, dtype=np.dtype(dtype)
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
            compression_method=compression_method,
        )
