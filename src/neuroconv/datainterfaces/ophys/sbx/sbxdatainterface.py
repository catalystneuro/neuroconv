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
        file_path : FilePathType
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
            A dictionary containing metadata for the Scanbox imaging data,
            including device description set to "Scanbox imaging".
        """
        metadata = super().get_metadata()
        metadata["Ophys"]["Device"][0]["description"] = "Scanbox imaging"
        return metadata
