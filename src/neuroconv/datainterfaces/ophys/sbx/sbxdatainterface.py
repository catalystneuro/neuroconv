import warnings
from typing import Literal

from pydantic import FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict


class SbxImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for SbxImagingExtractor."""

    display_name = "Scanbox Imaging"
    associated_suffixes = (".sbx",)
    info = "Interface for Scanbox imaging data."

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import SbxImagingExtractor

        return SbxImagingExtractor

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        sampling_frequency: float | None = None,
        verbose: bool = False,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to .sbx file.
        sampling_frequency : float, optional
        verbose : bool, default: False
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "sampling_frequency",
                "verbose",
                "photon_series_type",
            ]
            num_positional_args_before_args = 1  # file_path
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
                f"Passing arguments positionally to SbxImagingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            sampling_frequency = positional_values.get("sampling_frequency", sampling_frequency)
            verbose = positional_values.get("verbose", verbose)
            photon_series_type = positional_values.get("photon_series_type", photon_series_type)

        super().__init__(
            file_path=file_path,
            sampling_frequency=sampling_frequency,
            verbose=verbose,
            photon_series_type=photon_series_type,
        )

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the Scanbox imaging data.

        Returns
        -------
        dict
            Dictionary containing metadata including device information and imaging details
            specific to the Scanbox system.
        """
        metadata = super().get_metadata()
        metadata["Ophys"]["Device"][0]["description"] = "Scanbox imaging"
        return metadata
