from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class CaimanSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for CaimanSegmentationExtractor."""

    display_name = "CaImAn Segmentation"
    associated_suffixes = (".hdf5",)
    info = "Interface for CaImAn segmentation data."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the CaImAn segmentation interface.

        Returns
        -------
        dict
            The schema dictionary containing input parameters and descriptions
            for initializing the CaImAn segmentation interface.
        """
        source_metadata = super().get_source_schema()
        source_metadata["properties"]["file_path"]["description"] = "Path to .hdf5 file."
        return source_metadata

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import CaimanSegmentationExtractor

        return CaimanSegmentationExtractor

    def __init__(
        self, file_path: FilePath, *, verbose: bool = False, metadata_key: str | None = None
    ):  # TODO: change to * (keyword only) on or after August 2026
        """
        Parameters
        ----------
        file_path : FilePath
            Path to .hdf5 file.
        verbose : bool, default False
            Whether to print progress
        metadata_key : str, optional
            Metadata key for this interface. When None, defaults to "caiman_segmentation".
        """

        if metadata_key is None:
            metadata_key = "caiman_segmentation"

        super().__init__(file_path=file_path, metadata_key=metadata_key)
        self.verbose = verbose

    def get_metadata(self, *, use_new_metadata_format: bool = True):
        if use_new_metadata_format:
            metadata = super().get_metadata(use_new_metadata_format=True)
            metadata["Ophys"] = {
                "PlaneSegmentations": {
                    self.metadata_key: {"description": "Segmentation data acquired with CaImAn."},
                },
            }
            return metadata

        return super().get_metadata(use_new_metadata_format=False)
