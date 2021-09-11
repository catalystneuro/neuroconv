"""Authors: Alessio Buccino."""
from spikeextractors import load_extractor_from_pickle

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils.json_schema import get_base_schema, FilePathType


class SIPickleRecordingExtractorInterface(BaseRecordingExtractorInterface):
    """Primary interface for reading and converting SpikeInterface objects through Pickle files."""

    RX = load_extractor_from_pickle

    def __init__(self, pkl_file: FilePathType):
        super().__init__(pkl_file=pkl_file)


class SIPickleSortingExtractorInterface(BaseSortingExtractorInterface):
    """Primary interface for reading and converting SpikeInterface objects through Pickle files."""

    SX = load_extractor_from_pickle

    @classmethod
    def get_source_schema(cls):
        return get_base_schema(required=["pkl_file"], properties=dict(pkl_file=dict(type="string")))

    def __init__(self, pkl_file: FilePathType):
        super().__init__(pkl_file=pkl_file)
