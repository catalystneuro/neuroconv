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
        
        self._create_integer_id_wrapper()
    
    def _create_integer_id_wrapper(self):
        """Create a wrapper that presents integer IDs to NWB while preserving string IDs internally."""
        # Store original methods and data
        original_get_roi_ids = self.segmentation_extractor.get_roi_ids
        original_get_roi_image_masks = self.segmentation_extractor.get_roi_image_masks
        self._string_to_int_map = {roi_id: i for i, roi_id in enumerate(original_get_roi_ids())}
        self._int_to_string_map = {i: roi_id for roi_id, i in self._string_to_int_map.items()}
        
        # Only override get_roi_ids for external callers (NWB)
        def get_integer_roi_ids():
            return list(range(len(self._string_to_int_map)))
        
        # Override get_roi_image_masks to handle the mismatch
        def patched_get_roi_image_masks(roi_ids=None):
            if roi_ids is None:
                return original_get_roi_image_masks(roi_ids=None)
            
            # The issue: get_roi_locations passes integers, but internally the extractor expects to match against get_roi_ids() results
            # temporarily restore original behavior
            
            current_get_roi_ids = self.segmentation_extractor.get_roi_ids
            
            try:
                # Temporarily restore original get_roi_ids
                self.segmentation_extractor.get_roi_ids = original_get_roi_ids
                
                # Convert integer IDs to strings if needed
                converted_ids = []
                for roi_id in roi_ids:
                    if isinstance(roi_id, int) and roi_id in self._int_to_string_map:
                        converted_ids.append(self._int_to_string_map[roi_id])
                    else:
                        converted_ids.append(roi_id)
                
                #original method with string IDs
                result = original_get_roi_image_masks(roi_ids=converted_ids)
                
            finally:
                self.segmentation_extractor.get_roi_ids = current_get_roi_ids
            
            return result

        self.segmentation_extractor.get_roi_ids = get_integer_roi_ids
        self.segmentation_extractor.get_roi_image_masks = patched_get_roi_image_masks