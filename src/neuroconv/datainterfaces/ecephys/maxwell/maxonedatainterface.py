import os
from pathlib import Path
from platform import system
from typing import Optional

from pydantic import DirectoryPath, FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class MaxOneRecordingInterface(BaseRecordingExtractorInterface):  # pragma: no cover
    """
    Primary data interface class for converting MaxOne data.

    Using the :py:class:`~spikeinterface.extractors.MaxwellRecordingExtractor`.
    """

    display_name = "MaxOne Recording"
    associated_suffixes = (".raw", ".h5")
    info = "Interface for MaxOne recording data."

    ExtractorName = "MaxwellRecordingExtractor"

    @staticmethod
    def auto_install_maxwell_hdf5_compression_plugin(
        hdf5_plugin_path: Optional[DirectoryPath] = None, download_plugin: bool = True
    ) -> None:
        """
        If you do not yet have the Maxwell compression plugin installed, this function will automatically install it.

        Parameters
        ----------
        hdf5_plugin_path : string or Path, optional
            Path to your systems HDF5 plugin library.
            Uses the home directory by default.
        download_plugin : boolean, default: True
            Whether to force download of the decompression plugin.
            It's a very lightweight install but does require an internet connection.
            This is left as True for seamless passive usage and should not impact performance.
        """
        from neo.rawio.maxwellrawio import auto_install_maxwell_hdf5_compression_plugin

        auto_install_maxwell_hdf5_compression_plugin(hdf5_plugin_path=hdf5_plugin_path, force_download=download_plugin)

    def __init__(
        self,
        file_path: FilePath,
        hdf5_plugin_path: Optional[DirectoryPath] = None,
        download_plugin: bool = True,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ) -> None:
        """
        Load and prepare data for MaxOne.

        Parameters
        ----------
        file_path : string or Path
            Path to the .raw.h5 file.
        hdf5_plugin_path : string or Path, optional
            Path to your systems HDF5 plugin library.
            Uses the home directory by default.
        download_plugin : boolean, default: True
            Whether to force download of the decompression plugin.
            It's a very lightweight install but does require an internet connection.
            This is left as True for seamless passive usage and should not impact performance.
        verbose : boolean, default: True
            Allows verbosity.
        es_key : str, default: "ElectricalSeries"
            The key of this ElectricalSeries in the metadata dictionary.
        """
        if system() != "Linux":
            raise NotImplementedError(
                "The MaxOneRecordingInterface has not yet been implemented for systems other than Linux."
            )

        hdf5_plugin_path = os.environ.get(
            "HDF5_PLUGIN_PATH",
            hdf5_plugin_path or Path.home() / "hdf5_plugin_path_maxwell",
        )
        os.environ["HDF5_PLUGIN_PATH"] = str(hdf5_plugin_path)

        if download_plugin:
            self.auto_install_maxwell_hdf5_compression_plugin(hdf5_plugin_path=hdf5_plugin_path)

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        maxwell_version = self.recording_extractor.neo_reader.raw_annotations["blocks"][0]["maxwell_version"]
        metadata["Ecephys"]["Device"][0].update(description=f"Recorded using Maxwell version '{maxwell_version}'.")

        return metadata
