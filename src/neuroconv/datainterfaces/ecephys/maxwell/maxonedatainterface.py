import os
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
        *,
        hdf5_plugin_path: DirectoryPath | None = None,
        download_plugin: bool = True,
        verbose: bool = False,
        es_key: str | None = None,
        metadata_key: str | None = None,
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
        metadata_key : str, optional
            Key that indexes this interface's entries in the dict-based metadata. Defaults to
            ``"maxone_recording"``.
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

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key, metadata_key=metadata_key)

        if metadata_key is None:
            self.metadata_key = "maxone_recording"

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        metadata = super().get_metadata(use_new_metadata_format=use_new_metadata_format)

        maxwell_version = self.recording_extractor.neo_reader.raw_annotations["blocks"][0]["maxwell_version"]
        description = f"Recorded using Maxwell version '{maxwell_version}'."

        if use_new_metadata_format:
            from ....tools.spikeinterface.spikeinterface import _get_group_name

            # The old format only rewrote the description of the pipeline's placeholder device, which left
            # the device itself unnamed. Here the recording system is named after the format it is, with
            # the Maxwell software version the file records as its description.
            device_metadata_key = "maxone_device"
            device_model_metadata_key = "maxone_model"
            metadata["DeviceModels"] = {
                device_model_metadata_key: dict(name="MaxOne", manufacturer="MaxWell Biosystems")
            }
            metadata["Devices"] = {
                device_metadata_key: dict(
                    name="MaxOne", description=description, device_model_metadata_key=device_model_metadata_key
                )
            }

            channel_group_names = set(_get_group_name(recording=self.recording_extractor).tolist())
            metadata["Ecephys"]["ElectrodeGroups"] = {
                group_name: dict(name=group_name, device_metadata_key=device_metadata_key)
                for group_name in channel_group_names
            }

            return metadata

        metadata["Ecephys"]["Device"][0].update(description=description)

        return metadata
