import warnings

from pydantic import DirectoryPath, validate_call

from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import get_json_schema_from_method_signature


class OpenEphysSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting OpenEphys spiking data."""

    display_name = "OpenEphys Sorting"
    associated_suffixes = (".spikes",)
    info = "Interface for converting legacy OpenEphys sorting data."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Compile input schema for the SortingExtractor.

        Returns
        -------
        dict
            The schema dictionary containing input parameters and descriptions
            for initializing the SortingExtractor.
        """
        metadata_schema = get_json_schema_from_method_signature(
            method=cls.__init__, exclude=["recording_id", "experiment_id"]
        )
        metadata_schema["properties"]["folder_path"].update(
            description="Path to directory containing OpenEphys .spikes files."
        )
        metadata_schema["additionalProperties"] = False
        return metadata_schema

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import (
            OpenEphysSortingExtractor,
        )

        return OpenEphysSortingExtractor

    @validate_call
    def __init__(
        self, folder_path: DirectoryPath, *args, experiment_id: int = 0, recording_id: int = 0
    ):  # TODO: change to * (keyword only) on or after August 2026
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "experiment_id",
                "recording_id",
            ]
            num_positional_args_before_args = 1  # folder_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to OpenEphysSortingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            experiment_id = positional_values.get("experiment_id", experiment_id)
            recording_id = positional_values.get("recording_id", recording_id)

        super().__init__(folder_path=str(folder_path), experiment_id=experiment_id, recording_id=recording_id)
