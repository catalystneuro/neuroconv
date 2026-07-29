import warnings

from pydantic import ConfigDict, FilePath, validate_call

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import ArrayType, get_json_schema_from_method_signature


class SpikeGadgetsRecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface class for converting data in the SpikeGadgets format.

    Uses the :py:func:`~spikeinterface.extractors.read_spikegadgets` reader from SpikeInterface.
    """

    display_name = "SpikeGadgets Recording"
    associated_suffixes = (".rec",)
    info = "Interface for SpikeGadgets recording data."

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import (
            SpikeGadgetsRecordingExtractor,
        )

        return SpikeGadgetsRecordingExtractor

    def _initialize_extractor(self, interface_kwargs: dict):
        """Override to pop gains parameter."""
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("es_key", None)
        self.extractor_kwargs.pop("gains", None)

        return self.get_extractor_class()(**self.extractor_kwargs)

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(cls, exclude=["source_data"])
        source_schema["properties"]["file_path"].update(description="Path to SpikeGadgets (.rec) file.")
        return source_schema

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        stream_id: str = "trodes",
        gains: ArrayType | None = None,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ):
        """
        Recording Interface for the SpikeGadgets Format.

        Parameters
        ----------
        file_path : FilePath
            Path to the .rec file.
        gains : array_like, optional
            The early versions of SpikeGadgets do not automatically record the conversion factor ('gain') of the
            acquisition system. Thus, it must be specified either as a single value (if all channels have the same gain)
            or an array of values for each channel.
        es_key : str, default: "ElectricalSeries"
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "stream_id",
                "gains",
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
                f"Passing arguments positionally to SpikeGadgetsRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            stream_id = positional_values.get("stream_id", stream_id)
            gains = positional_values.get("gains", gains)
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)

        super().__init__(file_path=file_path, stream_id=stream_id, verbose=verbose, es_key=es_key)

        if gains is not None:
            if len(gains) == 1:
                gains = [gains[0]] * self.recording_extractor.get_num_channels()
            self.recording_extractor.set_channel_gains(gains=gains)
