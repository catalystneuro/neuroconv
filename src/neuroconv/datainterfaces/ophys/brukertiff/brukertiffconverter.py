from typing import Literal, Optional

from pydantic import DirectoryPath, FilePath
from pynwb import NWBFile

from ... import (
    BrukerTiffMultiPlaneImagingInterface,
    BrukerTiffSinglePlaneImagingInterface,
)
from ....nwbconverter import NWBConverter
from ....tools.nwb_helpers import make_or_load_nwbfile
from ....utils import get_schema_from_method_signature


class BrukerTiffMultiPlaneConverter(NWBConverter):
    """
    Converter class for Bruker imaging data with multiple channels and multiple planes.
    """

    display_name = "Bruker TIFF Imaging (multiple channels, multiple planes)"
    keywords = BrukerTiffMultiPlaneImagingInterface.keywords
    associated_suffixes = BrukerTiffMultiPlaneImagingInterface.associated_suffixes
    info = "Interface for handling all channels and all planes of Bruker imaging data."

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(cls)
        source_schema["properties"]["folder_path"][
            "description"
        ] = "The folder that contains the Bruker TIF image files (.ome.tif) and configuration files (.xml, .env)."
        return source_schema

    def get_conversion_options_schema(self):
        interface_name = list(self.data_interface_objects.keys())[0]
        return self.data_interface_objects[interface_name].get_conversion_options_schema()

    def __init__(
        self,
        folder_path: DirectoryPath,
        plane_separation_type: Literal["disjoint", "contiguous"] = None,
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
        verbose : bool, default: True
            Controls verbosity.
        """
        self.verbose = verbose
        self.data_interface_objects = dict()

        if plane_separation_type is None or plane_separation_type not in ["disjoint", "contiguous"]:
            raise ValueError(
                "For volumetric imaging data the plane separation method must be one of 'disjoint' or 'contiguous'."
            )

        streams = BrukerTiffMultiPlaneImagingInterface.get_streams(
            folder_path=folder_path,
            plane_separation_type=plane_separation_type,
        )

        channel_streams = streams["channel_streams"]
        interface_name = "BrukerImaging"
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

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata,
        stub_test: bool = False,
        stub_frames: int = 100,
    ):
        for photon_series_index, (interface_name, data_interface) in enumerate(self.data_interface_objects.items()):
            data_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                photon_series_index=photon_series_index,
                stub_test=stub_test,
                stub_frames=stub_frames,
            )

    def run_conversion(
        self,
        nwbfile_path: Optional[FilePath] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        stub_test: bool = False,
        stub_frames: int = 100,
    ) -> None:
        if metadata is None:
            metadata = self.get_metadata()

        self.validate_metadata(metadata=metadata)

        self.temporally_align_data_interfaces()

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
        ) as nwbfile_out:
            self.add_to_nwbfile(nwbfile=nwbfile_out, metadata=metadata, stub_test=stub_test, stub_frames=stub_frames)


class BrukerTiffSinglePlaneConverter(NWBConverter):
    """
    Primary data interface class for converting Bruker imaging data with multiple channels and a single plane.
    """

    display_name = "Bruker TIFF Imaging (multiple channels, single plane)"
    keywords = BrukerTiffMultiPlaneImagingInterface.keywords
    associated_suffixes = BrukerTiffMultiPlaneImagingInterface.associated_suffixes
    info = "Interface for handling multiple channels of a single plane of Bruker imaging data."

    @classmethod
    def get_source_schema(cls):
        return get_schema_from_method_signature(cls)

    def get_conversion_options_schema(self):
        interface_name = list(self.data_interface_objects.keys())[0]
        return self.data_interface_objects[interface_name].get_conversion_options_schema()

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
        verbose : bool, default: True
            Controls verbosity.
        """
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
        for channel_stream_name in channel_streams:
            if len(channel_streams) > 1:
                interface_name += channel_stream_name.replace("_", "")
            self.data_interface_objects[interface_name] = BrukerTiffSinglePlaneImagingInterface(
                folder_path=folder_path,
                stream_name=channel_stream_name,
            )

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata,
        stub_test: bool = False,
        stub_frames: int = 100,
    ):
        for photon_series_index, (interface_name, data_interface) in enumerate(self.data_interface_objects.items()):
            data_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                photon_series_index=photon_series_index,
                stub_test=stub_test,
                stub_frames=stub_frames,
            )

    def run_conversion(
        self,
        nwbfile_path: Optional[FilePath] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        stub_test: bool = False,
        stub_frames: int = 100,
    ) -> None:
        if metadata is None:
            metadata = self.get_metadata()

        self.validate_metadata(metadata=metadata)

        self.temporally_align_data_interfaces()

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
        ) as nwbfile_out:
            self.add_to_nwbfile(nwbfile=nwbfile_out, metadata=metadata, stub_test=stub_test, stub_frames=stub_frames)
