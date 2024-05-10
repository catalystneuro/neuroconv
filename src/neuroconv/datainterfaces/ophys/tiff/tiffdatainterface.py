from typing import Literal
from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FilePathType
from ....utils.dict import DeepDict


class TiffImagingInterface(BaseImagingExtractorInterface):
    """Interface for multi-page TIFF files."""

    display_name = "TIFF Imaging"
    associated_suffixes = (".tif", ".tiff")
    info = "Interface for multi-page TIFF files."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff file."
        return source_schema

    def __init__(self, file_path: FilePathType, sampling_frequency: float, photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries", verbose: bool = True):
        """
        Initialize reading of TIFF file.

        Parameters
        ----------
        file_path : FilePathType
        sampling_frequency : float
        verbose : bool, default: True
        """
        self.photon_series_type=photon_series_type
        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency, verbose=verbose)

    def get_metadata_schema(self):
        metadata_schema=super().get_metadata_schema(photon_series_type=self.photon_series_type)
        return metadata_schema
    
    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata(photon_series_type=self.photon_series_type)

        return metadata