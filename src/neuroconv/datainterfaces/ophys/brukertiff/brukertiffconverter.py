import warnings
from typing import Literal

from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from ... import (
    BrukerTiffImagingInterface,
    BrukerTiffMultiPlaneImagingInterface,
    BrukerTiffSinglePlaneImagingInterface,
)
from ....basedatainterface import BaseDataInterface
from ....nwbconverter import ConverterPipe
from ....utils import DeepDict, dict_deep_update, get_json_schema_from_method_signature


class BrukerTiffConverter(ConverterPipe):
    """Convenience converter that auto-detects channels in a Bruker TIFF folder.

    Builds one :class:`~neuroconv.datainterfaces.BrukerTiffImagingInterface` per channel
    found in the folder's OME-XML, so multi-channel acquisitions (e.g. dual-color)
    produce one ``ImagingPlane`` and one ``TwoPhotonSeries`` per channel without manual
    enumeration. Single-channel folders pass through with no channel selection.

    Volumetric data is exposed as a single 4D ``TwoPhotonSeries`` per channel. For one
    ``TwoPhotonSeries`` per z-plane (the legacy "disjoint" mode), use
    :class:`~neuroconv.converters.BrukerTiffMultiPlaneConverter` until per-plane
    selection lands on ``BrukerTiffImagingExtractor`` upstream.

    Per-channel options (``stub_test``, ``stub_samples``, etc.) are passed through the
    standard ``conversion_options`` dict keyed by channel interface name, e.g.::

        converter.run_conversion(
            nwbfile_path=...,
            conversion_options={"BrukerImaging_Ch1": {"stub_test": True, "stub_samples": 100}},
        )
    """

    display_name = "Bruker TIFF Imaging"
    keywords = BrukerTiffImagingInterface.keywords
    associated_suffixes = BrukerTiffImagingInterface.associated_suffixes
    info = "Auto-channel-enumerated converter for Bruker TIFF imaging data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__)
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Folder containing Bruker .ome.tif files and the matching configuration .xml."
        return source_schema

    @validate_call
    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        """
        Parameters
        ----------
        folder_path : DirectoryPath
            Folder containing Bruker .ome.tif files and the matching configuration .xml.
        verbose : bool, default: False
        """
        channel_names = BrukerTiffImagingInterface.get_available_channels(folder_path=folder_path)

        data_interfaces: dict[str, BrukerTiffImagingInterface] = {}
        if len(channel_names) == 1:
            data_interfaces["BrukerImaging"] = BrukerTiffImagingInterface(
                folder_path=folder_path,
                verbose=verbose,
            )
        else:
            for channel_name in channel_names:
                data_interfaces[f"BrukerImaging_{channel_name}"] = BrukerTiffImagingInterface(
                    folder_path=folder_path,
                    channel_name=channel_name,
                    verbose=verbose,
                )

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)


class BrukerTiffMultiPlaneConverter(BaseDataInterface):
    """
    Converter class for Bruker volumetric (multi-plane) imaging data.

    Notes
    -----
    The ``plane_separation_type="contiguous"`` mode is fully covered by the unified
    :class:`~neuroconv.datainterfaces.BrukerTiffImagingInterface`. The
    ``plane_separation_type="disjoint"`` mode (one ``TwoPhotonSeries`` per z-plane)
    has no replacement on the unified interface yet, so this converter is kept
    available for that case until a ``plane_index`` selector lands in the upstream
    ``BrukerTiffImagingExtractor``.
    """

    display_name = "Bruker TIFF Imaging (multiple channels, multiple planes)"
    keywords = BrukerTiffMultiPlaneImagingInterface.keywords
    associated_suffixes = BrukerTiffMultiPlaneImagingInterface.associated_suffixes
    info = "Interface for handling all channels and all planes of Bruker imaging data."

    @classmethod
    def get_source_schema(cls):
        source_schema = get_json_schema_from_method_signature(cls)
        source_schema["properties"]["folder_path"][
            "description"
        ] = "The folder that contains the Bruker TIF image files (.ome.tif) and configuration files (.xml, .env)."
        return source_schema

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        plane_separation_type: Literal["disjoint", "contiguous"],
        verbose: bool = False,
    ):
        """
        Initializes the data interfaces for Bruker volumetric imaging data stream.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder that contains the Bruker TIF image files (.ome.tif) and configuration files (.xml, .env).
        plane_separation_type: {'contiguous', 'disjoint'}
            Defines how to write volumetric imaging data. Use 'contiguous' to create the volumetric two photon series,
            and 'disjoint' to create separate imaging plane and two photon series for each plane.
        verbose : bool, default: False
            Controls verbosity.
        """
        self.verbose = verbose
        self.data_interface_objects = dict()

        streams = BrukerTiffMultiPlaneImagingInterface.get_streams(
            folder_path=folder_path,
            plane_separation_type=plane_separation_type,
        )

        channel_streams = streams["channel_streams"]
        interface_name = "BrukerImaging"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            for channel_stream_name in channel_streams:
                plane_streams = streams["plane_streams"][channel_stream_name]
                for plane_stream in plane_streams:
                    if len(plane_streams) > 1:
                        interface_name += plane_stream.replace("_", "")
                    if plane_separation_type == "contiguous":
                        self.data_interface_objects[interface_name] = BrukerTiffMultiPlaneImagingInterface(
                            folder_path=folder_path,
                            stream_name=plane_stream,
                        )
                    elif plane_separation_type == "disjoint":
                        self.data_interface_objects[interface_name] = BrukerTiffSinglePlaneImagingInterface(
                            folder_path=folder_path,
                            stream_name=plane_stream,
                        )

    def get_metadata(self) -> DeepDict:
        metadata = DeepDict()
        for interface in self.data_interface_objects.values():
            interface_metadata = interface.get_metadata()
            metadata = dict_deep_update(metadata, interface_metadata)
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata,
        stub_test: bool = False,
        stub_samples: int = 100,
    ):
        """
        Add data from multiple data interfaces to the specified NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile object to which the data will be added.
        metadata : dict
            Metadata dictionary containing information to describe the data being added to the NWB file.
        stub_test : bool, optional
            If True, only a subset of the data (up to `stub_samples`) will be added for testing purposes. Default is False.
        stub_samples : int, default: 100
            The number of samples (frames) to use for testing.
        """
        for photon_series_index, (interface_name, data_interface) in enumerate(self.data_interface_objects.items()):
            data_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                photon_series_index=photon_series_index,
                stub_test=stub_test,
                stub_samples=stub_samples,
            )


class BrukerTiffSinglePlaneConverter(BaseDataInterface):
    """
    Primary data interface class for converting Bruker imaging data with multiple channels and a single plane.
    """

    display_name = "Bruker TIFF Imaging (multiple channels, single plane)"
    keywords = BrukerTiffMultiPlaneImagingInterface.keywords
    associated_suffixes = BrukerTiffMultiPlaneImagingInterface.associated_suffixes
    info = "Interface for handling multiple channels of a single plane of Bruker imaging data."

    @classmethod
    def get_source_schema(cls):
        return get_json_schema_from_method_signature(cls)

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        verbose: bool = False,
    ):
        """
        Initializes the data interfaces for Bruker imaging data stream.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder that contains the Bruker TIF image files (.ome.tif) and configuration files (.xml, .env).
        verbose : bool, default: False
            Controls verbosity.
        """
        warnings.warn(
            "BrukerTiffSinglePlaneConverter is deprecated and will be removed on or after November 2026. "
            "Use BrukerTiffImagingInterface instead.",
            FutureWarning,
            stacklevel=2,
        )

        from roiextractors.extractors.tiffimagingextractors.brukertiffimagingextractor import (
            _determine_imaging_is_volumetric,
        )

        if _determine_imaging_is_volumetric(folder_path=folder_path):
            raise ValueError("For volumetric imaging data use BrukerTiffMultiPlaneConverter.")

        self.verbose = verbose
        self.data_interface_objects = dict()

        streams = BrukerTiffSinglePlaneImagingInterface.get_streams(folder_path=folder_path)
        channel_streams = streams["channel_streams"]
        interface_name = "BrukerImaging"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            for channel_stream_name in channel_streams:
                if len(channel_streams) > 1:
                    interface_name += channel_stream_name.replace("_", "")
                self.data_interface_objects[interface_name] = BrukerTiffSinglePlaneImagingInterface(
                    folder_path=folder_path,
                    stream_name=channel_stream_name,
                )

    def get_metadata(self) -> DeepDict:
        metadata = DeepDict()
        for interface in self.data_interface_objects.values():
            interface_metadata = interface.get_metadata()
            metadata = dict_deep_update(metadata, interface_metadata)
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata,
        stub_test: bool = False,
        stub_samples: int = 100,
    ):
        """
        Add data from all instantiated data interfaces to the provided NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile object to which the data will be added.
        metadata : dict
            Metadata dictionary containing information about the data to be added.
        stub_test : bool, optional
            If True, only a subset of the data (defined by `stub_samples`) will be added for testing purposes,
            by default False.
        stub_samples : int, default: 100
            The number of samples (frames) to use for testing.
        """
        for photon_series_index, (interface_name, data_interface) in enumerate(self.data_interface_objects.items()):
            data_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                photon_series_index=photon_series_index,
                stub_test=stub_test,
                stub_samples=stub_samples,
            )
