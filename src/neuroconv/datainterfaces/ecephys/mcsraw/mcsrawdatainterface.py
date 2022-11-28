"""Authors: Cody Baker."""
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface

from ....utils.types import FilePathType


class MCSRawRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting MCSRaw data.

    Using the :py:class:`~spikeinterface.extractors.MCSRawRecordingExtractor`.
    """

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """
        Load and prepare data for MCSRaw.

        Parameters
        ----------
        folder_path: string or Path
            Path to the .raw file.
        verbose: boolean
            Allows verbose.
            Default is True.
        """
        super().__init__(file_path=file_path, verbose=verbose)
