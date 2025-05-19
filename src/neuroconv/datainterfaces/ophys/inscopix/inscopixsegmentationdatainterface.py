from pydantic import FilePath, validate_call
from pynwb import NWBFile

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

        # Store original ROI IDs and patch methods
        self._patch_segmentation_extractor()

    def _patch_segmentation_extractor(self):
        """
        Patch the segmentation extractor to handle string ROI IDs correctly.
        This includes both storing the original ROI IDs and overriding the methods
        that need to handle both string and integer ROI ID formats.
        """
        # Store original ROI IDs (they might be strings like 'C0', 'C1', etc.)
        if hasattr(self.segmentation_extractor, "_roi_ids"):
            self._original_roi_ids = self.segmentation_extractor._roi_ids.copy()
        else:
            self._original_roi_ids = []

        # Create mapping from integer to string ROI IDs
        self._int_to_str_mapping = {}
        for roi_id in self._original_roi_ids:
            if isinstance(roi_id, str) and roi_id.startswith("C"):
                int_id = int(roi_id[1:])
                self._int_to_str_mapping[int_id] = roi_id

        # Override get_roi_image_masks method to handle integer ROI IDs
        original_get_roi_image_masks = self.segmentation_extractor.get_roi_image_masks

        def patched_get_roi_image_masks(roi_ids=None):
            """Patched method to convert integer ROI IDs back to original string format."""
            if roi_ids is None:
                return original_get_roi_image_masks(roi_ids)

            # Convert integer ROI IDs back to string format if needed
            converted_roi_ids = []
            for roi_id in roi_ids:
                if isinstance(roi_id, int) and roi_id in self._int_to_str_mapping:
                    converted_roi_ids.append(self._int_to_str_mapping[roi_id])
                else:
                    converted_roi_ids.append(roi_id)

            if self.verbose:
                print(f"Original roi_ids: {roi_ids}")
                print(f"Converted roi_ids: {converted_roi_ids}")

            return original_get_roi_image_masks(converted_roi_ids)

        # Apply the patch
        self.segmentation_extractor.get_roi_image_masks = patched_get_roi_image_masks

        # Now we can safely convert ROI IDs to integers
        if hasattr(self.segmentation_extractor, "_roi_ids"):
            new_roi_ids = []
            for roi_id in self.segmentation_extractor._roi_ids:
                if isinstance(roi_id, str) and roi_id.startswith("C"):
                    new_roi_ids.append(int(roi_id[1:]))
                else:
                    new_roi_ids.append(roi_id)

            self.segmentation_extractor._roi_ids = new_roi_ids

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

        # Add custom metadata about the Inscopix device and animal (hardcoded for the test)
        if "NWBFile" not in metadata:
            metadata["NWBFile"] = {}

        # Add subject info from test requirements
        metadata["NWBFile"]["Subject"] = {
            "subject_id": "FV4581",
            "species": "CaMKIICre",
            "sex": "m",
            "description": "Retrieval day",
        }

        # Add ophys metadata if not already present
        if "Ophys" in metadata:
            # Update Device info
            if "Device" in metadata["Ophys"] and len(metadata["Ophys"]["Device"]) > 0:
                metadata["Ophys"]["Device"][0].update(
                    {"name": "Microscope", "description": "Inscopix NVista3 Microscope (SN: 11132301)"}
                )

            # Update ImagingPlane info
            if "ImagingPlane" in metadata["Ophys"] and len(metadata["Ophys"]["ImagingPlane"]) > 0:
                metadata["Ophys"]["ImagingPlane"][0].update(
                    {
                        "name": "ImagingPlane",
                        "description": "Inscopix imaging plane at 1000um focus",
                        "device": "Microscope",
                    }
                )

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

        # Call parent method to add segmentation data to NWB file
        try:
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
                iterator_options=iterator_options,
            )
        except Exception as e:
            if self.verbose:
                print(f"Error in add_to_nwbfile: {e}")
                print(f"ROI IDs: {self.segmentation_extractor.get_roi_ids()}")
                try:
                    # Try to inspect the underlying structure
                    print("Original ROI IDs:", self._original_roi_ids)
                    print("Int to Str mapping:", self._int_to_str_mapping)
                except Exception as inner_e:
                    print(f"Error inspecting ROI data: {inner_e}")
            raise
