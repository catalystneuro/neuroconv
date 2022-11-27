"""Authors: Cody Baker."""
from typing import List, Optional

from neo.rawio.maxwellrawio import auto_install_maxwell_hdf5_compression_plugin

from .maxonedatainterface import MaxOneRecordingInterface
from ....utils.types import FilePathType, FolderPathType


class MaxTwoRecordingInterface(MaxOneRecordingInterface):
    """
    Primary data interface class for converting MaxTwo data.

    Must specify the name of the recording session within the file, as well as the stream name for that recording.

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
        auto_install_maxwell_hdf5_compression_plugin(hdf5_plugin_path=hdf5_plugin_path)

    @staticmethod
    def get_recording_names(file_path: FilePathType) -> Optional[List[str]]:
        """
        If you do not know the name of the recording sessions, you may retrieve them with this helper function.

        Adaptation of https://github.com/NeuralEnsemble/python-neo/blob/master/neo/rawio/maxwellrawio.py#L56-L72

        Parameters
        ----------
        file_path: string or Path
            Path to the .raw.h5 file.
        verbose: boolean
            Allows verbose.
            Default is True.
        """
        import h5py

        with h5py.File(path=file_path, mode="r") as h5:
            version = h5["version"][0].decode()

            stream_ids = list(h5["wells"].keys())
            if int(version) <= 20160704:
                print("This version of MaxTwo does not support multiple recording sessions.")
                return

            all_rec_names = set()
            for stream_id in stream_ids:
                all_rec_names.update(h5["wells"][stream_id].keys())

            return all_rec_names

    @staticmethod
    def get_stream_names(file_path: FilePathType, recording_name: str) -> List[str]:
        """
        If you do not know the name of the streams, you may retrieve them with this helper function.

        Parameters
        ----------
        file_path: string or Path
            Path to the .raw.h5 file.
        recording_name: string
            Name of the recording session to extract streams from.
        verbose: boolean
            Allows verbose.
            Default is True.
        """
        from spikeinterface.extractors import MaxwellRecordingExtractor

        stream_names, _ = MaxwellRecordingExtractor.get_streams(file_path=file_path, rec_name=recording_name)
        return stream_names

    def __init__(self, file_path: FilePathType, recording_name: str, stream_name: str, verbose: bool = True):
        """
        Load and prepare data for MaxTwo.

        Parameters
        ----------
        folder_path: string or Path
            Path to the .raw.h5 file.
        recording_name: string
            Name of the recording session to extract streams from.
        verbose: boolean
            Allows verbose.
            Default is True.
        """
        from spikeinterface.extractors import MaxwellRecordingExtractor

        stream_names, stream_ids = MaxwellRecordingExtractor.get_streams(file_path=file_path, rec_name=recording_name)
        stream_index = stream_names.index(stream_name)
        super().__init__(
            file_path=file_path, rec_name=recording_name, stream_id=stream_ids[stream_index], verbose=verbose
        )
