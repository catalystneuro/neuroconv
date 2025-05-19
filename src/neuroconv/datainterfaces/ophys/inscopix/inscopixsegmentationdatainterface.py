import numpy as np
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
        self.verbose = verbose
        super().__init__(file_path=self.file_path, verbose=verbose)

        # Cache cell data for direct access
        self._cell_set = self.segmentation_extractor.cell_set
        self._num_cells = self._cell_set.num_cells

        if self.verbose:
            print(f"Initialized InscopixSegmentationInterface with {self._num_cells} cells")
            print(f"Original ROI IDs: {self.segmentation_extractor.get_roi_ids()}")

        # Patch the segmentation extractor
        self._patch_segmentation_extractor()

    def _patch_segmentation_extractor(self):
        """Patch the segmentation extractor with methods that work correctly."""
        extractor = self.segmentation_extractor
        interface_self = self  # For use in the methods

        # Override get_roi_ids to return integers
        def patched_get_roi_ids():
            ids = list(range(interface_self._num_cells))
            if interface_self.verbose:
                print(f"get_roi_ids: Returning {len(ids)} integer ROI IDs: {ids}")
            return ids

        # Override get_roi_image_masks to handle integer IDs correctly
        def patched_get_roi_image_masks(roi_ids=None):
            if interface_self.verbose:
                print(f"get_roi_image_masks called with roi_ids={roi_ids}")

            if roi_ids is None:
                # Get all masks
                masks = []
                for i in range(interface_self._num_cells):
                    try:
                        mask = interface_self._cell_set.get_cell_image_data(i)
                        masks.append(mask)
                        if interface_self.verbose:
                            print(f"Got mask for cell {i} with shape {mask.shape}")
                    except Exception as e:
                        if interface_self.verbose:
                            print(f"Error getting mask for cell {i}: {str(e)}")
                        # Create an empty mask with the same shape as others
                        if masks:
                            empty_mask = np.zeros_like(masks[0])
                        else:
                            # Try to get dimensions from a single cell
                            try:
                                sample_mask = interface_self._cell_set.get_cell_image_data(0)
                                empty_mask = np.zeros_like(sample_mask)
                            except Exception:
                                # Last resort: use small default size
                                empty_mask = np.zeros((100, 100))
                        masks.append(empty_mask)

                if masks:
                    return np.stack(masks)
                return np.array([])

            # Handle specific ROI IDs
            masks = []
            for roi_id in roi_ids:
                try:
                    # Use the ROI ID directly as the index
                    mask = interface_self._cell_set.get_cell_image_data(roi_id)
                    masks.append(mask)
                    if interface_self.verbose:
                        print(f"Got mask for ROI ID {roi_id} with shape {mask.shape}")
                except Exception as e:
                    if interface_self.verbose:
                        print(f"Error getting mask for ROI ID {roi_id}: {str(e)}")
                    # Create an empty mask with the same shape as others
                    if masks:
                        empty_mask = np.zeros_like(masks[0])
                    else:
                        # Try to get dimensions from a single cell
                        try:
                            sample_mask = interface_self._cell_set.get_cell_image_data(0)
                            empty_mask = np.zeros_like(sample_mask)
                        except Exception:
                            # Last resort: use small default size
                            empty_mask = np.zeros((100, 100))
                    masks.append(empty_mask)

            if len(masks) == 1:
                return masks[0]
            elif masks:
                return np.stack(masks)
            else:
                return np.array([])

        # Add a direct implementation of get_roi_locations
        def patched_get_roi_locations(roi_ids=None):
            if interface_self.verbose:
                print(f"get_roi_locations called with roi_ids={roi_ids}")

            if roi_ids is None:
                roi_ids = list(range(interface_self._num_cells))

            locations = []
            for roi_id in roi_ids:
                try:
                    # Get mask directly from cell_set
                    mask = interface_self._cell_set.get_cell_image_data(roi_id)

                    # Find the center of mass
                    indices = np.where(mask > 0)
                    if len(indices[0]) > 0:
                        y_center = np.mean(indices[0])
                        x_center = np.mean(indices[1])
                        locations.append([y_center, x_center])
                        if interface_self.verbose:
                            print(f"Found centroid for ROI {roi_id}: [{y_center}, {x_center}]")
                    else:
                        # Fallback to center of image
                        y_center = mask.shape[0] // 2
                        x_center = mask.shape[1] // 2
                        locations.append([y_center, x_center])
                        if interface_self.verbose:
                            print(f"Empty mask for ROI {roi_id}, using center: [{y_center}, {x_center}]")
                except Exception as e:
                    if interface_self.verbose:
                        print(f"Error processing ROI {roi_id}: {str(e)}")
                    # Use a default location
                    try:
                        # Try to get dimensions from another cell
                        sample_mask = interface_self._cell_set.get_cell_image_data(0)
                        y_center = sample_mask.shape[0] // 2
                        x_center = sample_mask.shape[1] // 2
                    except Exception:
                        # Last resort: use arbitrary coordinates
                        y_center, x_center = 50, 50

                    locations.append([y_center, x_center])
                    if interface_self.verbose:
                        print(f"Using fallback location for ROI {roi_id}: [{y_center}, {x_center}]")

            if locations:
                result = np.array(locations)
                if interface_self.verbose:
                    print(f"Returning locations array with shape {result.shape}")
                return result
            else:
                if interface_self.verbose:
                    print("No locations found, returning empty array")
                return np.zeros((0, 2))

        # Apply the patches
        extractor.get_roi_ids = patched_get_roi_ids
        extractor.get_roi_image_masks = patched_get_roi_image_masks
        extractor.get_roi_locations = patched_get_roi_locations

    def add_to_nwbfile(self, nwbfile, metadata=None, **kwargs):
        """Add segmentation data to an NWBFile."""
        if self.verbose:
            print("Calling add_to_nwbfile...")

        # Override mask_type to "image" if not specified
        if "mask_type" not in kwargs:
            kwargs["mask_type"] = "image"
            if self.verbose:
                print("Setting mask_type to 'image'")

        # Call the parent method with our patched extractor
        try:
            super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **kwargs)
            if self.verbose:
                print("Successfully added to NWBFile")
        except Exception as e:
            if self.verbose:
                print(f"Error in add_to_nwbfile: {type(e).__name__}: {str(e)}")
            raise
