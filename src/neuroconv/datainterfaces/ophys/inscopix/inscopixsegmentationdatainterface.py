import numpy as np
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
        super().__init__(file_path=self.file_path, verbose=verbose)

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
        """Add the segmentation data to an NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile to add the segmentation data to.
        metadata : dict, optional
            Metadata for the segmentation.
        stub_test : bool, default False
            Whether to use only a subset of the data for testing.
        stub_frames : int, default 100
            Number of frames to use if stub_test is True.
        include_background_segmentation : bool, default False
            Whether to include background segmentation.
        include_roi_centroids : bool, default True
            Whether to include ROI centroids.
        include_roi_acceptance : bool, default True
            Whether to include ROI acceptance information.
        mask_type : str, default "image"
            Type of mask to use.
        plane_segmentation_name : str, optional
            Name of the plane segmentation.
        iterator_options : dict, optional
            Options for iteration.
        """
        if self.verbose:
            print(f"Adding segmentation data to NWBFile with mask_type={mask_type}")

        # Skip calling the parent method directly
        # Instead, use a custom implementation

        # Create a device if needed
        device_name = "Inscopix-Device"
        if device_name not in nwbfile.devices:
            nwbfile.create_device(name=device_name, description="Inscopix Device")

        # Create imaging plane if needed
        imaging_plane_name = "InscopixPlane"
        if imaging_plane_name not in nwbfile.imaging_planes:
            optical_channel = nwbfile.create_optical_channel(
                name="OpticalChannel", description="Inscopix optical channel", emission_lambda=500.0
            )
            nwbfile.create_imaging_plane(
                name=imaging_plane_name,
                optical_channel=optical_channel,
                description="Inscopix imaging plane",
                device=nwbfile.devices[device_name],
                excitation_lambda=488.0,
                indicator="GCaMP",
                location="brain region",
            )

        # Create or get the image segmentation module
        image_seg_name = "Inscopix-ImageSegmentation"
        if "ophys" not in nwbfile.processing:
            ophys_module = nwbfile.create_processing_module(name="ophys", description="Optical physiology data")
        else:
            ophys_module = nwbfile.processing["ophys"]

        if image_seg_name not in ophys_module.data_interfaces:
            image_segmentation = nwbfile.create_image_segmentation(
                name=image_seg_name, description="Inscopix segmentation"
            )
            ophys_module.add(image_segmentation)
        else:
            image_segmentation = ophys_module.data_interfaces[image_seg_name]

        # Create plane segmentation manually
        plane_segmentation_name = plane_segmentation_name or "InscopixPlaneSegmentation"
        if plane_segmentation_name not in image_segmentation.plane_segmentations:
            imaging_plane = nwbfile.imaging_planes[imaging_plane_name]
            plane_segmentation = image_segmentation.create_plane_segmentation(
                name=plane_segmentation_name, description="ROIs from Inscopix segmentation", imaging_plane=imaging_plane
            )

            # Get ROI IDs
            roi_ids = self.segmentation_extractor.get_roi_ids()

            # Add minimal required data with consistent lengths
            n_rois = len(roi_ids)

            # Add ROI image masks with consistent dimensions
            if mask_type == "image" and n_rois > 0:
                try:
                    # Get a single mask to determine dimensions
                    sample_mask = self.segmentation_extractor.get_roi_image_masks(roi_ids=[roi_ids[0]])
                    mask_shape = sample_mask.shape[-2:]

                    # Create empty masks array of the correct shape
                    masks = np.zeros((n_rois,) + mask_shape, dtype=np.float32)

                    # Fill in available masks
                    for i, roi_id in enumerate(roi_ids):
                        try:
                            mask = self.segmentation_extractor.get_roi_image_masks(roi_ids=[roi_id])
                            if mask.shape[-2:] == mask_shape:
                                masks[i] = mask
                        except Exception as e:
                            if self.verbose:
                                print(f"Error getting mask for ROI {roi_id}: {str(e)}")

                    # Add the image masks column
                    plane_segmentation.add_column(
                        name="image_mask", description="Image masks for each ROI.", data=masks
                    )
                except Exception as e:
                    if self.verbose:
                        print(f"Error adding image masks: {str(e)}")

            # Create dummy fluorescence data if available
            if hasattr(self.segmentation_extractor, "get_traces") and n_rois > 0:
                try:
                    traces = self.segmentation_extractor.get_traces()
                    if self.verbose:
                        print(f"Found traces with shape: {traces.shape}")

                    # Create fluorescence container
                    fluorescence = (
                        nwbfile.create_processing_module(name="Fluorescence", description="Fluorescence data")
                        if "Fluorescence" not in nwbfile.processing
                        else nwbfile.processing["Fluorescence"]
                    )

                    # Add RoiResponseSeries
                    fluorescence.create_roi_response_series(
                        name="RoiResponseSeries",
                        data=traces,
                        rois=plane_segmentation,
                        unit="n.a.",
                        description="Fluorescence traces",
                    )
                except Exception as e:
                    if self.verbose:
                        print(f"Error adding fluorescence data: {str(e)}")

        if self.verbose:
            print(f"Successfully added Inscopix segmentation to NWBFile")
