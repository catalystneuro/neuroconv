"""Authors: Alessio Buccino."""
from warnings import warn

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import FilePathType


class SIPickleRecordingInterface(BaseRecordingExtractorInterface):
    """Primary interface for reading and converting SpikeInterface Recording objects through .pkl files."""

    ExtractorModuleName = "spikeextractors"
    ExtractorName = "load_extractor_from_pickle"

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """
        Initialize reading of SpikeInterface Pickle files.

        Parameters
        ----------
        file_path : FilePathType
            Path to .pkl file.
        verbose : bool, optional, default=True
        """
        # TODO: Remove entire interfaces
        warn(
            message=(
                "Interfaces using a spikeextractors backend will soon be deprecated! "
                "Please use the SpikeInterface backend instead."
            ),
            category=DeprecationWarning,
            stacklevel=2,
        )

        from spikeextractors import load_extractor_from_pickle

        self.recording_extractor = load_extractor_from_pickle(pkl_file=file_path)
        self.subset_channels = None
        self.source_data = dict(file_path=file_path)
        self.verbose = verbose
        self.es_key = None


class SIPickleSortingInterface(BaseSortingExtractorInterface):
    """Primary interface for reading and converting SpikeInterface Sorting objects through .pkl files."""

    ExtractorModuleName = "spikeextractors"
    ExtractorName = "load_extractor_from_pickle"

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        from spikeextractors import load_extractor_from_pickle

        self.sorting_extractor = load_extractor_from_pickle(pkl_file=file_path)
        self.source_data = dict(file_path=file_path)
        self.verbose = verbose
