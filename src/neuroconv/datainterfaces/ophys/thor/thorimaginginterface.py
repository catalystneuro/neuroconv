from roiextractors.extractors.thorextractors.thorimagingextractor import (
    ThorTiffImagingExtractor,
)

from neuroconv.datainterfaces.ophys.baseimagingextractorinterface import (
    BaseImagingExtractorInterface,
)
from neuroconv.utils import DeepDict, FilePathType


class ThorTiffImagingInterface(BaseImagingExtractorInterface):
    """Interface for multi-page TIFF files from the ThorLabs acquisition system."""

    display_name = "ThorLabs TIFF Imaging"
    Extractor = ThorTiffImagingExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"]["description"] = (
            "Directory that contains the TIFF files and " "Experiment.xml file. "
        )
        return source_schema

    def __init__(self, folder_path: FilePathType, verbose: bool = False):
        """
        Initialize reading of TIFF file.

        Parameters
        ----------
        folder_path : FilePathType
            Directory that contains the TIFF files and Experiment.xml file.
        verbose : bool, default: False
        """
        super().__init__(folder_path=folder_path, verbose=verbose)

    def get_metadata(self, photon_series_type="TwoPhotonSeries") -> DeepDict:
        metadata = super().get_metadata(photon_series_type=photon_series_type)
        metadata["NWBFile"]["session_start_time"] = self.extractor.start_time
        return metadata
