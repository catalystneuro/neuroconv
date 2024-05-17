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
    pretty_backend_name: ClassVar[Literal["HDF5", "Zarr"]]
    data_io_class: ClassVar[Type[DataIO]]

    model_config = ConfigDict(validate_assignment=True)  # Re-validate model on mutation

    dataset_configurations: Dict[str, DatasetIOConfiguration] = Field(
        description=(
            "A mapping from object locations (e.g. `acquisition/TestElectricalSeriesAP/data`) "
            "to their DatasetConfiguration specification that contains all information "
            "for writing the datasets to disk using the specific backend."
        )
    )

    nwbfile_identifier: str = Field(
        description="The unique identifier of the NWBFile object used to create this configuration."
    )

    def __str__(self) -> str:
        """Not overriding __repr__ as this is intended to render only when wrapped in print()."""
        string = (
            f"\n{self.pretty_backend_name} dataset configurations" f"\n{'-' * (len(self.pretty_backend_name) + 23)}"
        )

        for dataset_configuration in self.dataset_configurations.values():
            string += f"\n{dataset_configuration}"

        return string

    # Pydantic models have several API calls for retrieving the schema - override all of them to work
    @classmethod
    def schema(cls, **kwargs) -> Dict[str, Any]:
        return cls.model_json_schema(**kwargs)

    @classmethod
    def schema_json(cls, **kwargs) -> Dict[str, Any]:
        return cls.model_json_schema(**kwargs)

    @classmethod
    def model_json_schema(cls, **kwargs) -> Dict[str, Any]:
        assert "mode" not in kwargs, "The 'mode' of this method is fixed to be 'validation' and cannot be changed."
        assert "schema_generator" not in kwargs, "The 'schema_generator' of this method cannot be changed."
        return super().model_json_schema(mode="validation", schema_generator=PureJSONSchemaGenerator, **kwargs)

    @classmethod
    def from_nwbfile(cls, nwbfile: NWBFile) -> Self:
        default_dataset_configurations = get_default_dataset_io_configurations(nwbfile=nwbfile, backend=cls.backend)
        dataset_configurations = {
            default_dataset_configuration.location_in_file: default_dataset_configuration
            for default_dataset_configuration in default_dataset_configurations
        }

        return cls(dataset_configurations=dataset_configurations, nwbfile_identifier=nwbfile.identifier)

    def is_compatible_with_nwbfile(self, nwbfile: NWBFile) -> bool:
        """
        Check if the backend configuration is compatible with a given NWBFile.

        Parameters
        ----------
        nwbfile : pynwb.NWBFile
            The NWBFile object to check compatibility against.

        Returns
        -------
        bool
            True if all NWB object IDs in `nwbfile` are present in this backend configuration's
            dataset configurations, False otherwise.
        """

        ids_in_backend_configuration = {
            dataset_configuration.object_id for dataset_configuration in self.dataset_configurations.values()
        }
        ids_in_nwbfile = set(nwbfile.objects.keys())
        return ids_in_nwbfile.issubset(ids_in_backend_configuration)

    def build_remapped_backend_to_nwbfile(self, nwbfile: NWBFile) -> Self:
        """
        Create a new backend configuration remapped to a different NWBFile.

        Parameters
        ----------
        nwbfile : pynwb.NWBFile
            The new NWBFile to remap the configuration to.

        Returns
        -------
            A new instance of the backend configuration class, with dataset configurations
            remapped to their corresponding locations in the new NWBFile.

        Raises
        ------
        ValueError
            If there is a location in the NWBFile that does not have a corresponding
            configuration in the original configuration.

        Notes
        -----
        This function creates a new configuration object. The original configuration remains unchanged.
        """

        location_to_former_configuration = {
            dataset_configuration.location_in_file: dataset_configuration
            for dataset_configuration in self.dataset_configurations.values()
        }

        backend_configuration_class = type(self)
        new_backend_configuration = backend_configuration_class.from_nwbfile(nwbfile=nwbfile)

        for dataset_configuration in new_backend_configuration.dataset_configurations.values():
            location_in_new_nwbfile = dataset_configuration.location_in_file
            if location_in_new_nwbfile not in location_to_former_configuration:
                raise ValueError(f"Configuration for object in the following {location_in_new_nwbfile} not found.")

            # Mapping the configuration through locations in the new NWBFile to the former configuration
            former_configuration = location_to_former_configuration[location_in_new_nwbfile]
            former_configuration.object_id = dataset_configuration.object_id

            # Update the new configuration with the former configuration
            new_backend_configuration.dataset_configurations[location_in_new_nwbfile] = former_configuration

        return new_backend_configuration
