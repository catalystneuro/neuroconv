from typing import Optional

from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class WhiteMatterRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface for converting binary WhiteMatter data (.bin files).

    Uses the :py:func:`~spikeinterface.extractors.read_whitematter` reader from SpikeInterface.
    """

    display_name = "WhiteMatter Recording"
    associated_suffixes = (".bin",)
    info = "Interface for converting binary WhiteMatter recording data."

    ExtractorName = "WhiteMatterRecordingExtractor"

    def __init__(
        self,
        file_path: FilePath,
        sampling_frequency: float,
        num_channels: int,
        channel_ids: Optional[list] = None,
        is_filtered: Optional[bool] = None,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ):
        """
        Initialize reading of OpenEphys binary recording.

        Parameters
        ----------
        file_path : Path
            Path to the binary file.
        sampling_frequency : float
            The sampling frequency.
        num_channels : int
            Number of channels in the recording.
        channel_ids : list or None, default: None
            A list of channel ids. If None, channel_ids = list(range(num_channels)).
        is_filtered : bool or None, default: None
            If True, the recording is assumed to be filtered. If None, is_filtered is not set.
        verbose : bool, default: False
            If True, will print out additional information.
        es_key : str, default: "ElectricalSeries"
            The key of this ElectricalSeries in the metadata dictionary.
        """
        super().__init__(
            file_path=file_path,
            sampling_frequency=sampling_frequency,
            num_channels=num_channels,
            channel_ids=channel_ids,
            is_filtered=is_filtered,
            verbose=verbose,
            es_key=es_key,
        )
