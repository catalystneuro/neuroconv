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

    def _initialize_extractor(self, source_data):
        """Override to patch get_frame_shape before extractor instantiation.

        Temporary patch for roiextractors bug where get_frame_shape() accesses _image_masks before it's set.
        Only applies to LegacyExtractSegmentationExtractor.
        TODO: Remove this once roiextractors is fixed.
        """
        import h5py
        from roiextractors.extractors.schnitzerextractor.extractsegmentationextractor import (
            LegacyExtractSegmentationExtractor,
        )

        # Check if this is a Legacy format file by checking for 'extractAnalysisOutput'
        file_path = source_data["file_path"]
        output_struct_name = source_data.get("output_struct_name") or "extractAnalysisOutput"

        with h5py.File(file_path, "r") as f:
            # Only patch if this is Legacy format (has extractAnalysisOutput or custom output_struct_name)
            if output_struct_name in f:
                # Shape after transpose [1, 2, 0] is (H, W, N), so we need [1:3] for (H, W)
                frame_shape = f[output_struct_name]["filters"].shape[1:3]
                # Patch get_frame_shape to return the shape we just read
                LegacyExtractSegmentationExtractor.get_frame_shape = lambda _: frame_shape

        return super()._initialize_extractor(source_data)

    def __init__(
        self,
        file_path: FilePath,
        sampling_frequency: float,
        output_struct_name: str | None = None,
        verbose: bool = False,
    ):
        """

        Parameters
        ----------
        file_path : FilePath
        sampling_frequency : float
        output_struct_name : str, optional
        verbose: bool, default : True
        """
        self.verbose = verbose
        super().__init__(
            file_path=file_path,
            sampling_frequency=sampling_frequency,
            output_struct_name=output_struct_name,
        )
