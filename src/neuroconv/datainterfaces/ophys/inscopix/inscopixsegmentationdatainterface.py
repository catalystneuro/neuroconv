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
        
        # Store a mapping between integer IDs and cell IDs (strings like "C0", "C1")
        self._id_mapping = {}
        for i in range(self.segmentation_extractor.get_num_rois()):
            cell_name = self.segmentation_extractor.cell_set.get_cell_name(i)
            self._id_mapping[i] = cell_name
        
        # Store the original methods
        original_get_roi_ids = self.segmentation_extractor.get_roi_ids
        original_get_roi_image_masks = self.segmentation_extractor.get_roi_image_masks
        original_get_traces = self.segmentation_extractor.get_traces
        original_get_accepted_list = self.segmentation_extractor.get_accepted_list
        original_get_rejected_list = self.segmentation_extractor.get_rejected_list
        
        # Override get_roi_ids to return integer IDs
        def new_get_roi_ids():
            return list(range(len(self._id_mapping)))
        
        # Override get_roi_image_masks to handle integer IDs
        def new_get_roi_image_masks(roi_ids=None):
            if roi_ids is None:
                return original_get_roi_image_masks(roi_ids)
            
            # Convert integer IDs to string cell names
            str_roi_ids = []
            for roi_id in roi_ids:
                if isinstance(roi_id, int):
                    # Use the mapping to get the original cell name
                    str_roi_ids.append(self._id_mapping.get(roi_id, f"C{roi_id}"))
                else:
                    str_roi_ids.append(roi_id)
            
            return original_get_roi_image_masks(str_roi_ids)
        
        # Override get_traces to handle integer IDs
        def new_get_traces(roi_ids=None, start_frame=None, end_frame=None, name="raw"):
            if roi_ids is None:
                return original_get_traces(roi_ids, start_frame, end_frame, name)
            
            # Convert integer IDs to string cell names
            str_roi_ids = []
            for roi_id in roi_ids:
                if isinstance(roi_id, int):
                    str_roi_ids.append(self._id_mapping.get(roi_id, f"C{roi_id}"))
                else:
                    str_roi_ids.append(roi_id)
            
            return original_get_traces(str_roi_ids, start_frame, end_frame, name)
        
        # Override get_accepted_list to return integer IDs
        def new_get_accepted_list():
            str_ids = original_get_accepted_list()
            # Convert string IDs to integer IDs
            return [i for i, cell_name in self._id_mapping.items() if cell_name in str_ids]
        
        # Override get_rejected_list to return integer IDs
        def new_get_rejected_list():
            str_ids = original_get_rejected_list()
            # Convert string IDs to integer IDs
            return [i for i, cell_name in self._id_mapping.items() if cell_name in str_ids]
        
        # Replace all methods
        self.segmentation_extractor.get_roi_ids = new_get_roi_ids
        self.segmentation_extractor.get_roi_image_masks = new_get_roi_image_masks
        self.segmentation_extractor.get_traces = new_get_traces
        self.segmentation_extractor.get_accepted_list = new_get_accepted_list
        self.segmentation_extractor.get_rejected_list = new_get_rejected_list
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
