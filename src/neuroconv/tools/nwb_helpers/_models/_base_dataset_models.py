"""Base Pydantic models for DatasetInfo and DatasetConfiguration."""
from typing import Any, Dict, Tuple, Union

import h5py
import numcodecs
import numpy as np
from pydantic import BaseModel, Field, root_validator, validator


class DatasetInfo(BaseModel):
    # TODO: When using Pydantic v2, replace with
    # model_config = ConfigDict(allow_mutation=False)
    class Config:  # noqa: D106
        allow_mutation = False
        arbitrary_types_allowed = True

    object_id: str = Field(description="The UUID of the neurodata object containing the dataset.")
    location: str = Field(description="The relative location of the this dataset within the in-memory NWBFile.")
    full_shape: Tuple[int, ...] = Field(description="The maximum shape of the entire dataset.")
    dtype: np.dtype = Field(  # TODO: When using Pydantic v2, replace np.dtype with InstanceOf[np.dtype]
        description="The data type of elements of this dataset."
    )

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
        string = (
            f"\n{self.location}"
            f"\n{'-' * len(self.location)}"
            f"\n  full_shape: {self.full_shape}"
            f"\n  dtype: {self.dtype}"
        )
        return string


class DatasetConfiguration(BaseModel):
    """A data model for configuring options about an object that will become a HDF5 or Zarr Dataset in the file."""

    # TODO: When using Pydantic v2, remove
    class Config:
        arbitrary_types_allowed = True

    dataset_info: DatasetInfo = Field(description="The immutable information about this dataset.")
    chunk_shape: Tuple[int, ...] = Field(
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
        string = (
            f"\n{self.dataset_info.location}"
            f"\n{'-' * len(self.dataset_info.location)}"
            f"\n  maxshape: {self.dataset_info.full_shape}"
            f"\n  dtype: {self.dataset_info.dtype}"
            "\n"
            f"\n  chunk_shape: {self.chunk_shape}"
            f"\n  buffer_shape: {self.buffer_shape}"
            f"\n  compression_method: {self.compression_method}"
        )
        if self.compression_options is not None:
            string += f"\n  compression_options: {self.compression_options}"

        return string

    @root_validator
    def validate_all_shapes(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        chunk_shape = values["chunk_shape"]
        buffer_shape = values["buffer_shape"]
        full_shape = values["dataset_info"].full_shape

        if len(chunk_shape) != len(buffer_shape):
            raise ValueError(f"{len(chunk_shape)=} does not match {len(buffer_shape)=}!")
        if len(buffer_shape) != len(full_shape):
            raise ValueError(f"{len(buffer_shape)=} does not match {len(full_shape)=}!")

        if any(chunk_axis <= 0 for chunk_axis in chunk_shape):
            raise ValueError(f"Some dimensions of the {chunk_shape=} are less than or equal to zero!")
        if any(buffer_axis <= 0 for buffer_axis in buffer_shape):
            raise ValueError(f"Some dimensions of the {buffer_shape=} are less than or equal to zero!")

        if any(chunk_axis > buffer_axis for chunk_axis, buffer_axis in zip(chunk_shape, buffer_shape)):
            raise ValueError(f"Some dimensions of the {chunk_shape=} exceed the {buffer_shape=})!")
        if any(buffer_axis > full_axis for buffer_axis, full_axis in zip(buffer_shape, full_shape)):
            raise ValueError(f"Some dimensions of the {buffer_shape=} exceed the {full_shape=}!")

        if any(buffer_axis % chunk_axis != 0 for chunk_axis, buffer_axis in zip(chunk_shape, buffer_shape)):
            raise ValueError(f"Some dimensions of the {chunk_shape=} do not evenly divide the {buffer_shape=})!")

        return values

    def get_data_io_keyword_arguments(self):
        """
        Fetch the properly structured dictionary of input arguments to be passed directly into a H5DataIO or ZarrDataIO.
        """
        raise NotImplementedError
