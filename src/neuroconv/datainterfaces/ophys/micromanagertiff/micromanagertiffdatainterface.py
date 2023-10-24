from typing import Literal, Optional

from dateutil.parser import parse
from pynwb import NWBFile

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....tools.roiextractors import get_nwb_imaging_metadata
from ....utils import FolderPathType, dict_deep_update


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
        # Micro-Manager uses "Default" as channel name, for clarity we rename it to  'OpticalChannelDefault'
        channel_name = self.imaging_extractor._channel_names[0]
        self.imaging_extractor._channel_names = [f"OpticalChannel{channel_name}"]

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        default_metadata = get_nwb_imaging_metadata(self.imaging_extractor, photon_series_type="OnePhotonSeries")
        metadata = dict_deep_update(metadata, default_metadata)
        # Remove default TwoPhotonSeries metadata to only contain metadata for OnePhotonSeries
        metadata["Ophys"].pop("TwoPhotonSeries", None)

        micromanager_metadata = self.imaging_extractor.micromanager_metadata
        session_start_time = parse(micromanager_metadata["Summary"]["StartTime"])
        metadata["NWBFile"].update(session_start_time=session_start_time)

        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        imaging_plane_metadata.update(
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )

        return metadata

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema(photon_series_type="OnePhotonSeries")
        return metadata_schema

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "OnePhotonSeries",
        photon_series_index: int = 0,
        parent_container: Literal["acquisition", "processing/ophys"] = "acquisition",
        stub_test: bool = False,
        stub_frames: int = 100,
    ):
        return super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            photon_series_index=photon_series_index,
            parent_container=parent_container,
            stub_test=stub_test,
            stub_frames=stub_frames,
        )
