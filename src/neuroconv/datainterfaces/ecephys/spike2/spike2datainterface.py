from pathlib import Path
from warnings import warn

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....tools import get_package
from ....utils import FilePathType, get_schema_from_method_signature


def _test_sonpy_installation() -> None:
    get_package(
        package_name="sonpy",
        excluded_python_versions=["3.10", "3.11"],
        excluded_platforms_and_python_versions=dict(darwin=dict(arm=["3.8", "3.9", "3.10", "3.11"])),
    )


class Spike2RecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface class for converting Spike2 data from CED (Cambridge Electronic
    Design) using the :py:class:`~spikeinterface.extractors.CedRecordingExtractor`."""

    keywords = BaseRecordingExtractorInterface.keywords + [
        "CED",
    ]

    ExtractorName = "CedRecordingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_schema_from_method_signature(method=cls.__init__, exclude=["smrx_channel_ids"])
        source_schema.update(additionalProperties=True)
        source_schema["properties"]["file_path"].update(description="Path to CED data file.")
        return source_schema

    @classmethod
    def get_all_channels_info(cls, file_path: FilePathType):
        """Retrieve and inspect necessary channel information prior to initialization."""
        _test_sonpy_installation()
        return cls.get_extractor().get_all_channels_info(file_path=file_path)

    def __init__(self, file_path: FilePathType, verbose: bool = True, es_key: str = "ElectricalSeries"):
        """
        Initialize reading of Spike2 file. CEDRecordingInterface will soon be deprecated. Please use
        Spike2RecordingInterface instead.

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


class CEDRecordingInterface(Spike2RecordingInterface):
    def __init__(self, file_path: FilePathType, verbose: bool = True, es_key: str = "ElectricalSeries"):
        """
        Initialize reading of CED file.

        Parameters
        ----------
        file_path : FilePathType
            Path to .smr or .smrx file.
        verbose : bool, default: True
        es_key : str, default: "ElectricalSeries"
        """
        warn(
            message="CEDRecordingInterface will soon be deprecated. Please use Spike2RecordingInterface instead.",
            category=DeprecationWarning,
        )
        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)
