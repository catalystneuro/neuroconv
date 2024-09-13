"""Base Pydantic models for DatasetInfo and DatasetConfiguration."""

from typing import Any, ClassVar, Literal, Type

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

    dataset_configurations: dict[str, DatasetIOConfiguration] = Field(
        description=(
            "A mapping from object locations (e.g. `acquisition/TestElectricalSeriesAP/data`) "
            "to their DatasetConfiguration specification that contains all information "
            "for writing the datasets to disk using the specific backend."
        )
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
    def from_nwbfile(cls, nwbfile: NWBFile) -> Self:
        default_dataset_configurations = get_default_dataset_io_configurations(nwbfile=nwbfile, backend=cls.backend)
        dataset_configurations = {
            default_dataset_configuration.location_in_file: default_dataset_configuration
            for default_dataset_configuration in default_dataset_configurations
        }

        return cls(dataset_configurations=dataset_configurations)

    def find_locations_requiring_remapping(self, nwbfile: NWBFile) -> dict[str, DatasetIOConfiguration]:
        """
        Find locations of objects with mismatched IDs in the file.

        This function identifies neurodata objects in the `nwbfile` that have matching locations
        with the current configuration but different object IDs. It returns a dictionary of
        remapped `DatasetIOConfiguration` objects for these mismatched locations.

        Parameters
        ----------
        nwbfile : pynwb.NWBFile
            The NWBFile object to check for mismatched object IDs.

        Returns
        -------
        dict[str, DatasetIOConfiguration]
            A dictionary where:
            * Keys: Locations in the NWB of objects with mismatched IDs.
            * Values: New `DatasetIOConfiguration` objects corresponding to the updated object IDs.

        Notes
        -----
        * This function only checks for objects with the same location but different IDs.
        * It does not identify objects missing from the current configuration.
        * The returned `DatasetIOConfiguration` objects are copies of the original configurations
        with updated `object_id` fields.
        """
        # Use a fresh default configuration to get mapping of object IDs to locations in file
        default_configurations = list(get_default_dataset_io_configurations(nwbfile=nwbfile, backend=self.backend))

        if len(default_configurations) != len(self.dataset_configurations):
            raise ValueError(
                f"The number of default configurations ({len(default_configurations)}) does not match the number of "
                f"specified configurations ({len(self.dataset_configurations)})!"
            )

        objects_requiring_remapping = {}
        for dataset_configuration in default_configurations:
            location_in_file = dataset_configuration.location_in_file
            object_id = dataset_configuration.object_id

            location_cannot_be_remapped = location_in_file not in self.dataset_configurations
            if location_cannot_be_remapped:
                raise KeyError(
                    f"Unable to remap the object IDs for object at location '{location_in_file}'! This "
                    "usually occurs if you are attempting to configure the backend for two files of "
                    "non-equivalent structure."
                )

            former_configuration = self.dataset_configurations[location_in_file]
            former_object_id = former_configuration.object_id

            if former_object_id == object_id:
                continue

            remapped_configuration = former_configuration.model_copy(update={"object_id": object_id})
            objects_requiring_remapping[location_in_file] = remapped_configuration

        return objects_requiring_remapping

    def build_remapped_backend(
        self,
        locations_to_remap: dict[str, DatasetIOConfiguration],
    ) -> Self:
        """
        Build a remapped backend configuration by updating mismatched object IDs.

        This function takes a dictionary of new `DatasetIOConfiguration` objects
        (as returned by `find_locations_requiring_remapping`) and updates a copy of the current configuration
        with these new configurations.

        Parameters
        ----------
        locations_to_remap : dict
            A dictionary mapping locations in the NWBFile to their corresponding new
            `DatasetIOConfiguration` objects with updated IDs.

        Returns
        -------
        Self
            A new instance of the backend configuration class with updated object IDs for
            the specified locations.
        """
        new_backend_configuration = self.model_copy(deep=True)
        new_backend_configuration.dataset_configurations.update(locations_to_remap)
        return new_backend_configuration
