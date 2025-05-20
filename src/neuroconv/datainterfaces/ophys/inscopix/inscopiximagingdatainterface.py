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

        self.optical_series_name = photon_series_type

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
        metadata["Ophys"]["Device"][0]["description"] = "Inscopix imaging"
        return metadata

    def add_to_nwbfile(self, nwbfile, metadata=None, **kwargs):
        """
        Add the Inscopix data to the NWB file.
        Parameters
        ----------
        nwbfile : NWBFile
            NWB file to add the data to.
        metadata : dict, optional
            Metadata dictionary.
        **kwargs
            Additional keyword arguments.
        """
        # Ensure photon_series_type is correctly passed to parent method
        kwargs["photon_series_type"] = self.photon_series_type

        # Call parent add_to_nwbfile method with the correct photon_series_type
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **kwargs)