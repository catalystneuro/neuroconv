from pydantic import FilePath, validate_call

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class InscopixSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for Inscopix Segmentation Extractor."""

    display_name = "Inscopix Segmentation"
    associated_suffixes = (".isxd",)
    info = "Interface for handling segmentation data from Inscopix."

    @validate_call
    def __init__(self, file_path: FilePath, verbose: bool = False):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the Inscopix segmentation file (.isxd).
        verbose : bool, optional
            If True, enables verbose output during processing. Default is False.
        """
        self.file_path = str(file_path)
        super().__init__(file_path=self.file_path, verbose=verbose)
        
        # Fix ROI ID issue - NWB expects integer IDs, but Inscopix uses strings
        self._fix_roi_id_mismatch()
    
    def _fix_roi_id_mismatch(self):
        """Fix the mismatch between NWB's integer requirements and Inscopix's string IDs."""
        # Store original string IDs
        self._original_roi_ids = self.segmentation_extractor.get_roi_ids()
        
        # Patch get_roi_ids to return integers for NWB
        def get_integer_roi_ids():
            return list(range(len(self._original_roi_ids)))
        
        # Store original method before patching
        original_get_roi_image_masks = self.segmentation_extractor.get_roi_image_masks
        
        # Patch get_roi_image_masks to handle both integer and string inputs
        def patched_get_roi_image_masks(roi_ids=None):
            if roi_ids is None:
                # When None, the original method will use all ROIs
                return original_get_roi_image_masks(roi_ids=None)
            
            # Convert any integers to their corresponding string IDs
            converted_ids = []
            for roi_id in roi_ids:
                if isinstance(roi_id, int) and 0 <= roi_id < len(self._original_roi_ids):
                    # Convert integer to string ID
                    converted_ids.append(self._original_roi_ids[roi_id])
                else:
                    # Keep string IDs as is
                    converted_ids.append(roi_id)
            
            # Call original method with string IDs
            return original_get_roi_image_masks(roi_ids=converted_ids)
        
        # Apply patches
        self.segmentation_extractor.get_roi_ids = get_integer_roi_ids
        self.segmentation_extractor.get_roi_image_masks = patched_get_roi_image_masks