from typing import Optional

from numpy import ndarray
from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import DeepDict


class MinianSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for MinianSegmentationExtractor."""

    display_name = "Minian Segmentation"
    associated_suffixes = (".zarr",)
    info = "Interface for Minian segmentation data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_metadata = super().get_source_schema()
        source_metadata["properties"]["folder_path"]["description"] = "Path to .zarr output."
        return source_metadata

    @validate_call
    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        """

        Parameters
        ----------
        folder_path : str or Path
            Path to .zarr path.
        verbose : bool, default False
            Whether to print progress
        """
        super().__init__(folder_path=folder_path)
        self.verbose = verbose

    def get_original_timestamps(self, start_sample: Optional[int] = None, end_sample: Optional[int] = None) -> ndarray:
        return self.segmentation_extractor.get_native_timestamps(start_sample=start_sample, end_sample=end_sample)

    def get_timestamps(self, start_sample: Optional[int] = None, end_sample: Optional[int] = None) -> ndarray:
        return self.segmentation_extractor.get_timestamps(start_sample=start_sample, end_sample=end_sample)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        stub_frames: int = 100,
        include_background_segmentation: bool = True,
        include_roi_centroids: bool = True,
        include_roi_acceptance: bool = False,
        mask_type: Optional[str] = "image",  # Literal["image", "pixel", "voxel"]
        plane_segmentation_name: Optional[str] = None,
        iterator_options: Optional[dict] = None,
    ):
        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            stub_frames=stub_frames,
            include_background_segmentation=include_background_segmentation,
            include_roi_centroids=include_roi_centroids,
            include_roi_acceptance=include_roi_acceptance,
            mask_type=mask_type,
            plane_segmentation_name=plane_segmentation_name,
            iterator_options=iterator_options,
        )

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the Minian segmentation data.

        Returns
        -------
        DeepDict
            The metadata dictionary containing imaging metadata from the Minian output.
            This includes:
            - session_id: Unique identifier for the session.
            - subject_id: Unique identifier for the subject.
        """
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_id"] = self.segmentation_extractor._get_session_id()
        # metadata["Subject"]["subject_id"] = self.segmentation_extractor._get_subject_id()
        return metadata
