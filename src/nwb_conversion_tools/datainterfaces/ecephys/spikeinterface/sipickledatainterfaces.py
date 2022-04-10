"""Authors: Alessio Buccino."""
from spikeextractors import load_extractor_from_pickle

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import FilePathType


class SIPickleRecordingExtractorInterface(BaseRecordingExtractorInterface):
    """Primary interface for reading and converting SpikeInterface Recording objects through .pkl files."""

    RX = None

    def __init__(self, file_path: FilePathType):
        self.recording_extractor = load_extractor_from_pickle(pkl_file=file_path)
        self.subset_channels = None
        self.source_data = dict(file_path=file_path)


class SIPickleSortingExtractorInterface(BaseSortingExtractorInterface):
    """Primary interface for reading and converting SpikeInterface Sorting objects through .pkl files."""

    SX = None

    def __init__(self, file_path: FilePathType):
        self.sorting_extractor = load_extractor_from_pickle(pkl_file=file_path)
        self.source_data = dict(file_path=file_path)
