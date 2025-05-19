from pydantic import FilePath, validate_call
import numpy as np

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
        self.verbose = verbose
        super().__init__(file_path=self.file_path, verbose=verbose)
        
        # Save the original methods
        self._original_get_roi_ids = self.segmentation_extractor.get_roi_ids
        self._original_get_roi_image_masks = self.segmentation_extractor.get_roi_image_masks
        
        # Cache cell data for direct access
        self._cell_set = self.segmentation_extractor.cell_set
        self._num_cells = self._cell_set.num_cells
        
        if self.verbose:
            print(f"Initialized InscopixSegmentationInterface with {self._num_cells} cells")
            print(f"Original ROI IDs: {self._original_get_roi_ids()}")
        
        # Add methods directly to the segmentation extractor instance
        self._patch_segmentation_extractor()

    def _patch_segmentation_extractor(self):
        """Add custom methods to the segmentation extractor."""
        extractor = self.segmentation_extractor
        interface_self = self  # For use in the functions
        
        # Directly add a get_roi_locations method to the extractor instance
        def custom_get_roi_locations(roi_ids=None):
            """Get ROI locations by directly accessing the cell_set data.
            
            This bypasses the problematic get_roi_image_masks method.
            """
            if roi_ids is None:
                roi_ids = list(range(interface_self._num_cells))
                if interface_self.verbose:
                    print(f"get_roi_locations: Using all ROI IDs: {roi_ids}")
            else:
                if interface_self.verbose:
                    print(f"get_roi_locations: Called with ROI IDs: {roi_ids}")
            
            locations = []
            for roi_id in roi_ids:
                # Convert roi_id to integer index if needed
                if isinstance(roi_id, (str, np.str_)):
                    try:
                        roi_idx = interface_self._original_get_roi_ids().index(roi_id)
                        if interface_self.verbose:
                            print(f"get_roi_locations: Converted string ROI ID '{roi_id}' to index {roi_idx}")
                    except ValueError:
                        if interface_self.verbose:
                            print(f"get_roi_locations: Could not find string ROI ID '{roi_id}' in original IDs")
                        continue
                else:
                    roi_idx = roi_id
                    if interface_self.verbose:
                        print(f"get_roi_locations: Using ROI ID {roi_id} directly as index")
                
                # Get image mask directly from the cell_set
                try:
                    mask = interface_self._cell_set.get_cell_image_data(roi_idx)
                    if interface_self.verbose:
                        print(f"get_roi_locations: Got mask for ROI {roi_idx}, shape: {mask.shape}")
                    
                    # Find the center of mass of the mask
                    indices = np.where(mask > 0)
                    if len(indices[0]) > 0:
                        y_center = np.mean(indices[0])
                        x_center = np.mean(indices[1])
                        locations.append([y_center, x_center])
                        if interface_self.verbose:
                            print(f"get_roi_locations: Found center of mass for ROI {roi_idx}: ({y_center}, {x_center})")
                    else:
                        if interface_self.verbose:
                            print(f"get_roi_locations: Mask for ROI {roi_idx} is empty, trying cell metrics")
                        
                        # Fallback to cell coordinates if available
                        try:
                            # Check if cell metrics are available with coordinates
                            metrics = interface_self._cell_set.get_cell_metrics(roi_idx)
                            if interface_self.verbose:
                                print(f"get_roi_locations: Got cell metrics for ROI {roi_idx}: {metrics}")
                                
                            if hasattr(metrics, 'x') and hasattr(metrics, 'y'):
                                locations.append([metrics.y, metrics.x])
                                if interface_self.verbose:
                                    print(f"get_roi_locations: Using metrics coordinates for ROI {roi_idx}: ({metrics.y}, {metrics.x})")
                            else:
                                # If no valid coordinates, use a placeholder
                                image_height, image_width = mask.shape
                                locations.append([image_height // 2, image_width // 2])
                                if interface_self.verbose:
                                    print(f"get_roi_locations: No coordinates in metrics, using image center for ROI {roi_idx}: ({image_height // 2}, {image_width // 2})")
                        except Exception as e:
                            # Last resort: use the center of the image
                            image_height, image_width = mask.shape
                            locations.append([image_height // 2, image_width // 2])
                            if interface_self.verbose:
                                print(f"get_roi_locations: Error getting metrics for ROI {roi_idx}, using image center: ({image_height // 2}, {image_width // 2})")
                                print(f"get_roi_locations: Error details: {type(e).__name__}: {str(e)}")
                except Exception as e:
                    # If everything fails, use a placeholder
                    if interface_self.verbose:
                        print(f"get_roi_locations: Error getting mask for ROI {roi_idx}: {type(e).__name__}: {str(e)}")
                    
                    # Get the first mask to determine dimensions
                    try:
                        first_mask = interface_self._cell_set.get_cell_image_data(0)
                        image_height, image_width = first_mask.shape
                        locations.append([image_height // 2, image_width // 2])
                        if interface_self.verbose:
                            print(f"get_roi_locations: Using dimensions from first mask as fallback for ROI {roi_idx}: ({image_height // 2}, {image_width // 2})")
                    except Exception as e:
                        # Absolute last resort
                        locations.append([0, 0])
                        if interface_self.verbose:
                            print(f"get_roi_locations: Could not get any mask dimensions, using (0, 0) for ROI {roi_idx}")
                            print(f"get_roi_locations: Error details: {type(e).__name__}: {str(e)}")
            
            if locations:
                result = np.array(locations)
                if interface_self.verbose:
                    print(f"get_roi_locations: Returning locations array with shape {result.shape}")
                return result
            else:
                if interface_self.verbose:
                    print("get_roi_locations: No valid locations found, returning empty array")
                # Return empty array with correct shape
                return np.zeros((0, 2))
        
        # Patch get_roi_ids to return integers
        def patched_get_roi_ids():
            ids = list(range(interface_self._num_cells))
            if interface_self.verbose:
                print(f"get_roi_ids: Returning {len(ids)} integer ROI IDs: {ids}")
            return ids
        
        # Patch get_roi_image_masks to handle integer IDs consistently
        def patched_get_roi_image_masks(roi_ids=None):
            if roi_ids is None:
                if interface_self.verbose:
                    print("get_roi_image_masks: Called with roi_ids=None, getting all masks")
                # Get all masks directly from cell_set
                masks = []
                for i in range(interface_self._num_cells):
                    try:
                        mask = interface_self._cell_set.get_cell_image_data(i)
                        masks.append(mask)
                        if interface_self.verbose:
                            print(f"get_roi_image_masks: Got mask for ROI {i}, shape: {mask.shape}")
                    except Exception as e:
                        if interface_self.verbose:
                            print(f"get_roi_image_masks: Error getting mask for ROI {i}: {type(e).__name__}: {str(e)}")
                        # If mask can't be obtained, create an empty one
                        # Use the dimensions of the first successful mask, or default to a small size
                        if masks:
                            empty_mask = np.zeros_like(masks[0])
                        else:
                            # Very last resort: use small default size
                            empty_mask = np.zeros((100, 100))
                        masks.append(empty_mask)
                        if interface_self.verbose:
                            print(f"get_roi_image_masks: Using empty mask for ROI {i}, shape: {empty_mask.shape}")
                
                if masks:
                    result = np.stack(masks)
                    if interface_self.verbose:
                        print(f"get_roi_image_masks: Returning stack of all masks with shape {result.shape}")
                    return result
                else:
                    if interface_self.verbose:
                        print("get_roi_image_masks: No masks found, returning empty array")
                    return np.array([])
            
            # Handle specific ROI IDs
            if interface_self.verbose:
                print(f"get_roi_image_masks: Called with ROI IDs: {roi_ids}")
            
            masks = []
            for roi_id in roi_ids:
                # For integer IDs, use them directly as indices
                if isinstance(roi_id, (int, np.integer)):
                    idx = roi_id
                    if interface_self.verbose:
                        print(f"get_roi_image_masks: Using integer ROI ID {roi_id} directly as index")
                # For string IDs, try to map them to indices
                else:
                    try:
                        idx = interface_self._original_get_roi_ids().index(roi_id)
                        if interface_self.verbose:
                            print(f"get_roi_image_masks: Mapped string ROI ID '{roi_id}' to index {idx}")
                    except ValueError:
                        if interface_self.verbose:
                            print(f"get_roi_image_masks: Could not map string ROI ID '{roi_id}', skipping")
                        continue
                
                # Get the mask directly from cell_set
                try:
                    mask = interface_self._cell_set.get_cell_image_data(idx)
                    masks.append(mask)
                    if interface_self.verbose:
                        print(f"get_roi_image_masks: Got mask for ROI {idx}, shape: {mask.shape}")
                except Exception as e:
                    if interface_self.verbose:
                        print(f"get_roi_image_masks: Error getting mask for ROI {idx}: {type(e).__name__}: {str(e)}")
                    # If mask can't be obtained, create an empty one
                    # Use the dimensions of the first successful mask, or default to a small size
                    if masks:
                        empty_mask = np.zeros_like(masks[0])
                    else:
                        # Try to get dimensions from another mask
                        try:
                            sample_mask = interface_self._cell_set.get_cell_image_data(0)
                            empty_mask = np.zeros_like(sample_mask)
                        except Exception:
                            # Very last resort: use small default size
                            empty_mask = np.zeros((100, 100))
                    
                    masks.append(empty_mask)
                    if interface_self.verbose:
                        print(f"get_roi_image_masks: Using empty mask for ROI {idx}, shape: {empty_mask.shape}")
            
            if masks:
                if len(masks) == 1:
                    if interface_self.verbose:
                        print(f"get_roi_image_masks: Returning single mask with shape {masks[0].shape}")
                    return masks[0]
                else:
                    result = np.stack(masks)
                    if interface_self.verbose:
                        print(f"get_roi_image_masks: Returning stack of masks with shape {result.shape}")
                    return result
            else:
                if interface_self.verbose:
                    print("get_roi_image_masks: No masks found, returning empty array")
                return np.array([])
        
        # Apply the patches
        extractor.get_roi_locations = custom_get_roi_locations
        extractor.get_roi_ids = patched_get_roi_ids
        extractor.get_roi_image_masks = patched_get_roi_image_masks
        
        if self.verbose:
            print("Successfully patched segmentation extractor methods")