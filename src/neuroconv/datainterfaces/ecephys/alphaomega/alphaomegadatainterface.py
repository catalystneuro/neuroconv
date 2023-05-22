from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils.types import FolderPathType


class AlphaOmegaRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting AlphaOmega data.

    Uses the :py:class:`~spikeinterface.extractors.AlphaOmegaRecordingExtractor`.
    """

    def __init__(self, folder_path: FolderPathType, verbose: bool = True, es_key: str = "ElectricalSeries"):
        """
        Load and prepare data for AlphaOmega.

        Parameters
        ----------
        folder_path: string or Path
            Path to the folder of .mrx files.
        verbose: boolean
            Allows verbose.
            Default is True.
        es_key: str, default: "ElectricalSeries"
        """
        super().__init__(folder_path=folder_path, stream_id="RAW", verbose=verbose, es_key=es_key)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        annotation = self.recording_extractor.neo_reader.raw_annotations
        metadata["NWBFile"].update(session_start_time=annotation["blocks"][0]["rec_datetime"])
        return metadata
