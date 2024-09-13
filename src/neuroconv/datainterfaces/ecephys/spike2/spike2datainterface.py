from pathlib import Path

from pydantic import FilePath, validate_call

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....tools import get_package
from ....utils import get_schema_from_method_signature


def _test_sonpy_installation() -> None:
    get_package(
        package_name="sonpy",
        excluded_python_versions=["3.10", "3.11"],
        excluded_platforms_and_python_versions=dict(darwin=dict(arm=["3.9", "3.10", "3.11", "3.12"])),
    )


class Spike2RecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface class for converting Spike2 data from CED (Cambridge Electronic
    Design) using the :py:class:`~spikeinterface.extractors.CedRecordingExtractor`."""

    display_name = "Spike2 Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("CED",)
    associated_suffixes = (".smrx",)
    info = "Interface for Spike2 recording data from CED (Cambridge Electronic Design)."

    ExtractorName = "CedRecordingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_schema_from_method_signature(method=cls.__init__, exclude=["smrx_channel_ids"])
        source_schema.update(additionalProperties=True)
        source_schema["properties"]["file_path"].update(description="Path to .smrx file.")
        return source_schema

    @classmethod
    def get_all_channels_info(cls, file_path: FilePath):
        """Retrieve and inspect necessary channel information prior to initialization."""
        _test_sonpy_installation()
        return cls.get_extractor().get_all_channels_info(file_path=file_path)

    @validate_call
    def __init__(self, file_path: FilePath, verbose: bool = True, es_key: str = "ElectricalSeries"):
        """
        Initialize reading of Spike2 file.

        Parameters
        ----------
        file_path : FilePathType
            Path to .smr or .smrx file.
        verbose : bool, default: True
        es_key : str, default: "ElectricalSeries"
        """
        _test_sonpy_installation()

        stream_id = "1" if Path(file_path).suffix == ".smr" else None
        super().__init__(file_path=file_path, stream_id=stream_id, verbose=verbose, es_key=es_key)

        # Subset raw channel properties
        signal_channels = self.recording_extractor.neo_reader.header["signal_channels"]
        channel_ids_of_raw_data = [channel_info[1] for channel_info in signal_channels if channel_info[4] == "mV"]
        self.recording_extractor = self.recording_extractor.channel_slice(channel_ids=channel_ids_of_raw_data)
