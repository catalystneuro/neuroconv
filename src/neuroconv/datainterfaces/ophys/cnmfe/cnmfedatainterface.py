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

    def _initialize_extractor(self, source_data):
        """Override to patch get_frame_shape before extractor instantiation.

        Temporary patch for roiextractors bug where get_frame_shape() accesses _image_masks before it's set.
        TODO: Remove this once roiextractors is fixed.
        """
        import h5py
        from roiextractors.extractors.schnitzerextractor.cnmfesegmentationextractor import (
            CnmfeSegmentationExtractor,
        )

        # Read the shape directly from the file to patch get_frame_shape
        file_path = source_data["file_path"]
        with h5py.File(file_path, "r") as f:
            group0 = [key for key in f.keys() if "#" not in key]
            frame_shape = f[group0[0]]["extractedImages"].shape[1:3]  # (H, W) from transposed data

        # Patch get_frame_shape to return the shape we just read
        CnmfeSegmentationExtractor.get_frame_shape = lambda _: frame_shape

        return super()._initialize_extractor(source_data)

    def __init__(self, file_path: FilePath, verbose: bool = False):
        super().__init__(file_path=file_path)
        self.verbose = verbose
