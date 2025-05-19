from pydantic import FilePath, validate_call

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class InscopixSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for Inscopix Segmentation Extractor.
    
    This interface handles segmentation data from Inscopix (.isxd) files.
    """

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
        
        # Save the original methods we'll need to patch
        self._original_get_roi_ids = self.segmentation_extractor.get_roi_ids
        self._original_get_roi_image_masks = self.segmentation_extractor.get_roi_image_masks
        
        # Create int-to-string and string-to-int mappings
        original_ids = self._original_get_roi_ids()
        self._id_map = {i: id for i, id in enumerate(original_ids)}
        
        # Patch the methods
        self._patch_segmentation_extractor()

    def _patch_segmentation_extractor(self):
        """Patch the segmentation extractor to use integer IDs."""
        # Store self reference for use in methods
        interface_self = self
        
        # Override get_roi_ids to return integer IDs
        def patched_get_roi_ids():
            return list(range(len(interface_self._id_map)))
        
        # Override get_roi_image_masks to handle integer IDs
        def patched_get_roi_image_masks(roi_ids=None):
            if roi_ids is None:
                return interface_self._original_get_roi_image_masks(roi_ids=None)
            
            # Convert integer IDs to original string IDs
            converted_ids = []
            for roi_id in roi_ids:
                if isinstance(roi_id, int) and roi_id in interface_self._id_map:
                    converted_ids.append(interface_self._id_map[roi_id])
                else:
                    converted_ids.append(roi_id)
            
            return interface_self._original_get_roi_image_masks(roi_ids=converted_ids)
        
        # Apply the patches
        self.segmentation_extractor.get_roi_ids = patched_get_roi_ids
        self.segmentation_extractor.get_roi_image_masks = patched_get_roi_image_masks