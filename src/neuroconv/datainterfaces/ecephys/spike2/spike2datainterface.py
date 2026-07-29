import warnings
from pathlib import Path

from pydantic import FilePath, validate_call

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....tools import get_package
from ....utils import get_json_schema_from_method_signature


def _test_sonpy_installation() -> None:
    get_package(
        package_name="sonpy",
        excluded_python_versions=["3.10", "3.11"],
        excluded_platforms_and_python_versions=dict(darwin=dict(arm=["3.9", "3.10", "3.11", "3.12"])),
    )


class Spike2RecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface class for converting Spike2 data from CED (Cambridge Electronic
    Design)

    Uses  :py:func:`~spikeinterface.extractors.read_ced` from SpikeInterface.
    """

    display_name = "Spike2 Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("CED",)
    associated_suffixes = (".smrx",)
    info = "Interface for Spike2 recording data from CED (Cambridge Electronic Design)."

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import CedRecordingExtractor

        return CedRecordingExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["smrx_channel_ids"])
        source_schema.update(additionalProperties=True)
        source_schema["properties"]["file_path"].update(description="Path to .smrx file.")
        return source_schema

    @classmethod
    def get_all_channels_info(cls, file_path: FilePath):
        """
        Retrieve and inspect necessary channel information prior to initialization.

        Parameters
        ----------
        file_path : FilePath
            Path to .smr or .smrx file.

        Returns
        -------
        dict
            Dictionary containing information about all channels in the Spike2 file.
        """
        _test_sonpy_installation()
        from spikeinterface.extractors.extractor_classes import CedRecordingExtractor

        return CedRecordingExtractor.get_all_channels_info(file_path=file_path)

    @validate_call
    def __init__(
        self, file_path: FilePath, *args, verbose: bool = False, es_key: str = "ElectricalSeries"
    ):  # TODO: change to * (keyword only) on or after August 2026
        """
        Initialize reading of Spike2 file.

        Parameters
        ----------
        file_path : FilePath
            Path to .smr or .smrx file.
        verbose : bool, default: False
        es_key : str, default: "ElectricalSeries"
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
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
                f"Passing arguments positionally to Spike2RecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)

        _test_sonpy_installation()

        stream_id = "1" if Path(file_path).suffix == ".smr" else None
        super().__init__(file_path=file_path, stream_id=stream_id, verbose=verbose, es_key=es_key)

        # Subset raw channel properties
        signal_channels = self.recording_extractor.neo_reader.header["signal_channels"]
        channel_ids_of_raw_data = [channel_info[1] for channel_info in signal_channels if channel_info[4] == "mV"]
        self.recording_extractor = self.recording_extractor.select_channels(channel_ids=channel_ids_of_raw_data)
