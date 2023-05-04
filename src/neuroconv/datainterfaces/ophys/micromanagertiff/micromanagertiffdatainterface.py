from dateutil.parser import parse

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FolderPathType


class MicroManagerTiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for MicroManagerTiffImagingExtractor."""

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()

        source_schema["properties"]["folder_path"][
            "description"
        ] = "The path that points to the folder containing the OME-TIF image files."
        return source_schema

    def __init__(self, folder_path: FolderPathType, verbose: bool = True):
        """
        Data Interface for MicroManagerTiffImagingExtractor.

        Parameters
        ----------
        folder_path : FolderPathType
            The folder path that contains the OME-TIF image files (.ome.tif files) and
           the 'DisplaySettings' JSON file.
        verbose : bool, default: True
        """
        super().__init__(folder_path=folder_path)
        self.verbose = verbose

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        micromanager_metadata = self.imaging_extractor.micromanager_metadata
        session_start_time = parse(micromanager_metadata["Summary"]["StartTime"])
        metadata["NWBFile"].update(session_start_time=session_start_time)

        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        imaging_plane_metadata.update(
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )
        optical_channel_metadata = imaging_plane_metadata["optical_channel"][0]
        optical_channel_name = "OpticalChannel" + self.imaging_extractor.get_channel_names()[0]
        optical_channel_metadata.update(name=optical_channel_name)
        metadata["Ophys"]["TwoPhotonSeries"][0].update(
            unit="px",
            format="tiff",
        )

        return metadata
