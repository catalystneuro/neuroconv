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
        
        # Create a wrapper that presents integer IDs to NWB while preserving string IDs internally
        self._create_integer_id_wrapper()

    def _create_integer_id_wrapper(self):
        """Create a wrapper that presents integer IDs to NWB while preserving string IDs internally."""
        # Store original methods and data
        original_get_roi_ids = self.segmentation_extractor.get_roi_ids
        original_get_roi_image_masks = self.segmentation_extractor.get_roi_image_masks
        original_get_roi_pixel_masks = self.segmentation_extractor.get_roi_pixel_masks
        
        # Create mappings between string and integer IDs
        string_roi_ids = original_get_roi_ids()
        self._string_to_int_map = {roi_id: i for i, roi_id in enumerate(string_roi_ids)}
        self._int_to_string_map = {i: roi_id for roi_id, i in self._string_to_int_map.items()}

        # Override get_roi_ids to return integer IDs
        def get_integer_roi_ids():
            return list(range(len(self._string_to_int_map)))

        # Override get_roi_image_masks to handle integer IDs
        def patched_get_roi_image_masks(roi_ids=None):
            if roi_ids is None:
                return original_get_roi_image_masks(roi_ids=None)

            # Convert integer IDs to string IDs
            converted_ids = []
            for roi_id in roi_ids:
                if isinstance(roi_id, int) and roi_id in self._int_to_string_map:
                    converted_ids.append(self._int_to_string_map[roi_id])
                else:
                    converted_ids.append(roi_id)

            return original_get_roi_image_masks(roi_ids=converted_ids)

        # Override get_roi_pixel_masks to handle integer IDs
        def patched_get_roi_pixel_masks(roi_ids=None):
            if roi_ids is None:
                return original_get_roi_pixel_masks(roi_ids=None)

            # Convert integer IDs to string IDs
            converted_ids = []
            for roi_id in roi_ids:
                if isinstance(roi_id, int) and roi_id in self._int_to_string_map:
                    converted_ids.append(self._int_to_string_map[roi_id])
                else:
                    converted_ids.append(roi_id)

            return original_get_roi_pixel_masks(roi_ids=converted_ids)

        # Replace the methods on the segmentation extractor
        self.segmentation_extractor.get_roi_ids = get_integer_roi_ids
        self.segmentation_extractor.get_roi_image_masks = patched_get_roi_image_masks
        self.segmentation_extractor.get_roi_pixel_masks = patched_get_roi_pixel_masks