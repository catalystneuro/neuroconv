import warnings
from typing import Any

from pydantic import DirectoryPath, validate_call

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
        *args: Any,  # TODO: change to * (keyword only) on or after August 2026
        folder_path: DirectoryPath,
        gain: float,
        stream_id: str = "0",  # Stream "0" corresponds to LFP for gin data. Other streams seem non-electrical.
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
        stream_name: str | None = None,
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
        Either stream_id or stream_name can be used to select the desired stream.
        If neither are specified, this interface defaults to the first stream, with stream_id "0".
        If both are specified, stream_name takes precedence.
        """
        if args:
            parameter_names = [
                "folder_path",
                "gain",
                "stream_id",
                "verbose",
                "es_key",
                "stream_name",
            ]
            num_positional_args_before_args = 0
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"add_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                    f"{len(args) + num_positional_args_before_args} were given. "
                    "Note: Positional arguments are deprecated and will be removed in June 2026. Please use keyword arguments."
                )
            # Map positional args to keyword args, positional args take precedence
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally is deprecated and will be removed in June 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            folder_path = positional_values.get("folder_path", folder_path)
            gain = positional_values.get("gain", gain)
            stream_id = positional_values.get("stream_id", stream_id)
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)
            stream_name = positional_values.get("stream_name", stream_name)

        # Deprecate stream_id parameter
        # TODO: Remove after June 2026 - Only external videos will be supported
        if stream_id is not None:
            warnings.warn(
                "The 'stream_id' parameter is deprecated and will be removed in June 2026. "
                "Use 'stream_name' parameter instead to select the desired stream.",
                FutureWarning,
                stacklevel=2,
            )

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
