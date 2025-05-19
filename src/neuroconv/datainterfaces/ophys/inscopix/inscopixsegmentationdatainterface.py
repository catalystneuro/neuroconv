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

        # Initialize parent class with the file path
        super().__init__(file_path=self.file_path, verbose=verbose)
        
        # Replace the extractor with a custom version that handles integer IDs
        self.segmentation_extractor = _IntegerIDHandler(self.segmentation_extractor)


class _IntegerIDHandler:
    """
    A wrapper class that handles the conversion between integer IDs and string IDs.
    
    This class wraps the original segmentation extractor and provides methods
    that are compatible with both integer IDs and string IDs.
    """
    
    def __init__(self, extractor):
        """
        Initialize the wrapper with the original extractor.
        
        Parameters
        ----------
        extractor : SegmentationExtractor
            The original segmentation extractor.
        """
        self._extractor = extractor
        
        # Create a mapping between integer IDs and string IDs
        self._string_to_int = {}
        self._int_to_string = {}
        for i, string_id in enumerate(self._extractor.get_roi_ids()):
            self._string_to_int[string_id] = i
            self._int_to_string[i] = string_id
        
        # Store important attributes
        self.cell_set = self._extractor.cell_set
    
    def get_roi_ids(self):
        """Return integer ROI IDs instead of string cell names."""
        return list(range(len(self._int_to_string)))
    
    def get_roi_image_masks(self, roi_ids=None):
        """Get ROI image masks using integer or string IDs."""
        if roi_ids is None:
            return self._extractor.get_roi_image_masks(None)
            
        # Convert to string IDs if needed
        str_ids = []
        for roi_id in roi_ids:
            if isinstance(roi_id, int):
                str_ids.append(self._int_to_string[roi_id])
            else:
                str_ids.append(roi_id)
                
        return self._extractor.get_roi_image_masks(str_ids)
    
    def get_roi_pixel_masks(self, roi_ids=None):
        """Get ROI pixel masks using integer or string IDs."""
        if roi_ids is None:
            return self._extractor.get_roi_pixel_masks(None)
            
        # Convert to string IDs if needed
        str_ids = []
        for roi_id in roi_ids:
            if isinstance(roi_id, int):
                str_ids.append(self._int_to_string[roi_id])
            else:
                str_ids.append(roi_id)
                
        return self._extractor.get_roi_pixel_masks(str_ids)
    
    def get_roi_locations(self, roi_ids=None):
        """Get ROI locations using integer or string IDs."""
        if roi_ids is None:
            roi_idx = range(len(self._int_to_string))
        else:
            roi_idx = []
            for roi_id in roi_ids:
                if isinstance(roi_id, int):
                    roi_idx.append(roi_id)
                else:
                    roi_idx.append(self._string_to_int[roi_id])
        
        # Create a result array
        roi_locations = np.zeros((2, len(roi_idx)), dtype="int")
        
        # Get the locations one by one
        for i, idx in enumerate(roi_idx):
            string_id = self._int_to_string[idx]
            image_mask = self._extractor.get_roi_image_masks([string_id])
            
            # Compute centroid
            coords = np.where(image_mask > 0)
            if coords[0].size > 0:
                roi_locations[0, i] = int(np.median(coords[0]))
                roi_locations[1, i] = int(np.median(coords[1]))
                
        return roi_locations
    
    def get_traces(self, roi_ids=None, start_frame=None, end_frame=None, name="raw"):
        """Get traces using integer or string IDs."""
        if roi_ids is None:
            return self._extractor.get_traces(None, start_frame, end_frame, name)
            
        # Convert to string IDs if needed
        str_ids = []
        for roi_id in roi_ids:
            if isinstance(roi_id, int):
                str_ids.append(self._int_to_string[roi_id])
            else:
                str_ids.append(roi_id)
                
        return self._extractor.get_traces(str_ids, start_frame, end_frame, name)
    
    def get_accepted_list(self):
        """Return integer IDs of accepted ROIs."""
        accepted_str_ids = self._extractor.get_accepted_list()
        return [self._string_to_int[sid] for sid in accepted_str_ids]
    
    def get_rejected_list(self):
        """Return integer IDs of rejected ROIs."""
        rejected_str_ids = self._extractor.get_rejected_list()
        return [self._string_to_int[sid] for sid in rejected_str_ids]
    
    def get_image_size(self):
        """Get the image size."""
        return self._extractor.get_image_size()
    
    def get_num_rois(self):
        """Get the number of ROIs."""
        return len(self._int_to_string)
    
    def get_num_frames(self):
        """Get the number of frames in the recording."""
        return self._extractor.get_num_frames()
    
    def get_sampling_frequency(self):
        """Get the sampling frequency in Hz."""
        return self._extractor.get_sampling_frequency()
    
    def frame_to_time(self, frames):
        """Convert frame indices to times in seconds."""
        return self._extractor.frame_to_time(frames)
    
    def __getattr__(self, name):
        """Forward all other attribute access to the original extractor."""
        return getattr(self._extractor, name)