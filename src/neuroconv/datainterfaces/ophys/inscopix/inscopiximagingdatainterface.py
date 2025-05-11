from typing import Literal

from pydantic import FilePath

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class InscopixImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for Inscopix Imaging Extractor."""

    display_name = "Inscopix Imaging"
    associated_suffixes = (".isxd",)
    info = "Interface for handling Inscopix imaging data."

    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = False,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "OnePhotonSeries",
    ):
        """
        Parameters
        ----------
        file_path : str
            Path to the .isxd Inscopix file.
        verbose : bool, optional
        """

        super().__init__(
            file_path=file_path,
            verbose=verbose,
            photon_series_type=photon_series_type,
        )
