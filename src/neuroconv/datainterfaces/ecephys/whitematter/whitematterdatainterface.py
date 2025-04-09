from typing import Optional

from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class WhiteMatterRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface for converting binary WhiteMatter data (.bin files).

    Uses :py:class:`~spikeinterface.extractors.WhiteMatterRecordingExtractor`.
    """

    display_name = "WhiteMatter Recording"
    associated_suffixes = (".bin",)
    info = "Interface for converting binary WhiteMatter recording data."

    ExtractorName = "WhiteMatterRecordingExtractor"

    def __init__(
        self,
        file_paths: list[FilePath],
        sampling_frequency: float,
        num_channels: int,
        channel_ids: Optional[list] = None,
        time_axis: int = 0,
        is_filtered: Optional[bool] = None,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ):
        """
        Initialize reading of OpenEphys binary recording.

        Parameters
        ----------
        file_paths : list or Path
            List of paths to the binary files.
        sampling_frequency : float
            The sampling frequency.
        num_channels : int
            Number of channels in the recording.
        channel_ids : list or None, default: None
            A list of channel ids. If None, channel_ids = list(range(num_channels)).
        time_axis : int, default: 0
            The axis of the time dimension.
        is_filtered : bool or None, default: None
            If True, the recording is assumed to be filtered. If None, is_filtered is not set.
        verbose : bool, default: False
            If True, will print out additional information.
        es_key : str, default: "ElectricalSeries"
            The key of this ElectricalSeries in the metadata dictionary.
        """
        super().__init__(
            file_paths=file_paths,
            sampling_frequency=sampling_frequency,
            num_channels=num_channels,
            channel_ids=channel_ids,
            time_axis=time_axis,
            is_filtered=is_filtered,
            verbose=verbose,
            es_key=es_key,
        )
