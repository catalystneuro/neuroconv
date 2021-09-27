"""Authors: Alessio Buccino."""
from spikeextractors import load_extractor_from_pickle

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils.json_schema import FilePathType


class SIPickleRecordingExtractorInterface(BaseRecordingExtractorInterface):
    """Primary interface for reading and converting SpikeInterface Recording objects through .pkl files."""

    RX = None

    def __init__(self, pkl_file: FilePathType):
        self.recording_extractor = load_extractor_from_pickle(pkl_file=pkl_file)
        self.subset_channels = None
        self.source_data = dict(pkl_file=pkl_file)


class SIPickleSortingExtractorInterface(BaseSortingExtractorInterface):
    """Primary interface for reading and converting SpikeInterface Sorting objects through .pkl files."""

    SX = None

    def __init__(self, pkl_file: FilePathType):
        self.sorting_extractor = load_extractor_from_pickle(pkl_file=pkl_file)
        self.source_data = dict(pkl_file=pkl_file)
