import warnings
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

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import (
            WhiteMatterRecordingExtractor,
        )

        return WhiteMatterRecordingExtractor

    def _initialize_extractor(self, interface_kwargs: dict):
        """Override to pop all_annotations since WhiteMatter extractor doesn't support it."""
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("es_key", None)
        self.extractor_kwargs.pop("all_annotations", None)

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
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
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "sampling_frequency",
                "num_channels",
                "channel_ids",
                "is_filtered",
                "verbose",
                "es_key",
            ]
            num_positional_args_before_args = 1  # file_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to WhiteMatterRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            sampling_frequency = positional_values.get("sampling_frequency", sampling_frequency)
            num_channels = positional_values.get("num_channels", num_channels)
            channel_ids = positional_values.get("channel_ids", channel_ids)
            is_filtered = positional_values.get("is_filtered", is_filtered)
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)

        super().__init__(
            file_path=file_path,
            sampling_frequency=sampling_frequency,
            num_channels=num_channels,
            channel_ids=channel_ids,
            is_filtered=is_filtered,
            verbose=verbose,
            es_key=es_key,
        )
