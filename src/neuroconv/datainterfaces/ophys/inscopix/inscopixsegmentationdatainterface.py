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
        self._patch_extractor_for_nwb()
    
    def _patch_extractor_for_nwb(self):
        """Convert string ROI IDs to integers for NWB compatibility."""
        self._original_roi_ids = self.segmentation_extractor.get_roi_ids()
        
        def get_integer_roi_ids():
            return list(range(len(self._original_roi_ids)))
        
        # Replace get_roi_image_masks to handle integer indexing
        original_get_roi_image_masks = self.segmentation_extractor.get_roi_image_masks
        
        def patched_get_roi_image_masks(roi_ids=None):
            if roi_ids is not None:
                # Convert integer indices to original string IDs
                roi_ids = [self._original_roi_ids[i] if isinstance(i, int) and i < len(self._original_roi_ids) else i 
                          for i in roi_ids]
            return original_get_roi_image_masks(roi_ids=roi_ids)
        
        self.segmentation_extractor.get_roi_ids = get_integer_roi_ids
        self.segmentation_extractor.get_roi_image_masks = patched_get_roi_image_masks