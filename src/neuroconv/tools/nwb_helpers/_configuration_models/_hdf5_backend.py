"""Base Pydantic models for the HDF5DatasetConfiguration."""

from typing import ClassVar, Literal, Type

from pydantic import Field
from pynwb import H5DataIO

from ._base_backend import BackendConfiguration
from ._hdf5_dataset_io import HDF5DatasetIOConfiguration


class HDF5BackendConfiguration(BackendConfiguration):
    """A model for matching collections of DatasetConfigurations specific to the HDF5 backend."""

    backend: ClassVar[Literal["hdf5"]] = "hdf5"
    pretty_backend_name: ClassVar[Literal["HDF5"]] = "HDF5"
    data_io_class: ClassVar[Type[H5DataIO]] = H5DataIO

    dataset_configurations: dict[str, HDF5DatasetIOConfiguration] = Field(
        description=(
            "A mapping from object locations to their HDF5DatasetConfiguration specification that contains all "
            "information for writing the datasets to disk using the HDF5 backend."
        )
    )
