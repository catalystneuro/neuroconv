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

        # Handle string ROI IDs if present
        self._fix_roi_ids()

    def _fix_roi_ids(self):
        """
        Convert string ROI IDs (like 'C0') to integers (like 0) if needed.
        The base segmentation extractor expects integer ROI IDs.
        """
        # Check if ROI IDs are available and if any are strings
        if hasattr(self.segmentation_extractor, "_roi_ids"):
            roi_ids = self.segmentation_extractor._roi_ids
            if any(isinstance(roi_id, str) for roi_id in roi_ids):
                # Convert string ROI IDs to integers
                new_roi_ids = []
                for roi_id in roi_ids:
                    if isinstance(roi_id, str) and roi_id.startswith("C"):
                        new_roi_ids.append(int(roi_id[1:]))  # Remove 'C' prefix and convert to int
                    else:
                        new_roi_ids.append(roi_id)

                # Update the ROI IDs in the extractor
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

        # Get additional metadata from the segmentation extractor
        extractor_meta = self.segmentation_extractor.get_extra_property("metadata")
        if extractor_meta is None:
            return metadata

        # Add subject information
        if "extraProperties" in extractor_meta and "animal" in extractor_meta["extraProperties"]:
            animal_info = extractor_meta["extraProperties"]["animal"]

            if "NWBFile" not in metadata:
                metadata["NWBFile"] = {}

            metadata["NWBFile"]["Subject"] = {
                "subject_id": animal_info.get("id", ""),
                "species": animal_info.get("species", ""),
                "sex": animal_info.get("sex", ""),
                "description": animal_info.get("description", ""),
            }

        # Add microscope information
        if "extraProperties" in extractor_meta and "microscope" in extractor_meta["extraProperties"]:
            microscope_info = extractor_meta["extraProperties"]["microscope"]

            if "Ophys" in metadata and "Device" in metadata["Ophys"] and len(metadata["Ophys"]["Device"]) > 0:
                # Update device description
                device = metadata["Ophys"]["Device"][0]
                device["description"] = (
                    f"Inscopix {microscope_info.get('type', '')} Microscope (SN: {microscope_info.get('serial', '')})"
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
        # Make sure ROI IDs are fixed before adding to NWB file
        self._fix_roi_ids()

        # Call parent method to add segmentation data to NWB file
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
