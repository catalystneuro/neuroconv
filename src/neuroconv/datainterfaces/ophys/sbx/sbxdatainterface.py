from typing import Literal, Optional

from pydantic import FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class SbxImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for SbxImagingExtractor."""

    display_name = "Scanbox Imaging"
    associated_suffixes = (".sbx",)
    info = "Interface for Scanbox imaging data."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        sampling_frequency: Optional[float] = None,
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

        super().__init__(
            file_path=file_path,
            sampling_frequency=sampling_frequency,
            verbose=verbose,
            photon_series_type=photon_series_type,
        )

    def get_metadata(self) -> dict:
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
