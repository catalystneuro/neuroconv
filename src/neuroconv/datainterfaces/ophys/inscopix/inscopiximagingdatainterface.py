from typing import Literal

from pydantic import FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class InscopixImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for Inscopix Imaging Extractor."""

    display_name = "Inscopix Imaging"
    associated_suffixes = (".isxd",)
    info = "Interface for handling Inscopix imaging data."

    @validate_call
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
            If True, outputs additional information during processing.
        photon_series_type : {"OnePhotonSeries", "TwoPhotonSeries"}, optional
            Specifies the type of photon series to be used. Defaults to "OnePhotonSeries".
        """

        super().__init__(
            file_path=file_path,
            verbose=verbose,
            photon_series_type=photon_series_type,
        )
