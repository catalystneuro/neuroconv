import copy
import platform
from typing import Optional

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
    plane_name : str, optional
        Name of the imaging plane to load (e.g., "plane0"). Required if the file contains multiple planes.
    verbose : bool, default: False
        Whether to print verbose output during operations
    """

    display_name = "Inscopix Segmentation"
    associated_suffixes = (".isxd",)
    info = "Interface for Inscopix segmentation data from Inscopix proprietary format."
    keywords = ("segmentation", "roi", "inscopix", "cells")

    def __init__(self, file_path: FilePath, plane_name: Optional[str] = None, verbose: bool = False):
        """Initialize the Inscopix segmentation interface.

        Parameters
        ----------
        file_path : FilePath
            Path to the Inscopix cell set file (.isxd)
        plane_name : str, optional
            Name of the imaging plane to load (e.g., "plane0"). Required if the file contains multiple planes.
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

        # Initialize parent class with file_path and optional plane_name
        kwargs = {"file_path": file_path}
        if plane_name is not None:
            kwargs["plane_name"] = plane_name

        # Initialize the parent class
        super().__init__(**kwargs)
        self.verbose = verbose

        # Check if we need to raise an error about missing plane_name
        try:
            # Try to access the extractor to see if it fails due to missing plane_name
            extractor = self._extractor_instance
            # If we got this far, check if we can identify a multi-plane issue
            if hasattr(extractor, "get_num_planes") and extractor.get_num_planes() > 1 and plane_name is None:
                raise ValueError(
                    f"Multiple imaging planes detected in {file_path}. "
                    f"Please specify which plane to use with the 'plane_name' parameter."
                )
        except Exception as e:
            # If there's an error that mentions planes, re-raise with a clearer message
            if "plane" in str(e).lower():
                raise ValueError(
                    f"Error loading Inscopix segmentation data: {str(e)}. "
                    f"You might need to specify a valid plane_name parameter."
                ) from e
            # Otherwise, just re-raise the original error
            raise

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
