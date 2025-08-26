from typing import Literal

from pydantic import FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class TiffImagingInterface(BaseImagingExtractorInterface):
    """Interface for multi-page TIFF files."""

    display_name = "TIFF Imaging"
    associated_suffixes = (".tif", ".tiff")
    info = "Interface for multi-page TIFF files."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the TIFF imaging interface.

        Returns
        -------
        dict
            The JSON schema for the TIFF imaging interface source data,
            containing file path and other configuration parameters.
        """
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff file."
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        sampling_frequency: float,
        verbose: bool = False,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
        metadata_key: str = "default",
    ):
        """
        Initialize reading of TIFF file.

        Parameters
        ----------
        file_path : FilePath
            Path to the TIFF file.
        sampling_frequency : float
            The sampling frequency in Hz.
        verbose : bool, default: False
            Whether to print verbose output.
        photon_series_type : {'OnePhotonSeries', 'TwoPhotonSeries'}, default: "TwoPhotonSeries"
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
