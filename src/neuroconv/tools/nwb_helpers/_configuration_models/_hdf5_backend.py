"""Base Pydantic models for the HDF5DatasetConfiguration."""

from typing import ClassVar, Dict, Literal, Type

from pydantic import Field
from pynwb import H5DataIO, NWBFile
from typing_extensions import Self

from ._base_backend import BackendConfiguration
from ._hdf5_dataset_io import HDF5DatasetIOConfiguration
from .._dataset_configuration import get_existing_dataset_io_configurations


class HDF5BackendConfiguration(BackendConfiguration):
    """A model for matching collections of DatasetConfigurations specific to the HDF5 backend."""

    backend: ClassVar[Literal["hdf5"]] = "hdf5"
    pretty_backend_name: ClassVar[Literal["HDF5"]] = "HDF5"
    data_io_class: ClassVar[Type[H5DataIO]] = H5DataIO

    dataset_configurations: Dict[str, HDF5DatasetIOConfiguration] = Field(
        description=(
            "A mapping from object locations to their HDF5DatasetConfiguration specification that contains all "
            "information for writing the datasets to disk using the HDF5 backend."
        )
    )

    @classmethod
    def from_existing_nwbfile(cls, nwbfile: NWBFile) -> Self:
        existing_dataset_configurations = get_existing_dataset_io_configurations(nwbfile=nwbfile, backend=cls.backend)
        dataset_configurations = {
            existing_dataset_configuration.location_in_file: existing_dataset_configuration
            for existing_dataset_configuration in existing_dataset_configurations
        }

        return cls(dataset_configurations=dataset_configurations)
