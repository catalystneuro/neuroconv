from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ...ecephys.baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import FilePathType


class InscopixSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for InscopixSegmentationExtractor."""

    def __init__(
        self,
        file_path: FilePathType,
        verbose: bool = True,
    ):
        """

        Parameters
        ----------
        file_path : FilePathType
        verbose: bool, default: True
        """
        self.verbose = verbose
        super().__init__(file_path=file_path)


class InscopixRecordingInterface(BaseRecordingExtractorInterface):
    """Data interface for InscopixRecordingExtractor."""

    def __init__(
        self,
        file_path: FilePathType,
        verbose: bool = True,
    ):
        """

        Parameters
        ----------
        file_path : FilePathType
        verbose: bool, default: True
        """
        self.verbose = verbose
        super().__init__(file_path=file_path)