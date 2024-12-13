from pydantic import DirectoryPath, validate_call

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class TdtRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting Tucker-Davis Technologies (TDT) data."""

    display_name = "TDT Recording"
    associated_suffixes = (".tbk", ".tbx", ".tev", ".tsq")
    info = "Interface for TDT recording data."

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:

        extractor_kwargs = source_data.copy()
        extractor_kwargs.pop("gain")

        return extractor_kwargs

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        gain: float,
        stream_id: str = "0",
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ):
        """
        Initialize reading of a TDT recording.

        Parameters
        ----------
        folder_path : str or Path
            Path to the directory with the corresponding files (TSQ, TBK, TEV, SEV)
        stream_id : str, "0" by default
            Select from multiple streams.
        gain : float
            The conversion factor from int16 to microvolts.
        verbose : bool, default: Falsee
            Allows verbose.
        es_key : str, optional


        Notes
        -----
        Stream "0" corresponds to LFP for gin data. Other streams seem non-electrical.
        """
        super().__init__(
            folder_path=folder_path,
            stream_id=stream_id,
            verbose=verbose,
            es_key=es_key,
            gain=gain,
        )

        # Fix channel name format
        channel_names = self.recording_extractor.get_property("channel_name")
        channel_names = [name.replace("'", "")[1:] for name in channel_names]
        self.recording_extractor.set_property(key="channel_name", values=channel_names)

        self.recording_extractor.set_channel_gains(gain)
