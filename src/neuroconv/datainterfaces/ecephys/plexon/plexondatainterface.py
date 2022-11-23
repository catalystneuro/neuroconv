"""Authors: Cody Baker."""
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface

from ....utils.types import FilePathType


class PlexonRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting Plexon data.

    Uses the :py:class:`~spikeinterface.extractors.PlexonRecordingExtractor`.
    """

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """
        Load and prepare data for Plexon.

        Parameters
        ----------
        file_path: string or Path
            Path to the .plx file.
        verbose: boolean
            Allows verbosity.
            Default is True.
        """
        super().__init__(file_path=file_path, verbose=verbose)
