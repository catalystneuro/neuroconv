from pathlib import Path
from xml.etree import ElementTree

from pydantic import FilePath, validate_call

from .thordatainterface import ThorImagingInterface
from ....nwbconverter import ConverterPipe
from ....tools.nwb_helpers import get_default_nwbfile_metadata
from ....utils import DeepDict, dict_deep_update, get_json_schema_from_method_signature


class ThorConverter(ConverterPipe):
    """Convert a ThorImageLS acquisition.

    Point this at the first OME-TIFF of the acquisition and every channel named in the accompanying
    ``Experiment.xml`` is written: one ``ImagingPlane`` and one ``TwoPhotonSeries`` per channel, all
    referring to a single ``Device`` named ``ThorMicroscope``. A single-channel acquisition needs no
    extra arguments.
    """

    display_name = "ThorLabs TIFF Imaging"
    keywords = ThorImagingInterface.keywords
    associated_suffixes = ThorImagingInterface.associated_suffixes
    info = "Auto-channel-enumerated converter for ThorImageLS TIFF data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__)
        source_schema["properties"]["file_path"][
            "description"
        ] = "Path to the first OME-TIFF file of the acquisition (e.g. 'ChanA_001_001_001_001.tif')."
        return source_schema

    @classmethod
    def get_available_channels(cls, file_path: FilePath) -> list[str]:
        """
        Get the channels named in the acquisition's ``Experiment.xml``.

        These are the names :class:`~neuroconv.datainterfaces.ThorImagingInterface` accepts. The
        names are read from ``Experiment.xml`` rather than through
        ``ThorTiffImagingExtractor.get_available_channel_names``, which reads the OME-XML instead and
        falls back to ``["0", "1"]`` when it carries no channel names, as ThorImageLS OME-XML does.
        Those numeric stand-ins are not names the extractor accepts, so a caller following them gets
        ``ValueError: Channel '0' not found. Available channels: ['ChanA', 'ChanB']``.

        Parameters
        ----------
        file_path : FilePath
            Path to the first OME-TIFF file of the acquisition.

        Returns
        -------
        list of str
            The available channel names, e.g. ``["ChanA", "ChanB"]``.
        """
        experiment_file_path = Path(file_path).parent / "Experiment.xml"
        if not experiment_file_path.is_file():
            raise FileNotFoundError(
                f"No 'Experiment.xml' next to '{file_path}'. ThorImageLS writes it beside the TIFF "
                "files of the acquisition, and the channel names are read from it."
            )

        root = ElementTree.parse(experiment_file_path).getroot()
        wavelengths = root.find("Wavelengths")
        # The block also carries a 'ChannelEnable Set' whose meaning across ThorImageLS versions we
        # have not established, so the names are taken as written rather than filtered by it.
        return [wavelength.get("name") for wavelength in wavelengths.findall("Wavelength")]

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the first OME-TIFF file of the acquisition (e.g. 'ChanA_001_001_001_001.tif').
            The 'Experiment.xml' that names the channels is read from the same folder.
        verbose : bool, default: False
            Controls verbosity.
        """
        channel_names = self.get_available_channels(file_path=file_path)
        single_channel = len(channel_names) == 1

        data_interfaces = {}
        for channel_name in channel_names:
            interface_name = "ThorImaging" if single_channel else f"ThorImaging_{channel_name}"
            data_interfaces[interface_name] = ThorImagingInterface(
                file_path=file_path,
                # The interface takes the only channel by itself, and naming it changes the metadata key
                # and the written names, which would make a single-channel file differ from the one the
                # interface writes on its own.
                channel_name=None if single_channel else channel_name,
                verbose=verbose,
            )

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        """
        Get metadata for every channel of the acquisition.

        Parameters
        ----------
        use_new_metadata_format : bool, default: True
            Ask the channel interfaces for the dict-based format. This defaults to True where the
            interfaces themselves still default to False, because the old list-based format addresses
            a photon series by its position in a list, which cannot name one entry per channel
            unambiguously; the dict-based format keys each channel's entry by its metadata key.

        Returns
        -------
        DeepDict
            The metadata of every channel, merged.
        """
        metadata = get_default_nwbfile_metadata()
        for interface in self.data_interface_objects.values():
            interface_metadata = self._get_interface_metadata(
                interface=interface, use_new_metadata_format=use_new_metadata_format
            )
            # Entries are keyed per channel, so a list inside one of them describes that channel and is
            # not something to merge across interfaces. Appending would also dedupe the repeated values
            # of a symmetric field, and a square field of view's [x, x] would reach the file as [x].
            metadata = dict_deep_update(metadata, interface_metadata, append_list=False)
        return metadata
