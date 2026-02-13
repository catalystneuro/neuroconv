import os
import warnings
from pathlib import Path
from platform import system

from pydantic import DirectoryPath, FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import DeepDict


class MaxOneRecordingInterface(BaseRecordingExtractorInterface):  # pragma: no cover
    """
    Primary data interface class for converting MaxOne data.

    Uses the :py:func:`~spikeinterface.extractors.read_maxwell` reader from SpikeInterface.
    """

    display_name = "MaxOne Recording"
    associated_suffixes = (".raw", ".h5")
    info = "Interface for MaxOne recording data."

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import (
            MaxwellRecordingExtractor,
        )

        return MaxwellRecordingExtractor

    @staticmethod
    def auto_install_maxwell_hdf5_compression_plugin(
        hdf5_plugin_path: DirectoryPath | None = None, download_plugin: bool = True
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
        *args,  # TODO: change to * (keyword only) on or after August 2026
        hdf5_plugin_path: DirectoryPath | None = None,
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
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "hdf5_plugin_path",
                "download_plugin",
                "verbose",
                "es_key",
            ]
            num_positional_args_before_args = 1  # file_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to MaxOneRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            hdf5_plugin_path = positional_values.get("hdf5_plugin_path", hdf5_plugin_path)
            download_plugin = positional_values.get("download_plugin", download_plugin)
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)

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

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        maxwell_version = self.recording_extractor.neo_reader.raw_annotations["blocks"][0]["maxwell_version"]
        metadata["Ecephys"]["Device"][0].update(description=f"Recorded using Maxwell version '{maxwell_version}'.")

        return metadata
