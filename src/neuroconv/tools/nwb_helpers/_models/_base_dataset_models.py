"""Collection of helper functions related to configuration of datasets dependent on backend."""
from typing import Any, Dict, Tuple, Type, Union

import numpy as np
from pydantic import BaseModel, Field, root_validator, validator, ConfigDict


class DatasetInfo(BaseModel):
    config = ConfigDict(allow_mutation=False, allow_arbitrary_types=True)
    object_id: str
    location: str
    full_shape: Tuple[int, ...]
    dtype: Union[str, np.dtype]  # TODO: When using Pydantic v2, replace with InstanceOf

    def __hash__(self):
        """To allow instances of this class to be used as keys in dictionaries."""
        return hash((type(self),) + tuple(self.__dict__.values()))

    @validator("dtype")
    def validate_numpy_dtype(cls, dtype):
        if isinstance(dtype, str):
            np.dtype(dtype)  # Rely on numpy type checking to raise an error if am unsupported string
        if not isinstance(dtype, np.dtype):
            raise TypeError(f"The specified 'dtype' ({dtype}) is not a np.dtype (found type: {type(dtype)})!")


class DatasetConfiguration(BaseModel):
    """A data model for configruing options about an object that will become a HDF5 or Zarr Dataset in the file."""

    dataset_info: DatasetInfo
    chunk_shape: Tuple[int, ...]
    buffer_shape: Tuple[int, ...]
    compression_method: Union[str, None]  # Backend configurations should specify Literals; None means no compression
    compression_options: Union[Dict[str, Any], None] = None

    def __str__(self) -> str:
        """Not overriding __repr__ as this is intended to render only when wrapped in print()."""
        string = (
            f"{self.object_name} of {self.parent}\n"
            + f"{'-' * (len(self.object_name) + 4 + len(self.parent))}\n"
            + f"  {self.field}\n"
            + f"    maxshape: {self.full_shape}\n"
            + f"    dtype: {self.dtype}"
        )
        return string

    def get_data_io_keyword_arguments(self) -> Dict[str, Any]:
        raise NotImplementedError

    # TODO: add validation that all _shape values are consistent in length
    @root_validator()
    def validate_shape_consistency(cls, values: Dict[str, Any]):
        chunk_shape = values["chunk_shape"]
        buffer_shape = values["buffer_shape"]
        full_shape = values["dataset_info"]["full_shape"]

        if len(chunk_shape) != len(buffer_shape):
            raise ValueError(
                f"The length of the chunk_shape ({len(chunk_shape)}) does not match the length of the "
                f"buffer_shape ({len(buffer_shape)})!"
            )
        if len(buffer_shape) != len(full_shape):
            raise ValueError(
                f"The length of the buffer_shape ({len(buffer_shape)}) does not match the length of the "
                f"full_shape ({len(full_shape)})!"
            )

        # Check chunks perfectly subset buffer (the GenericIterator will guarantee this, but this is top-level input specification before that is initialized)
        # Check buffer does not exceed full shape

        return values
