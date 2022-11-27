"""Authors: Cody Baker."""
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface

from ....utils.types import FilePathType


class MaxOneRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting MaxOne data.

    Using the :py:class:`~spikeinterface.extractors.MaxwellRecordingExtractor`.
    """

    ExtractorName = "MaxwellRecordingExtractor"

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """
        Load and prepare data for MaxOne.

        Parameters
        ----------
        folder_path: string or Path
            Path to the .raw.h5 file.
        verbose: boolean
            Allows verbose.
            Default is True.
        """
        super().__init__(file_path=file_path, verbose=verbose)

    def get_metadata(self):
        metadata = super().get_metadata()

        maxwell_version = self.recording_extractor.neo_reader.raw_annotations["blocks"][0]["maxwell_version"]
        metadata["Ecephys"]["Device"][0].update(description=f"Recorded using Maxwell version '{maxwell_version}'.")

        return metadata
