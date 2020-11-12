"""Authors: Alessio Buccino."""
import spikeextractors as se

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface


class SIPickleRecordingExtractorInterface(BaseRecordingExtractorInterface):
    """Primary interface for reading and converting SpikeInterface objects through Pickle files."""

    RX = None

    @classmethod
    def get_input_schema(cls):
        """Return partial json schema for expected input arguments."""
        return dict(
            required=['pkl_file'],
            properties=dict(
                pkl_file=dict(type='string')
            )
        )

    def __init__(self, **input_args):
        self.input_args = input_args
        self.recording_extractor = se.load_extractor_from_pickle(**input_args)


class SIPickleSortingExtractorInterface(BaseSortingExtractorInterface):
    """Primary interface for reading and converting SpikeInterface objects through Pickle files."""

    SX = None

    @classmethod
    def get_input_schema(cls):
        """Return partial json schema for expected input arguments."""
        return dict(
            required=['pkl_file'],
            properties=dict(
                pkl_file=dict(type='string')
            )
        )

    def __init__(self, **input_args):
        self.input_args = input_args
        self.sorting_extractor = se.load_extractor_from_pickle(**input_args)
