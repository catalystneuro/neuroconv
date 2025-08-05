from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class ExtractSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for ExtractSegmentationExtractor."""

    display_name = "EXTRACT Segmentation"
    associated_suffixes = (".mat",)
    info = "Interface for EXTRACT segmentation."

    def __init__(
        self,
        file_path: FilePath,
        sampling_frequency: float,
        output_struct_name: str | None = None,
        verbose: bool = False,
        metadata_key: str = "default",
    ):
        """

        Parameters
        ----------
        file_path : FilePath
            Path to .mat file containing EXTRACT segmentation data.
        sampling_frequency : float
            The sampling frequency of the imaging data.
        output_struct_name : str, optional
            The name of the output structure in the .mat file.
        verbose: bool, default : True
            Whether to print progress.
        metadata_key : str, optional
            The key to use for organizing metadata in the new dictionary structure.
            This single key will be used for ImageSegmentation.
            Default is "default".
        """
        self.verbose = verbose
        super().__init__(
            file_path=file_path,
            sampling_frequency=sampling_frequency,
            output_struct_name=output_struct_name,
            metadata_key=metadata_key,
        )
