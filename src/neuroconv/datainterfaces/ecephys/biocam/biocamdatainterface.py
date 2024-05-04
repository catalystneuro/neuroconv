from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils.types import FilePathType


class BiocamRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting Biocam data.

    Using the :py:class:`~spikeinterface.extractors.BiocamRecordingExtractor`.
    """

    display_name = "Biocam Recording"
    associated_suffixes = (".bwr",)
    info = "Interface for Biocam recording data."

    def __init__(self, file_path: FilePathType, verbose: bool = True, es_key: str = "ElectricalSeries"):
        """
        Load and prepare data for Biocam.

        Parameters
        ----------
        file_path : string or Path
            Path to the .bwr file.
        verbose : bool, default: True
            Allows verbose.
        es_key: str, default: "ElectricalSeries"
        """
        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)
