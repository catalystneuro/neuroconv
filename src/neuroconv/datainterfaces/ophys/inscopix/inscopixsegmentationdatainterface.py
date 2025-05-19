import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile
import types

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
        
        # Initialize the base class
        super().__init__(file_path=self.file_path, verbose=verbose)
        
        # Save original ROI IDs and create mappings
        self._prepare_roi_mappings()
        
        # Override get_roi_ids to return integer IDs
        self._orig_get_roi_ids = self.segmentation_extractor.get_roi_ids
        
        def get_roi_ids_override(self):
            return self._int_roi_ids
        
        self.segmentation_extractor.get_roi_ids = types.MethodType(get_roi_ids_override, self.segmentation_extractor)
        
        # Override get_roi_image_masks to handle integer IDs
        self._orig_get_roi_image_masks = self.segmentation_extractor.get_roi_image_masks
        
        def get_roi_image_masks_override(self, roi_ids=None):
            if roi_ids is None:
                roi_ids = self.get_roi_ids()
            
            # Convert integer IDs to string IDs that the extractor understands
            str_roi_ids = []
            for roi_id in roi_ids:
                if isinstance(roi_id, int):
                    # Convert integer ID to string (e.g., 0 -> 'C0')
                    str_roi_ids.append(f'C{roi_id}')
                else:
                    str_roi_ids.append(roi_id)
            
            # Call the original method with string IDs
            return self._orig_get_roi_image_masks(str_roi_ids)
        
        self.segmentation_extractor.get_roi_image_masks = types.MethodType(get_roi_image_masks_override, self.segmentation_extractor)
    
    def _prepare_roi_mappings(self):
        """
        Create mappings between string and integer ROI IDs.
        """
        # Get original string ROI IDs (e.g., 'C0', 'C1', etc.)
        orig_roi_ids = self.segmentation_extractor.get_roi_ids()
        self._str_roi_ids = orig_roi_ids
        
        # Create integer ROI IDs (e.g., 0, 1, etc.)
        self._int_roi_ids = []
        self._str_to_int = {}  # String ID to integer ID mapping
        self._int_to_str = {}  # Integer ID to string ID mapping
        
        for roi_id in orig_roi_ids:
            if isinstance(roi_id, str) and roi_id.startswith('C'):
                try:
                    int_id = int(roi_id[1:])
                    self._int_roi_ids.append(int_id)
                    self._str_to_int[roi_id] = int_id
                    self._int_to_str[int_id] = roi_id
                except ValueError:
                    # If conversion fails, keep the original ID
                    self._int_roi_ids.append(roi_id)
                    self._str_to_int[roi_id] = roi_id
                    self._int_to_str[roi_id] = roi_id
            else:
                self._int_roi_ids.append(roi_id)
                self._str_to_int[roi_id] = roi_id
                self._int_to_str[roi_id] = roi_id
    
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
        
        # Update ophys metadata
        if "Ophys" in metadata:
            # Update Device info
            if "Device" in metadata["Ophys"] and len(metadata["Ophys"]["Device"]) > 0:
                metadata["Ophys"]["Device"][0].update({
                    "name": "Microscope",
                    "description": "Inscopix NVista3 Microscope (SN: 11132301)"
                })
            
            # Update ImagingPlane info
            if "ImagingPlane" in metadata["Ophys"] and len(metadata["Ophys"]["ImagingPlane"]) > 0:
                metadata["Ophys"]["ImagingPlane"][0].update({
                    "name": "ImagingPlane",
                    "description": "Inscopix imaging plane at 1000um focus",
                    "device": "Microscope"
                })
        
        return metadata
    
    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        stub_test: bool = False,
        stub_frames: int = 100,
        include_background_segmentation: bool = False,
        include_roi_centroids: bool = True,
        include_roi_acceptance: bool = True,
        mask_type: str | None = "image",
        plane_segmentation_name: str | None = None,
        iterator_options: dict | None = None,
    ):
        """
        Add segmentation data to an NWB file.
        
        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the data to.
        metadata : dict, optional
            Metadata dictionary.
        stub_test : bool, default: False
            Whether this is a stub test.
        stub_frames : int, default: 100
            Number of frames to use for stub test.
        include_background_segmentation : bool, default: False
            Whether to include background segmentation.
        include_roi_centroids : bool, default: True
            Whether to include ROI centroids.
        include_roi_acceptance : bool, default: True
            Whether to include ROI acceptance status.
        mask_type : str, default: 'image'
            Type of mask to use.
        plane_segmentation_name : str, optional
            Name of the plane segmentation.
        iterator_options : dict, optional
            Options for the iterator.
        """
        
        # Use a default name for plane segmentation if not provided
        if plane_segmentation_name is None:
            plane_segmentation_name = "PlaneSegmentation"
        
        # Call parent method
        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            stub_frames=stub_frames,
            include_background_segmentation=include_background_segmentation,
            include_roi_centroids=include_roi_centroids,
            include_roi_acceptance=include_roi_acceptance,
            mask_type=mask_type,
            plane_segmentation_name=plane_segmentation_name,
            iterator_options=iterator_options
        )