from pydantic import FilePath
import copy
import platform
import numpy as np

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
        
        # Initialize the parent class with file_path
        super().__init__(file_path=file_path)
        self.verbose = verbose
        
        # Validate that we have a working segmentation extractor
        self._check_extractor()
        
        # Create ROI ID mapping (str -> int) if needed
        self._roi_id_mapping = None
        self._initialize_roi_id_mapping()
    
    def _check_extractor(self):
        """Verify that the segmentation extractor is initialized correctly."""
        try:
            extractor = self.segmentation_extractor
            num_rois = extractor.get_num_rois()
            if num_rois == 0 and self.verbose:
                print("Warning: No ROIs found in the segmentation data.")
        except Exception as e:
            raise ValueError(
                f"Error initializing Inscopix segmentation extractor from {self.source_data.get('file_path')}: {str(e)}. "
                f"Please check that the file exists and is a valid Inscopix Cell Set file (.isxd)."
            ) from e
    
    def _initialize_roi_id_mapping(self):
        """Create a mapping from string ROI IDs to integer IDs if needed."""
        roi_ids = self.segmentation_extractor.get_roi_ids()
        
        # Check if any ROI IDs are non-integer - if so, create a mapping
        if not all(isinstance(id, int) for id in roi_ids):
            self._roi_id_mapping = {roi_id: i for i, roi_id in enumerate(roi_ids)}
            if self.verbose:
                print(f"Created mapping from ROI IDs to integers: {self._roi_id_mapping}")
    
    def _map_roi_ids(self, roi_ids):
        """Map ROI IDs to integers if needed."""
        if self._roi_id_mapping is None:
            return roi_ids
        
        # Map the IDs
        return [self._roi_id_mapping[roi_id] for roi_id in roi_ids if roi_id in self._roi_id_mapping]
    
    def _filter_valid_roi_ids(self, roi_ids=None):
        """Filter ROI IDs to include only valid ones."""
        all_ids = self.segmentation_extractor.get_roi_ids()
        
        if roi_ids is None:
            return all_ids
        
        # Filter to only include valid IDs
        valid_ids = [roi_id for roi_id in roi_ids if roi_id in all_ids]
        
        if len(valid_ids) < len(roi_ids) and self.verbose:
            print(f"Warning: Some requested ROI IDs are not valid. Valid IDs: {all_ids}")
            print(f"Using only valid IDs: {valid_ids}")
        
        return valid_ids
    
    def get_metadata(self) -> dict:
        """
        Retrieve metadata from the segmentation extractor and ensure it's properly formatted.
        
        Returns
        -------
        dict
            The metadata dictionary containing information from the segmentation extractor
        """
        # Get metadata from parent class
        metadata = super().get_metadata()
        
        # Ensure ROI IDs are properly handled in the metadata
        if "Ophys" in metadata and "ImageSegmentation" in metadata["Ophys"]:
            if "plane_segmentations" in metadata["Ophys"]["ImageSegmentation"]:
                for plane_seg in metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"]:
                    if "roi_table" in plane_seg and "ids" in plane_seg["roi_table"]:
                        # Ensure ROI IDs are integers
                        original_ids = plane_seg["roi_table"]["ids"]
                        if self._roi_id_mapping is not None:
                            mapped_ids = [self._roi_id_mapping.get(id, i) for i, id in enumerate(original_ids)]
                            plane_seg["roi_table"]["ids"] = mapped_ids
        
        # Return a deep copy to prevent mutation
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
            Options to use when iterating over the image masks of the segmentation extractor
        """
        # Ensure metadata is not mutated by making a deep copy if provided
        if metadata is not None:
            metadata = copy.deepcopy(metadata)
            
        # Validate mask_type
        if mask_type not in ["image", "pixel", "voxel", None]:
            raise ValueError(f"Invalid mask_type: {mask_type}. Must be one of: 'image', 'pixel', 'voxel', or None")
            
        # Get the segmentation extractor, either full or stubbed
        if stub_test:
            stub_frames = min([stub_frames, self.segmentation_extractor.get_num_frames()])
            segmentation_extractor = self.segmentation_extractor.frame_slice(start_frame=0, end_frame=stub_frames)
        else:
            segmentation_extractor = self.segmentation_extractor
            
        # Apply ROI ID mapping to make sure we have integer IDs for NWB
        if self._roi_id_mapping is not None:
            # We can't modify the extractor directly, but we can ensure the metadata is correct
            if metadata is not None and "Ophys" in metadata and "ImageSegmentation" in metadata["Ophys"]:
                for plane_seg in metadata["Ophys"]["ImageSegmentation"].get("plane_segmentations", []):
                    if "roi_table" in plane_seg and "ids" in plane_seg["roi_table"]:
                        # Map string IDs to integers
                        original_ids = plane_seg["roi_table"]["ids"]
                        mapped_ids = [self._roi_id_mapping.get(id, i) for i, id in enumerate(original_ids)]
                        plane_seg["roi_table"]["ids"] = mapped_ids
        

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