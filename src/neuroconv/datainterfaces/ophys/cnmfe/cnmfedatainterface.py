from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class CnmfeSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for constrained non-negative matrix factorization (CNMFE) segmentation extractor."""

    display_name = "CNMFE Segmentation"
    associated_suffixes = (".mat",)
    info = "Interface for constrained non-negative matrix factorization (CNMFE) segmentation."

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import CnmfeSegmentationExtractor

        return CnmfeSegmentationExtractor

    def __init__(
        self, file_path: FilePath, *, verbose: bool = False, metadata_key: str | None = None
    ):  # TODO: change to * (keyword only) on or after August 2026

        if metadata_key is None:
            metadata_key = "cnmfe_segmentation"

        super().__init__(file_path=file_path, metadata_key=metadata_key)
        self.verbose = verbose

    def get_metadata(self, *, use_new_metadata_format: bool = True):
        if use_new_metadata_format:
            metadata = super().get_metadata(use_new_metadata_format=True)
            metadata["Ophys"] = {
                "PlaneSegmentations": {
                    self.metadata_key: {"description": "Segmentation data acquired with CNMF-E."},
                },
            }
            return metadata

        return super().get_metadata(use_new_metadata_format=False)
