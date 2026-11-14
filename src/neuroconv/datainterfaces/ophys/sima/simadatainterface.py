from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class SimaSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for SimaSegmentationExtractor."""

    display_name = "SIMA Segmentation"
    associated_suffixes = (".sima",)
    info = "Interface for SIMA segmentation."

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import SimaSegmentationExtractor

        return SimaSegmentationExtractor

    def __init__(
        self,
        file_path: FilePath,
        *,
        sima_segmentation_label: str = "auto_ROIs",
        metadata_key: str | None = None,
    ):
        """

        Parameters
        ----------
        file_path : FilePath
        sima_segmentation_label : str, default: "auto_ROIs"
        metadata_key : str, optional
            Metadata key for this interface. When None, defaults to "sima_segmentation".
        """

        if metadata_key is None:
            metadata_key = "sima_segmentation"

        super().__init__(
            file_path=file_path, sima_segmentation_label=sima_segmentation_label, metadata_key=metadata_key
        )

    def get_metadata(self, *, use_new_metadata_format: bool = True):
        if use_new_metadata_format:
            metadata = super().get_metadata(use_new_metadata_format=True)
            metadata["Ophys"] = {
                "PlaneSegmentations": {
                    self.metadata_key: {"description": "Segmentation data acquired with SIMA."},
                },
            }
            return metadata

        return super().get_metadata(use_new_metadata_format=False)
