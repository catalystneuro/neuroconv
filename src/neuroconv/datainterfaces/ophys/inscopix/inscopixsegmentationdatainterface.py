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

        # Add a custom adapter to access columns directly
        self._add_custom_plane_segmentation_adapter()

    def _add_custom_plane_segmentation_adapter(self):
        """Add a custom adapter to ensure consistent column lengths in NWB tables."""
        from neuroconv.tools.roiextractors import roiextractors

        # Store the original add_plane_segmentation function
        original_add_plane_segmentation = roiextractors.add_plane_segmentation
        interface_self = self  # For use in the wrapped function

        # Define a wrapper function with the same signature
        def wrapped_add_plane_segmentation(
            segmentation_extractor,
            nwbfile,
            imaging_plane,
            name=None,
            image_series=None,
            id=None,
            columns=None,
            description=None,
            roi_response_series=None,
            reference_images=None,
            times=None,
        ):
            """Ensure consistent column lengths when adding plane segmentation."""
            if interface_self.verbose:
                print(f"Called wrapped_add_plane_segmentation with {len(segmentation_extractor.get_roi_ids())} ROIs")

            # Get the ROI IDs to ensure consistent lengths
            roi_ids = segmentation_extractor.get_roi_ids()
            roi_count = len(roi_ids)

            # For image masks, ensure we have one per ROI
            if columns is None:
                columns = {}

            # Override key columns to ensure consistent lengths
            if "image_mask" in columns:
                image_masks = columns["image_mask"]
                if len(image_masks) != roi_count:
                    if interface_self.verbose:
                        print(f"Fixing image_mask length: {len(image_masks)} -> {roi_count}")

                    # Reshape to ensure we have exactly one mask per ROI
                    if len(image_masks) > 0:
                        # Get the shape of a single mask
                        mask_shape = image_masks[0].shape

                        # Create a new array with the correct number of masks
                        if len(image_masks) > roi_count:
                            # Truncate if too many
                            new_masks = image_masks[:roi_count]
                        else:
                            # Pad with zeros if too few
                            new_masks = np.zeros((roi_count,) + mask_shape, dtype=image_masks.dtype)
                            new_masks[: len(image_masks)] = image_masks

                        columns["image_mask"] = new_masks

            # Fix pixel_mask if present
            if "pixel_mask" in columns:
                pixel_masks = columns["pixel_mask"]
                if len(pixel_masks) != roi_count:
                    if interface_self.verbose:
                        print(f"Fixing pixel_mask length: {len(pixel_masks)} -> {roi_count}")

                    # Create an empty array of the correct length
                    new_masks = [np.zeros((0, 3)) for _ in range(roi_count)]

                    # Copy over available masks
                    for i in range(min(len(pixel_masks), roi_count)):
                        new_masks[i] = pixel_masks[i]

                    columns["pixel_mask"] = new_masks

            # Fix voxel_mask if present
            if "voxel_mask" in columns:
                voxel_masks = columns["voxel_mask"]
                if len(voxel_masks) != roi_count:
                    if interface_self.verbose:
                        print(f"Fixing voxel_mask length: {len(voxel_masks)} -> {roi_count}")

                    # Create an empty array of the correct length
                    new_masks = [np.zeros((0, 4)) for _ in range(roi_count)]

                    # Copy over available masks
                    for i in range(min(len(voxel_masks), roi_count)):
                        new_masks[i] = voxel_masks[i]

                    columns["voxel_mask"] = new_masks

            # Finally, call the original function with the fixed columns
            if interface_self.verbose:
                print(f"Calling original add_plane_segmentation with {roi_count} ROIs")

            return original_add_plane_segmentation(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile,
                imaging_plane=imaging_plane,
                name=name,
                image_series=image_series,
                id=id,
                columns=columns,
                description=description,
                roi_response_series=roi_response_series,
                reference_images=reference_images,
                times=times,
            )

        # Monkey patch the add_plane_segmentation function in roiextractors
        roiextractors.add_plane_segmentation = wrapped_add_plane_segmentation

    def add_to_nwbfile(self, nwbfile, metadata=None, **kwargs):
        """Add segmentation data to an NWBFile.

        Override to handle the Inscopix-specific issues.

        Parameters
        ----------
        See BaseSegmentationExtractorInterface.add_to_nwbfile for parameter details.
        """
        if self.verbose:
            print("Calling custom add_to_nwbfile method")

        # Call the parent method with the patched extractor
        try:
            super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **kwargs)
            if self.verbose:
                print("Successfully added segmentation to NWBFile")
        except Exception as e:
            if self.verbose:
                print(f"Error adding segmentation to NWBFile: {type(e).__name__}: {str(e)}")
            raise
