from typing import Optional

from numpy import ndarray
from pydantic import DirectoryPath, FilePath, validate_call
from pynwb import NWBFile

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import DeepDict


class MinianSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for MinianSegmentationExtractor.

    Minian is a calcium imaging analysis pipeline that outputs segmented ROIs and their temporal dynamics
    as .zarr files. The standard Minian output includes:

    - Spatial footprints (A.zarr): ROI masks
    - Temporal components (C.zarr): Denoised fluorescence traces
    - Background components (b.zarr, f.zarr): Background masks and temporal dynamics
    - Deconvolved traces (S.zarr): Spike inference results
    - Baseline fluorescence (b0.zarr): Baseline estimates

    **Sampling Frequency and Timestamps:**
    Minian does not natively store sampling frequency information in its output. For NWB conversion,
    either a sampling frequency or timestamps are required. This interface supports:

    1. Providing sampling_frequency directly (recommended for regular sampling)
    2. Using a timeStamps.csv file (often copied from Miniscope outputs)
    3. If neither is provided, the interface will raise an informative error

    The timeStamps.csv file should contain 'Frame Number' and 'Time Stamp (ms)' columns and is
    typically placed in the same folder as the .zarr outputs."""

    display_name = "Minian Segmentation"
    associated_suffixes = (".zarr",)
    info = "Interface for Minian segmentation data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_metadata = super().get_source_schema()
        source_metadata["properties"]["folder_path"]["description"] = "Path to .zarr output."
        source_metadata["properties"]["sampling_frequency"] = {
            "type": "number",
            "description": "The sampling frequency in Hz. If not provided, will attempt to derive from timeStamps.csv.",
        }
        source_metadata["properties"]["timestamps_path"] = {
            "type": "string",
            "description": "Path to the timeStamps.csv file. If not provided, assumes default location at folder_path/timeStamps.csv.",
        }
        return source_metadata

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        sampling_frequency: Optional[float] = None,
        timestamps_path: Optional[FilePath] = None,
        verbose: bool = False,
    ):
        """

        Parameters
        ----------
        folder_path : str or Path
            Path to .zarr path.
        sampling_frequency : float, optional
            The sampling frequency in Hz. If not provided, will attempt to derive from timeStamps.csv.
        timestamps_path : str or Path, optional
            Path to the timeStamps.csv file. If not provided, assumes default location at folder_path/timeStamps.csv.
        verbose : bool, default False
            Whether to print progress
        """
        super().__init__(
            folder_path=folder_path, sampling_frequency=sampling_frequency, timestamps_path=timestamps_path
        )
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
