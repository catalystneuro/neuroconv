import warnings
from typing import Any

from pydantic import validate_call

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class TdtRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting Tucker-Davis Technologies (TDT) data."""

    display_name = "TDT Recording"
    associated_suffixes = (".tbk", ".tbx", ".tev", ".tsq")
    info = "Interface for TDT recording data."

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import TdtRecordingExtractor

        return TdtRecordingExtractor

    def _initialize_extractor(self, interface_kwargs: dict):
        """Override to pop gain parameter."""
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("es_key", None)
        self.extractor_kwargs.pop("gain")

        return self.get_extractor_class()(**self.extractor_kwargs)

    @validate_call
    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
        # folder_path: DirectoryPath,
        # gain: float,
        # stream_id: str = "0",
        # verbose: bool = False,
        # es_key: str = "ElectricalSeries",
        # stream_name: str | None = None,
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
        verbose : bool, default: False
            Allows verbose.
        es_key : str, optional
        stream_name : str or None, optional
            Name of the stream to select. If None, stream_id is used.


        Notes
        -----
        Stream "0" corresponds to LFP for gin data. Other streams seem non-electrical.
        Either stream_id or stream_name can be used to select the desired stream, but not both.
        """
        parameter_names = [
            "folder_path",
            "gain",
            "stream_id",
            "verbose",
            "es_key",
            "stream_name",
        ]
        if args:
            warnings.warn(
                "Passing arguments positionally is deprecated and will be removed in June 2026. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"add_to_nwbfile() takes {len(parameter_names)} positional arguments but "
                    f"{len(args)} were given."
                )
            # Bind positional args to their parameter names
            for i, value in enumerate(args):
                kwargs[parameter_names[i]] = value

        # Extract the actual parameters
        folder_path = kwargs.get("folder_path", None)
        gain = kwargs.get("gain", None)
        stream_id = kwargs.get("stream_id", "0")
        verbose = kwargs.get("verbose", False)
        es_key = kwargs.get("es_key", "ElectricalSeries")
        stream_name = kwargs.get("stream_name", None)

        if stream_name is not None:
            stream_id = None
        super().__init__(
            folder_path=folder_path,
            stream_id=stream_id,
            stream_name=stream_name,
            verbose=verbose,
            es_key=es_key,
            gain=gain,
        )

        # Fix channel name format
        channel_names = self.recording_extractor.get_property("channel_name")
        channel_names = [name.replace("'", "")[1:] for name in channel_names]
        self.recording_extractor.set_property(key="channel_name", values=channel_names)

        self.recording_extractor.set_channel_gains(gain)
