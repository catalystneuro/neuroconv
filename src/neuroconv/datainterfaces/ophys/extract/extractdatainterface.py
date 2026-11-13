from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class ExtractSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for ExtractSegmentationExtractor."""

    display_name = "EXTRACT Segmentation"
    associated_suffixes = (".mat",)
    info = "Interface for EXTRACT segmentation."

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import ExtractSegmentationExtractor

        return ExtractSegmentationExtractor

    def __init__(
        self,
        file_path: FilePath,
        *,
        sampling_frequency: float,
        output_struct_name: str | None = None,
        verbose: bool = False,
        metadata_key: str | None = None,
    ):
        """

        Parameters
        ----------
        file_path : FilePath
        sampling_frequency : float
        output_struct_name : str, optional
        verbose: bool, default : True
        metadata_key : str, optional
            Metadata key for this interface. When None, defaults to "extract_segmentation".
        """

        if metadata_key is None:
            metadata_key = "extract_segmentation"

        self.verbose = verbose
        super().__init__(
            file_path=file_path,
            sampling_frequency=sampling_frequency,
            output_struct_name=output_struct_name,
            metadata_key=metadata_key,
        )

    def get_metadata(self, *, use_new_metadata_format: bool = True):
        if use_new_metadata_format:
            metadata = super().get_metadata(use_new_metadata_format=True)
            metadata["Ophys"] = {
                "PlaneSegmentations": {
                    self.metadata_key: {"description": "Segmentation data acquired with EXTRACT."},
                },
            }
            return metadata

        return super().get_metadata(use_new_metadata_format=False)
