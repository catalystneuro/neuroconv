from typing import Literal

from pydantic import FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....tools.ophys_metadata_conversion import (
    is_old_ophys_metadata_format,
    update_old_ophys_metadata_format_to_new,
)
from ....utils import DeepDict


class SbxImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for SbxImagingExtractor."""

    display_name = "Scanbox Imaging"
    associated_suffixes = (".sbx",)
    info = "Interface for Scanbox imaging data."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        sampling_frequency: float | None = None,
        verbose: bool = False,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
        metadata_key: str = "default",
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to .sbx file.
        sampling_frequency : float, optional
            The sampling frequency in Hz.
        verbose : bool, default: False
            Whether to print verbose output.
        photon_series_type : {"OnePhotonSeries", "TwoPhotonSeries"}, default: "TwoPhotonSeries"
            The type of photon series to create.
        metadata_key : str, optional
            The key to use for organizing metadata in the new dictionary structure.
            This single key will be used for Device, ImagingPlane, and PhotonSeries.
            Default is "default".
        """

        super().__init__(
            file_path=file_path,
            sampling_frequency=sampling_frequency,
            verbose=verbose,
            photon_series_type=photon_series_type,
            metadata_key=metadata_key,
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

        # Handle backward compatibility
        if is_old_ophys_metadata_format(metadata):
            metadata = update_old_ophys_metadata_format_to_new(metadata)

        # Update device metadata in the new structure
        if "Devices" not in metadata:
            metadata["Devices"] = {}
        if self.metadata_key not in metadata["Devices"]:
            metadata["Devices"][self.metadata_key] = {}
        metadata["Devices"][self.metadata_key]["description"] = "Scanbox imaging"

        return metadata
