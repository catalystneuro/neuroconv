from typing import Literal

from pydantic import FilePath, validate_call

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class InscopixSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for Inscopix Segmentation Extractor."""

    display_name = "Inscopix Segmentation"
    associated_suffixes = (".isxd",)
    info = "Interface for handling segmentation data from Inscopix."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = False,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "OnePhotonSeries",
    ):
        super().__init__(
            file_path=file_path,
            verbose=verbose,
            photon_series_type=photon_series_type,
        )

    def get_metadata(self) -> dict:
        """
        Retrieve metadata for the Inscopix segmentation data.

        Returns:
            dict: Metadata dictionary with updated device description for Inscopix segmentation.
        """
        metadata = super().get_metadata()
        metadata["Ophys"]["Device"][0]["description"] = "Inscopix segmentation"
        return metadata
