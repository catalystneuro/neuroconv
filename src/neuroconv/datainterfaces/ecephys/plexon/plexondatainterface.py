"""Authors: Cody Baker."""
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface

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
        verbose: bool, default: True
            Allows verbosity.
        """
        super().__init__(file_path=file_path, verbose=verbose)


class PlexonSortingInterface(BaseSortingExtractorInterface):
    """
    Primary data interface class for converting Plexon spiking data.

    Uses :py:class:`~spikeinterface.extractors.PlexonSortingExtractor`.
    """

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """
        Load and prepare data for Plexon.

        Parameters
        ----------
        file_path: FilePathType
            Path to the plexon spiking data (.plx file).
        verbose: bool, default: True
            Allows verbosity.
        """
        super().__init__(file_path=file_path, verbose=verbose)
