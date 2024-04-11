"""Base Pydantic models for DatasetInfo and DatasetConfiguration."""

from typing import Any, ClassVar, Dict, Literal, Type

from hdmf.container import DataIO
from pydantic import BaseModel, ConfigDict, Field
from pynwb import NWBFile
from typing_extensions import Self

from ._base_dataset_io import DatasetIOConfiguration
from ._pydantic_pure_json_schema_generator import PureJSONSchemaGenerator
from .._dataset_configuration import get_default_dataset_io_configurations


class BackendConfiguration(BaseModel):
    """A model for matching collections of DatasetConfigurations to a specific backend."""

    backend: ClassVar[Literal["hdf5", "zarr"]]
    data_io_class: ClassVar[Type[DataIO]]

    model_config = ConfigDict(validate_assignment=True)  # Re-validate model on mutation

    dataset_configurations: Dict[str, DatasetIOConfiguration] = Field(
        description=(
            "A mapping from object locations (e.g. `acquisition/TestElectricalSeriesAP/data`) "
            "to their DatasetConfiguration specification that contains all information "
            "for writing the datasets to disk using the specific backend."
        )
    )

    def __str__(self) -> str:
        """Not overriding __repr__ as this is intended to render only when wrapped in print()."""
        string = (
            f"\nConfigurable datasets identified using the {self.backend} backend"
            f"\n{'-' * (43 + len(self.backend) + 8)}"
        )

        for dataset_configuration in self.dataset_configurations.values():
            string += f"\n{dataset_configuration}"

        return string

    # Pydantic models have several API calls for retrieving the schema - override all of them to work
    @classmethod
    def schema(cls) -> Dict[str, Any]:
        return cls.model_json_schema(mode="validation", schema_generator=PureJSONSchemaGenerator)

    @classmethod
    def schema_json(cls) -> Dict[str, Any]:
        return cls.model_json_schema(mode="validation", schema_generator=PureJSONSchemaGenerator)

    @classmethod
    def model_json_schema(cls) -> Dict[str, Any]:
        return cls.model_json_schema(mode="validation", schema_generator=PureJSONSchemaGenerator)

    @classmethod
    def from_nwbfile(cls, nwbfile: NWBFile) -> Self:
        default_dataset_configurations = get_default_dataset_io_configurations(nwbfile=nwbfile, backend=cls.backend)
        dataset_configurations = {
            default_dataset_configuration.location_in_file: default_dataset_configuration
            for default_dataset_configuration in default_dataset_configurations
        }

        return cls(dataset_configurations=dataset_configurations)
