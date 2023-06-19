from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils.types import FilePathType


class MCSRawRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting MCSRaw data.

    Using the :py:class:`~spikeinterface.extractors.MCSRawRecordingExtractor`.
    """

    def __init__(self, file_path: FilePathType, verbose: bool = True, es_key: str = "ElectricalSeries"):
        """
        Load and prepare data for MCSRaw.

        Parameters
        ----------
        file_path: string or Path
            Path to the .raw file.
        verbose: bool, default: True
            Allows verbose.
        es_key: str, default: "ElectricalSeries"
        """
        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)
