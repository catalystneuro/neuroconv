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
        
        # Store original methods for later use
        self._original_get_roi_ids = self.segmentation_extractor.get_roi_ids
        
        # Create a simple method to get integer ROI IDs
        def get_integer_roi_ids():
            return list(range(self.segmentation_extractor.get_num_rois()))
        
        # Replace the get_roi_ids method
        self.segmentation_extractor.get_roi_ids = get_integer_roi_ids
        
        # Create a mapping for get_roi_image_masks
        def modified_get_roi_image_masks(roi_ids=None):
            # If roi_ids is None, return all masks
            if roi_ids is None:
                return self.segmentation_extractor._original_get_roi_image_masks(None)
            
            # If roi_ids contains integers, convert them to string IDs ("C0", "C1", etc.)
            string_ids = []
            for roi_id in roi_ids:
                if isinstance(roi_id, int):
                    string_ids.append(f"C{roi_id}")
                else:
                    string_ids.append(roi_id)
                    
            # Call the original method with string IDs
            return self.segmentation_extractor._original_get_roi_image_masks(string_ids)
        
        # Store the original method and set up our patched version
        self.segmentation_extractor._original_get_roi_image_masks = self.segmentation_extractor.get_roi_image_masks
        self.segmentation_extractor.get_roi_image_masks = modified_get_roi_image_masks

    def add_to_nwbfile(self, nwbfile, metadata=None, **kwargs):
        """
        Add the segmentation data to an NWB file.
        
        This method overrides the parent method to ensure compatibility with NWB format.
        
        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the segmentation data to.
        metadata : dict, optional
            Metadata for the NWB file.
        **kwargs : dict
            Additional keyword arguments.
        """
        # Set the conversion options
        mask_type = kwargs.pop('mask_type', 'image')
        include_roi_centroids = kwargs.pop('include_roi_centroids', True)
        include_roi_acceptance = kwargs.pop('include_roi_acceptance', True)
        
        # Ensure we're using integer IDs for the segmentation data
        # This is critical for NWB compatibility
        from neuroconv.tools.roiextractors import add_segmentation_to_nwbfile
        
        # Call the parent method with our custom parameters
        add_segmentation_to_nwbfile(
            segmentation_extractor=self.segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            include_roi_centroids=include_roi_centroids,
            include_roi_acceptance=include_roi_acceptance,
            mask_type=mask_type,
            **kwargs
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