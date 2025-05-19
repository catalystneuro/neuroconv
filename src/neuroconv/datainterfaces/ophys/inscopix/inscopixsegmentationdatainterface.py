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

        # Initialize parent class with the file path
        super().__init__(file_path=self.file_path, verbose=verbose)

        # Store original get_roi_image_masks method
        self._original_get_roi_image_masks = self.segmentation_extractor.get_roi_image_masks

        # Override get_roi_image_masks to handle integer ROI IDs
        def patched_get_roi_image_masks(self, ids=None):
            """Patched method to handle integer ROI IDs."""
            if ids is None:
                return self._original_get_roi_image_masks(ids)

            # Convert integer IDs to string format (e.g., 0 -> 'C0')
            str_roi_ids = []
            for roi_id in ids:
                if isinstance(roi_id, int):
                    str_roi_ids.append(f"C{roi_id}")
                else:
                    str_roi_ids.append(roi_id)

            # Call original method with string IDs
            return self._original_get_roi_image_masks(str_roi_ids)

        # Apply patched method with the correct 'self' binding
        import types

        self.segmentation_extractor.get_roi_image_masks = types.MethodType(
            patched_get_roi_image_masks, self.segmentation_extractor
        )

    def get_metadata(self) -> dict:
        """
        Extract metadata from the Inscopix file.

        Returns
        -------
        dict
            Metadata dictionary for NWB file.
        """
        # Get base metadata from parent class
        metadata = super().get_metadata()
        return metadata
