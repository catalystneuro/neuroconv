"""Authors: Cody Baker."""
from typing import Optional

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils.types import FilePathType, FolderPathType


class MaxOneRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting MaxOne data.

    Using the :py:class:`~spikeinterface.extractors.MaxwellRecordingExtractor`.
    """

    ExtractorName = "MaxwellRecordingExtractor"

    @staticmethod
    def auto_install_maxwell_hdf5_compression_plugin(hdf5_plugin_path: Optional[FolderPathType] = None):
        """
        If you do not yet have the Maxwell compression plugin installed, this function will automatically install it.

        Parameters
        ----------
        hdf5_plugin_path: string or Path, optional
            Path to your systems HDF5 plugin library.
            Default is None.
        """
        from neo.rawio.maxwellrawio import auto_install_maxwell_hdf5_compression_plugin

        auto_install_maxwell_hdf5_compression_plugin(hdf5_plugin_path=hdf5_plugin_path)

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
