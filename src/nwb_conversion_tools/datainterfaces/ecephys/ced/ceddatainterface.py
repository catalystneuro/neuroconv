"""Authors: Heberto Mayorquin, Luiz Tauffer."""
from pathlib import Path
from platform import python_version
from sys import platform
from packaging import version

from spikeinterface.extractors import CedRecordingExtractor

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import get_schema_from_method_signature, FilePathType

HAVE_SONPY = True
try:
    import sonpy
except ImportError:
    HAVE_SONPY = False
INSTALL_MESSAGE = "Please install sonpy to use this interface (pip install sonpy)!"
if platform == "darwin" and version.parse(python_version()) < version.parse("3.8"):
    HAVE_SONPY = False
    INSTALL_MESSAGE = "The sonpy package (CED dependency) is not available on Mac for Python versions below 3.8!"


class CEDRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting data from CED (Cambridge Electronic Design)
    ."""

    RX = CedRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(class_method=cls.__init__, exclude=["smrx_channel_ids"])
        source_schema.update(additionalProperties=True)
        source_schema["properties"]["file_path"].update(description="Path to CED data file.")
        return source_schema

    @classmethod
    def get_all_channels_info(cls, file_path: FilePathType):
        """Retrieve and inspect necessary channel information prior to initialization."""
        assert HAVE_SONPY, INSTALL_MESSAGE
        return cls.RX.get_all_channels_info(file_path=file_path)

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        assert HAVE_SONPY, INSTALL_MESSAGE
        stream_id = None
        if Path(file_path).suffix == ".smr":
            stream_id = "1"
        super().__init__(file_path=file_path, stream_id=stream_id, verbose=verbose)
