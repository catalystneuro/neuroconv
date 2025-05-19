import copy
import platform

from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class InscopixSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for Inscopix segmentation extractor.

    This interface handles segmentation data from Inscopix's proprietary format (.isxd),
    extracting ROIs, their masks, and associated traces.

    Parameters
    ----------
    file_path : FilePath
        Path to the Inscopix cell set file (.isxd)
    verbose : bool, default: False
        Whether to print verbose output during operations
    """

    display_name = "Inscopix Segmentation"
    associated_suffixes = (".isxd",)
    info = "Interface for Inscopix segmentation data from Inscopix proprietary format."
    keywords = ("segmentation", "roi", "inscopix", "cells")

    def __init__(self, file_path: FilePath, verbose: bool = False):
        """Initialize the Inscopix segmentation interface.

        Parameters
        ----------
        file_path : FilePath
            Path to the Inscopix cell set file (.isxd)
        verbose : bool, default: False
            Whether to print verbose output during operations
        """
        # Check for macOS ARM64 platform before initialization to fail early
        if platform.system() == "Darwin" and platform.machine() == "arm64":
            raise ImportError(
                "The isx package is currently not natively supported on macOS with Apple Silicon. "
                "Installation instructions can be found at: "
                "https://github.com/inscopix/pyisx?tab=readme-ov-file#install"
            )

        # Initialize the parent class with just file_path
        # Note: Do NOT pass plane_name here as InscopixSegmentationExtractor doesn't accept it
        super().__init__(file_path=file_path)
        self.verbose = verbose

        # Access the extractor to verify it initialized correctly
        self._check_extractor()

    def _check_extractor(self):
        """
        Check if the segmentation extractor was properly initialized.

        This method verifies that the extractor is accessible and contains valid data.
        It's called during initialization to catch potential issues early.
        """
        try:
            # Try to access the extractor
            extractor = self.segmentation_extractor

            # Perform some basic checks
            num_rois = extractor.get_num_rois()
            if num_rois == 0:
                # This is not an error, but might be unexpected in some cases
                if self.verbose:
                    print("Warning: No ROIs found in the segmentation data.")

        except Exception as e:
            # If we hit an issue, provide a clear error message
            raise ValueError(
                f"Error initializing Inscopix segmentation extractor from {self.source_data.get('file_path')}: {str(e)}. "
                f"Please check that the file exists and is a valid Inscopix Cell Set file (.isxd)."
            ) from e

    def get_metadata(self) -> dict:
        """
        Retrieve metadata from the segmentation extractor and ensure it's not mutated.

        Returns
        -------
        dict
            The metadata dictionary containing information from the segmentation extractor
        """
        # Get metadata from parent class
        metadata = super().get_metadata()

        # Return a deep copy to prevent mutation during subsequent processing
        return copy.deepcopy(metadata)

    def add_to_nwbfile(
        self,
        nwbfile,
        metadata: dict = None,
        stub_test: bool = False,
        stub_frames: int = 100,
        include_background_segmentation: bool = False,
        include_roi_centroids: bool = True,
        include_roi_acceptance: bool = True,
        mask_type: str = "image",  # Literal["image", "pixel", "voxel"]
        plane_segmentation_name: str = None,
        iterator_options: dict = None,
    ):
        """
        Add the segmentation data to an NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the segmentation data to
        metadata : dict, optional
            Metadata dictionary with information used to create the NWB file
        stub_test : bool, default: False
            Whether to use a reduced dataset for testing
        stub_frames : int, default: 100
            Number of frames to use when stub_test is True
        include_background_segmentation : bool, default: False
            Whether to include the background plane segmentation and fluorescence traces
        include_roi_centroids : bool, default: True
            Whether to include the ROI centroids on the PlaneSegmentation table
        include_roi_acceptance : bool, default: True
            Whether to include if the detected ROI was 'accepted' or 'rejected'
        mask_type : str, default: "image"
            Type of mask representation to use. Options: "image", "pixel", "voxel", or None
        plane_segmentation_name : str, optional
            The name of the plane segmentation to be added
        iterator_options : dict, optional
            Options to use when iterating over the image masks
        """
        # Ensure metadata is not mutated by making a deep copy if provided
        if metadata is not None:
            metadata = copy.deepcopy(metadata)

        # Validate mask_type
        if mask_type not in ["image", "pixel", "voxel", None]:
            raise ValueError(f"Invalid mask_type: {mask_type}. Must be one of: 'image', 'pixel', 'voxel', or None")

        # Call the parent class implementation with validated parameters
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
