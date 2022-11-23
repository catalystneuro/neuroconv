"""Authors: Cody Baker."""
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface

from ....utils.types import FilePathType


class BiocamRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting Biocam data.

    Using the :py:class:`~spikeinterface.extractors.EDFRecordingExtractor`.
    """

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """
        Load and prepare data for Biocam.

        Parameters
        ----------
        folder_path: string or Path
            Path to the .bwr file.
        verbose: boolean
            Allows verbose.
            Default is True.
        """
        super().__init__(file_path=file_path, verbose=verbose)
