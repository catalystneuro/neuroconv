from pydantic import FilePath, validate_call

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class SimaSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for SimaSegmentationExtractor."""

    display_name = "SIMA Segmentation"
    associated_suffixes = (".sima",)
    info = "Interface for SIMA segmentation."

    @validate_call
    def __init__(self, file_path: FilePath, sima_segmentation_label: str = "auto_ROIs", metadata_key: str = "default"):
        """

        Parameters
        ----------
        file_path : FilePath
            Path to .sima file containing segmentation data.
        sima_segmentation_label : str, default: "auto_ROIs"
            The label for the segmentation data within the SIMA file.
        metadata_key : str, optional
            The key to use for organizing metadata in the new dictionary structure.
            This single key will be used for ImageSegmentation.
            Default is "default".
        """
        super().__init__(
            file_path=file_path, sima_segmentation_label=sima_segmentation_label, metadata_key=metadata_key
        )
