from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class MCSRawRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting MCSRaw data.

    Uses the :py:func:`~spikeinterface.extractors.read_mcsraw` reader from SpikeInterface.
    """

    display_name = "MCSRaw Recording"
    associated_suffixes = (".raw",)
    info = "Interface for MCSRaw recording data."

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import MCSRawRecordingExtractor

        return MCSRawRecordingExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .raw file."
        return source_schema

    def __init__(
        self,
        file_path: FilePath,
        *,
        verbose: bool = False,
        es_key: str | None = None,
        metadata_key: str | None = None,
        channels_to_exclude: list | None = None,
    ):
        """
        Load and prepare data for MCSRaw.

        Parameters
        ----------
        file_path: string or Path
            Path to the .raw file.
        verbose: bool, default: True
            Allows verbose.
        es_key: str, default: "ElectricalSeries"
        metadata_key : str, optional
            Key that indexes this interface's entries in the dict-based metadata. Defaults to
            ``"mcs_raw_recording"``.
        channels_to_exclude : list, optional
            Channels to leave out, by the ids in ``channel_ids``. Every other channel is converted. A name that
            is not one of the interface's channels raises.
        """

        if metadata_key is None:
            metadata_key = "mcs_raw_recording"

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key, metadata_key=metadata_key)

        self._exclude_channels(channels_to_exclude)
