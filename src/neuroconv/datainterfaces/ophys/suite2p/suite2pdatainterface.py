from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....tools.ophys_metadata_conversion import (
    is_old_ophys_metadata_format,
    update_old_ophys_metadata_format_to_new,
)
from ....utils import DeepDict


class Suite2pSegmentationInterface(BaseSegmentationExtractorInterface):
    """Interface for Suite2p segmentation data."""

    display_name = "Suite2p Segmentation"
    associated_suffixes = (".npy",)
    info = "Interface for Suite2p segmentation."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the Suite2p segmentation interface.

        Returns
        -------
        dict
            The schema dictionary containing input parameters and descriptions
            for initializing the Suite2p segmentation interface.
        """
        schema = super().get_source_schema()
        schema["properties"]["folder_path"][
            "description"
        ] = "Path to the folder containing Suite2p segmentation data. Should contain 'plane#' subfolder(s)."
        schema["properties"]["plane_name"][
            "description"
        ] = "The name of the plane to load. This interface only loads one plane at a time. Use the full name, e.g. 'plane0'. If this value is omitted, the first plane found will be loaded."

        return schema

    @classmethod
    def get_available_planes(cls, folder_path: DirectoryPath) -> dict:
        """
        Get the available planes in the Suite2p segmentation folder.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing Suite2p segmentation data.

        Returns
        -------
        dict
            Dictionary containing information about available planes in the dataset.
        """
        from roiextractors import Suite2pSegmentationExtractor

        return Suite2pSegmentationExtractor.get_available_planes(folder_path=folder_path)

    @classmethod
    def get_available_channels(cls, folder_path: DirectoryPath) -> dict:
        """
        Get the available channels in the Suite2p segmentation folder.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing Suite2p segmentation data.

        Returns
        -------
        dict
            Dictionary containing information about available channels in the dataset.
        """
        from roiextractors import Suite2pSegmentationExtractor

        return Suite2pSegmentationExtractor.get_available_channels(folder_path=folder_path)

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        channel_name: str | None = None,
        plane_name: str | None = None,
        plane_segmentation_name: str | None = None,
        verbose: bool = False,
        metadata_key: str = "default",
    ):
        """

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing Suite2p segmentation data. Should contain 'plane#' sub-folders.
        channel_name: str, optional
            The name of the channel to load.
            To determine what channels are available, use ``Suite2pSegmentationInterface.get_available_channels(folder_path)``.
        plane_name: str, optional
            The name of the plane to load. This interface only loads one plane at a time.
            If this value is omitted, the first plane found will be loaded.
            To determine what planes are available, use ``Suite2pSegmentationInterface.get_available_planes(folder_path)``.
        plane_segmentation_name: str, optional
            The name of the plane segmentation to be added.
        metadata_key : str, optional
            The key to use for organizing metadata in the new dictionary structure.
            This single key will be used for ImageSegmentation.
            Default is "default".
        """

        super().__init__(
            folder_path=folder_path, channel_name=channel_name, plane_name=plane_name, metadata_key=metadata_key
        )
        available_planes = self.get_available_planes(folder_path=self.source_data["folder_path"])
        available_channels = self.get_available_channels(folder_path=self.source_data["folder_path"])

        if plane_segmentation_name is None:
            plane_segmentation_name = (
                "PlaneSegmentation"
                if len(available_planes) == 1 and len(available_channels) == 1
                else f"PlaneSegmentation{self.segmentation_extractor.channel_name.capitalize()}{self.segmentation_extractor.plane_name.capitalize()}"
            )

        self.plane_segmentation_name = plane_segmentation_name
        self.verbose = verbose

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the Suite2p segmentation data.

        Returns
        -------
        DeepDict
            Dictionary containing metadata including plane segmentation details,
            fluorescence data, and segmentation images.
        """
        metadata = super().get_metadata()

        # Handle backward compatibility
        if is_old_ophys_metadata_format(metadata):
            metadata = update_old_ophys_metadata_format_to_new(metadata)

        # Update component names to match the plane segmentation name pattern
        plane_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"][self.metadata_key]
        default_plane_segmentation_name = plane_segmentation_metadata["name"]

        # If plane segmentation name is custom, update all related component names
        if self.plane_segmentation_name != default_plane_segmentation_name:
            # Extract suffix from plane segmentation name
            plane_suffix = self.plane_segmentation_name.replace("PlaneSegmentation", "")

            # Update PlaneSegmentation name
            plane_segmentation_metadata["name"] = self.plane_segmentation_name

            # Update ImagingPlane name
            imaging_plane_key = plane_segmentation_metadata["imaging_plane_metadata_key"]
            metadata["Ophys"]["ImagingPlanes"][imaging_plane_key]["name"] = f"ImagingPlane{plane_suffix}"

            # Update SegmentationImages names
            segmentation_images = metadata["Ophys"]["SegmentationImages"][self.metadata_key]
            segmentation_images["correlation"]["name"] = f"CorrelationImage{plane_suffix}"
            segmentation_images["mean"]["name"] = f"MeanImage{plane_suffix}"

            # Update Fluorescence trace names
            fluorescence_metadata = metadata["Ophys"]["Fluorescence"][self.metadata_key]
            for trace_name in fluorescence_metadata:
                if trace_name != "name" and isinstance(fluorescence_metadata[trace_name], dict):
                    if "name" in fluorescence_metadata[trace_name]:
                        # Apply new suffix to trace name
                        if trace_name == "raw":
                            base_name = "RoiResponseSeries"
                        elif trace_name == "neuropil":
                            base_name = "Neuropil"
                        elif trace_name == "deconvolved":
                            base_name = "Deconvolved"
                        else:
                            base_name = trace_name.capitalize()
                        fluorescence_metadata[trace_name]["name"] = f"{base_name}{plane_suffix}"

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        stub_test: bool = False,
        stub_frames: int = 100,
        include_roi_centroids: bool = True,
        include_roi_acceptance: bool = True,
        mask_type: str | None = "image",  # Literal["image", "pixel", "voxel"]
        plane_segmentation_name: str | None = None,
        iterator_options: dict | None = None,
    ):
        """
        Add segmentation data to the specified NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile object to which the segmentation data will be added.
        metadata : dict, optional
            Metadata containing information about the segmentation. If None, default metadata is used.
        stub_test : bool, optional
            If True, only a subset of the data (defined by `stub_frames`) will be added for testing purposes,
            by default False.
        stub_frames : int, optional
            The number of frames to include in the subset if `stub_test` is True, by default 100.
        include_roi_centroids : bool, optional
            Whether to include the centroids of regions of interest (ROIs) in the data, by default True.
        include_roi_acceptance : bool, optional
            Whether to include acceptance status of ROIs, by default True.
        mask_type : str, default: 'image'
            There are three types of ROI masks in NWB, 'image', 'pixel', and 'voxel'.

            * 'image' masks have the same shape as the reference images the segmentation was applied to, and weight each pixel
            by its contribution to the ROI (typically boolean, with 0 meaning 'not in the ROI').
            * 'pixel' masks are instead indexed by ROI, with the data at each index being the shape of the image by the number
            of pixels in each ROI.
            * 'voxel' masks are instead indexed by ROI, with the data at each index being the shape of the volume by the number
            of voxels in each ROI.

            Specify your choice between these two as mask_type='image', 'pixel', 'voxel', or None.
            plane_segmentation_name : str, optional
            The name of the plane segmentation object, by default None.
        iterator_options : dict, optional
            Additional options for iterating over the data, by default None.
        """
        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            stub_frames=stub_frames,
            include_roi_centroids=include_roi_centroids,
            include_roi_acceptance=include_roi_acceptance,
            mask_type=mask_type,
            plane_segmentation_name=self.plane_segmentation_name,
            iterator_options=iterator_options,
        )
