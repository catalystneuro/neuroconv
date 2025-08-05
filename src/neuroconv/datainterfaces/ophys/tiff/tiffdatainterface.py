from typing import Literal, Optional

from pydantic import FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class GeneralTiffImagingInterface(BaseImagingExtractorInterface):
    """General data Interface for TIFF files."""

    display_name = "General TIFF Imaging"
    associated_suffixes = (".tif", ".tiff")
    info = "Interface for TIFF files."
    ExtractorName: str | None = "MultiTIFFMultiPageExtractor"

    @classmethod
    def get_extractor(cls):
        """
        Get the extractor class for the general TIFF imaging interface.

        Returns
        -------
        str
            The name of the extractor class to be used with this interface.
        """
        from roiextractors import MultiTIFFMultiPageExtractor

        return MultiTIFFMultiPageExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the general TIFF imaging interface.

        Returns
        -------
        dict
            The JSON schema for the general TIFF imaging interface source data,
            containing file path and other configuration parameters.
        """
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff file."
        return source_schema

    @validate_call
    def __init__(
        self,
        file_paths: list[FilePath],
        sampling_frequency: float,
        dimension_order: str = "ZCT",
        num_channels: int = 1,
        channel_index: int = 0,
        num_planes: int = 1,
        num_acquisition_cycles: Optional[int] = None,
        verbose: bool = False,
    ):
        """
        Initialize reading of TIFF file.

        Parameters
        ----------
        file_paths : FilePath
        sampling_frequency : float
        verbose : bool, default: False
        """
        super().__init__(
            file_paths=file_paths,
            sampling_frequency=sampling_frequency,
            dimension_order=dimension_order,
            num_channels=num_channels,
            channel_index=channel_index,
            num_planes=num_planes,
            num_acquisition_cycles=num_acquisition_cycles,
            verbose=verbose,
        )
        self.imaging_extractor.get_num_channels = lambda: 1

    def get_metadata(self) -> dict:
        return super().get_metadata()


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
    ):
        """
        Initialize reading of TIFF file.

        Parameters
        ----------
        file_path : FilePath
        sampling_frequency : float
        verbose : bool, default: False
        photon_series_type : {'OnePhotonSeries', 'TwoPhotonSeries'}, default: "TwoPhotonSeries"
        """
        super().__init__(
            file_path=file_path,
            sampling_frequency=sampling_frequency,
            verbose=verbose,
            photon_series_type=photon_series_type,
        )
