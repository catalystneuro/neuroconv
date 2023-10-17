"""Base Pydantic models for DatasetInfo and DatasetConfiguration."""
import math
from abc import ABC, abstractmethod
from typing import Any, Dict, Literal, Tuple, Union

import h5py
import numcodecs
import numpy as np
from pydantic import BaseModel, Field, root_validator


class DatasetInfo(BaseModel):
    """A data model to represent immutable aspects of an object that will become a HDF5 or Zarr dataset on write."""

    # TODO: When using Pydantic v2, replace with
    # model_config = ConfigDict(allow_mutation=False)
    class Config:  # noqa: D106
        allow_mutation = False
        arbitrary_types_allowed = True

    object_id: str = Field(description="The UUID of the neurodata object containing the dataset.")
    location: str = Field(  # TODO: in v2, use init_var=False or assign as a property
        description="The relative location of the this dataset within the in-memory NWBFile."
    )
    dataset_name: Literal["data", "timestamps"] = Field(description="The reference name of the dataset.")
    dtype: np.dtype = Field(  # TODO: When using Pydantic v2, replace np.dtype with InstanceOf[np.dtype]
        description="The data type of elements of this dataset."
    )
    full_shape: Tuple[int, ...] = Field(description="The maximum shape of the entire dataset.")

    def __hash__(self):
        """To allow instances of this class to be used as keys in dictionaries."""
        return hash((type(self),) + tuple(self.__dict__.values()))

    def __str__(self) -> str:
        """
        Not overriding __repr__ as this is intended to render only when wrapped in print().

        Reason being two-fold; a standard `repr` is intended to be slightly more machine readable / a more basic
        representation of the true object state. But then also because an iterable of these objects, such as a
        `List[DataSetInfo]`, would print out the nested representations, which only look good when using the basic
        `repr` (that is, this fancy string print-out does not look good when nested in another container).
        """
        source_size_in_gb = math.prod(self.full_shape) * self.dtype.itemsize / 1e9

        string = (
            f"\n{self.location}"
            f"\n{'-' * len(self.location)}"
            f"\n  dtype : {self.dtype}"
            f"\n  full shape of source array : {self.full_shape}"
            f"\n  full size of source array : {source_size_in_gb:0.2f} GB"
        )
        return string

    def __init__(self, **values):
        location = values["location"]

        # For more efficient / explicit reference downstream, instead of reparsing from location multiple times
        dataset_name = location.split("/")[-1]
        values.update(dataset_name=dataset_name)
        super().__init__(**values)


class DatasetConfiguration(BaseModel, ABC):
    """A data model for configuring options about an object that will become a HDF5 or Zarr Dataset in the file."""

    # TODO: When using Pydantic v2, remove
    class Config:
        arbitrary_types_allowed = True

    dataset_info: DatasetInfo = Field(description="The immutable information about this dataset.")
    chunk_shape: Tuple[int, ...] = Field(  # When using Pydantic v2.0, specify PositiveInt
        description=(
            "The specified shape to use when chunking the dataset. "
            "For optimized streaming speeds, a total size of around 10 MB is recommended."
        )
    )
    buffer_shape: Tuple[int, ...] = Field(
        description=(
            "The specified shape to use when iteratively loading data into memory while writing the dataset. "
            "For optimized writing speeds and minimal RAM usage, a total size of around 1 GB is recommended."
        )
    )
    # TODO: When using Pydantic v2, wrap h5py._hl.filters.FilterRefBase and numcodecs.abc.Codec with InstanceOf
    compression_method: Union[str, h5py._hl.filters.FilterRefBase, numcodecs.abc.Codec, None] = Field(
        default="gzip",
        description="The specified compression method to apply to this dataset. Set to `None` to disable compression.",
    )
    compression_options: Union[Dict[str, Any], None] = Field(
        default=None, description="The optional parameters to use for the specified compression method."
    )

    def __str__(self) -> str:
        """
        Not overriding __repr__ as this is intended to render only when wrapped in print().

        Reason being two-fold; a standard `repr` is intended to be slightly more machine readable / a more basic
        representation of the true object state. But then also because an iterable of these objects, such as a
        `List[DatasetConfiguration]`, would print out the nested representations, which only look good when using the
        basic `repr` (that is, this fancy string print-out does not look good when nested in another container).
        """
        source_size_in_gb = math.prod(self.dataset_info.full_shape) * self.dataset_info.dtype.itemsize / 1e9
        maximum_ram_usage_per_iteration_in_gb = math.prod(self.buffer_shape) * self.dataset_info.dtype.itemsize / 1e9
        disk_space_usage_per_chunk_in_mb = math.prod(self.chunk_shape) * self.dataset_info.dtype.itemsize / 1e6

        string = (
            f"\n{self.dataset_info.location}"
            f"\n{'-' * len(self.dataset_info.location)}"
            f"\n  dtype : {self.dataset_info.dtype}"
            f"\n  full shape of source array : {self.dataset_info.full_shape}"
            f"\n  full size of source array : {source_size_in_gb:0.2f} GB"
            # TODO: add nicer auto-selection/rendering of units and amount for source data size
            "\n"
            f"\n  buffer shape : {self.buffer_shape}"
            f"\n  maximum RAM usage per iteration : {maximum_ram_usage_per_iteration_in_gb:0.2f} GB"
            "\n"
            f"\n  chunk shape : {self.chunk_shape}"
            f"\n  disk space usage per chunk : {disk_space_usage_per_chunk_in_mb:0.2f} MB"
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

    @root_validator
    def validate_all_shapes(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        chunk_shape = values["chunk_shape"]
        buffer_shape = values["buffer_shape"]
        full_shape = values["dataset_info"].full_shape
        location = values["dataset_info"].location  # For more identifiable error messages.

        if len(chunk_shape) != len(buffer_shape):
            raise ValueError(
                f"{len(chunk_shape)=} does not match {len(buffer_shape)=} for dataset at location '{location}'!"
            )
        if len(buffer_shape) != len(full_shape):
            raise ValueError(
                f"{len(buffer_shape)=} does not match {len(full_shape)=} for dataset at location '{location}'!"
            )

        if any(chunk_axis <= 0 for chunk_axis in chunk_shape):
            raise ValueError(
                f"Some dimensions of the {chunk_shape=} are less than or equal to zero for dataset at "
                f"location '{location}'!"
            )
        if any(buffer_axis <= 0 for buffer_axis in buffer_shape):
            raise ValueError(
                f"Some dimensions of the {buffer_shape=} are less than or equal to zero for dataset at "
                f"location '{location}'!"
            )

        if any(chunk_axis > buffer_axis for chunk_axis, buffer_axis in zip(chunk_shape, buffer_shape)):
            raise ValueError(
                f"Some dimensions of the {chunk_shape=} exceed the {buffer_shape=} for dataset at "
                f"location '{location}'!"
            )
        if any(buffer_axis > full_axis for buffer_axis, full_axis in zip(buffer_shape, full_shape)):
            raise ValueError(
                f"Some dimensions of the {buffer_shape=} exceed the {full_shape=} for dataset at "
                f"location '{location}'!"
            )

        if any(buffer_axis % chunk_axis != 0 for chunk_axis, buffer_axis in zip(chunk_shape, buffer_shape)):
            raise ValueError(
                f"Some dimensions of the {chunk_shape=} do not evenly divide the {buffer_shape=} for dataset at "
                f"location '{location}'!"
            )

        return values

    @abstractmethod
    def get_data_io_kwargs(self) -> Dict[str, Any]:
        """
        Fetch the properly structured dictionary of input arguments to be passed directly into a H5DataIO or ZarrDataIO.
        """
        raise NotImplementedError
