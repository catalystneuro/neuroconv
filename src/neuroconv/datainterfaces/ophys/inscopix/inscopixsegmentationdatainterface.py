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
        
        # Create a custom subclass of SegmentationExtractor that handles integer ROI IDs
        # but maintains compatibility with Inscopix's string-based cell names
        class IntegerIDInscopixSegmentationExtractor(self.segmentation_extractor.__class__):
            def __init__(self, parent_extractor):
                # Copy all attributes from the parent extractor
                for attr_name in dir(parent_extractor):
                    if not attr_name.startswith('__') and not callable(getattr(parent_extractor, attr_name)):
                        setattr(self, attr_name, getattr(parent_extractor, attr_name))
                
                # Store the parent extractor
                self._parent = parent_extractor
                
                # Create a mapping from integer ID to Inscopix cell name
                self._id_to_cell_name = {}
                for i in range(self._parent.get_num_rois()):
                    self._id_to_cell_name[i] = self._parent.cell_set.get_cell_name(i)
            
            def get_roi_ids(self):
                """Return integer ROI IDs instead of string cell names."""
                return list(range(len(self._id_to_cell_name)))
                
            def get_roi_image_masks(self, roi_ids=None):
                """Get ROI image masks using integer or string IDs."""
                if roi_ids is None:
                    return self._parent.get_roi_image_masks(None)
                    
                # Convert integer IDs to string cell names recognized by Inscopix
                str_roi_ids = []
                for roi_id in roi_ids:
                    if isinstance(roi_id, int):
                        # Use our mapping to get the original cell name
                        str_roi_ids.append(self._id_to_cell_name[roi_id])
                    else:
                        str_roi_ids.append(roi_id)
                        
                return self._parent.get_roi_image_masks(str_roi_ids)
                
            def get_traces(self, roi_ids=None, start_frame=None, end_frame=None, name="raw"):
                """Get traces using integer or string IDs."""
                if roi_ids is None:
                    return self._parent.get_traces(None, start_frame, end_frame, name)
                    
                # Convert integer IDs to string cell names
                str_roi_ids = []
                for roi_id in roi_ids:
                    if isinstance(roi_id, int):
                        str_roi_ids.append(self._id_to_cell_name[roi_id])
                    else:
                        str_roi_ids.append(roi_id)
                        
                return self._parent.get_traces(str_roi_ids, start_frame, end_frame, name)
                
            def get_accepted_list(self):
                """Return integer IDs of accepted ROIs."""
                accepted_str_ids = self._parent.get_accepted_list()
                # Convert string IDs to integer IDs
                return [idx for idx, cell_name in self._id_to_cell_name.items() if cell_name in accepted_str_ids]
                
            def get_rejected_list(self):
                """Return integer IDs of rejected ROIs."""
                rejected_str_ids = self._parent.get_rejected_list()
                # Convert string IDs to integer IDs
                return [idx for idx, cell_name in self._id_to_cell_name.items() if cell_name in rejected_str_ids]

            # Pass through all other methods to the parent extractor
            def __getattr__(self, name):
                return getattr(self._parent, name)
        
        # Replace the segmentation extractor with our custom version
        self.segmentation_extractor = IntegerIDInscopixSegmentationExtractor(self.segmentation_extractor)

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