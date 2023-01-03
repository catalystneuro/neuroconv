from typing import Optional

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FilePathType


class ExtractSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for ExtractSegmentationExtractor."""

    def __init__(
        self,
        file_path: FilePathType,
        sampling_frequency: float,
        output_struct_name: Optional[str] = None,
        verbose: bool = True,
    ):
        """

        Parameters
        ----------
        file_path : FilePathType
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
