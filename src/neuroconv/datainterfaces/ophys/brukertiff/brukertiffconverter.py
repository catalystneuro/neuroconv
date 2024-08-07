# TODO: Remove add_to_nwbfile and run_conversion and let inheritance handle it

import warnings
from typing import Literal, Optional

from pynwb import NWBFile

from ... import (
    BrukerTiffMultiPlaneImagingInterface,
    BrukerTiffSinglePlaneImagingInterface,
)
from ....nwbconverter import NWBConverter
from ....tools.nwb_helpers import make_or_load_nwbfile
from ....utils import FolderPathType, get_schema_from_method_signature


class BrukerTiffMultiPlaneConverter(NWBConverter):
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
        folder_path: FolderPathType,
        plane_separation_type: Literal["disjoint", "contiguous"] = None,
        verbose: bool = False,
    ):
        """
        Initializes the data interfaces for Bruker volumetric imaging data stream.

        Parameters
        ----------
        folder_path : PathType
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
        stub_test: Optional[bool] = False,
        stub_frames: Optional[int] = 100,
        conversion_options: Optional[dict] = None,
    ):

        # Put deprecation warnings for passing stub_test and stub_frames directly
        if stub_test is not None:
            warnings.warn(
                "The 'stub_test' argument is deprecated and will be removed at some point after February 2025"
                "Please set 'stub_test' during the initialization of the BrukerTiffMultiPlaneConverter instance.",
                DeprecationWarning,
                stacklevel=2,
            )

        if stub_frames is not None:
            warnings.warn(
                "The 'stub_frames' argument is deprecated and will be removed at some point after February 2025"
                "Please set 'stub_frames' during the initialization of the BrukerTiffMultiPlaneConverter instance.",
                DeprecationWarning,
                stacklevel=2,
            )

        conversion_options = conversion_options or dict()
        for photon_series_index, (interface_name, data_interface) in enumerate(self.data_interface_objects.items()):
            interface_conversion_options = conversion_options.get(interface_name, dict())
            interface_conversion_options["stub_test"] = stub_test
            interface_conversion_options["stub_frames"] = stub_frames

            data_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                photon_series_index=photon_series_index,
                **interface_conversion_options,
            )

    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        stub_test: bool = False,
        stub_frames: int = 100,
        conversion_options: Optional[dict] = None,
    ) -> None:

        # Put deprecation warnings for passing stub_test and stub_frames directly
        if stub_test is not None:
            warnings.warn(
                "The 'stub_test' argument is deprecated and will be removed at some point after February 2025"
                "Please set 'stub_test' during the initialization of the BrukerTiffMultiPlaneConverter instance.",
                DeprecationWarning,
                stacklevel=2,
            )

        if stub_frames is not None:
            warnings.warn(
                "The 'stub_frames' argument is deprecated and will be removed at some point after February 2025"
                "Please set 'stub_frames' during the initialization of the BrukerTiffMultiPlaneConverter instance.",
                DeprecationWarning,
                stacklevel=2,
            )

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
            self.add_to_nwbfile(
                nwbfile=nwbfile_out,
                metadata=metadata,
                stub_test=stub_test,
                stub_frames=stub_frames,
                conversion_options=conversion_options,
            )


class BrukerTiffSinglePlaneConverter(NWBConverter):
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
        folder_path: FolderPathType,
        verbose: bool = False,
    ):
        """
        Initializes the data interfaces for Bruker imaging data stream.

        Parameters
        ----------
        folder_path : PathType
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
        stub_test: Optional[bool] = False,
        stub_frames: Optional[int] = 100,
        conversion_options: Optional[dict] = None,
    ):

        # Put deprecation warnings for passing stub_test and stub_frames directly
        if stub_test is not None:
            warnings.warn(
                "The 'stub_test' argument is deprecated and will be removed at some point after February 2025"
                "Please set 'stub_test' during the initialization of the BrukerTiffMultiPlaneConverter instance.",
                DeprecationWarning,
                stacklevel=2,
            )

        if stub_frames is not None:
            warnings.warn(
                "The 'stub_frames' argument is deprecated and will be removed at some point after February 2025"
                "Please set 'stub_frames' during the initialization of the BrukerTiffMultiPlaneConverter instance.",
                DeprecationWarning,
                stacklevel=2,
            )

        conversion_options = conversion_options or dict()
        for photon_series_index, (interface_name, data_interface) in enumerate(self.data_interface_objects.items()):
            interface_conversion_options = conversion_options.get(interface_name, dict())
            interface_conversion_options["stub_test"] = stub_test
            interface_conversion_options["stub_frames"] = stub_frames

            data_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                photon_series_index=photon_series_index,
                **interface_conversion_options,
            )

    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        stub_test: Optional[bool] = False,
        stub_frames: Optional[int] = 100,
        conversion_options: Optional[dict] = None,
    ) -> None:

        # Put deprecation warnings for passing stub_test and stub_frames directly
        if stub_test is not None:
            warnings.warn(
                "The 'stub_test' argument is deprecated and will be removed at some point after February 2025"
                "Please set 'stub_test' during the initialization of the BrukerTiffMultiPlaneConverter instance.",
                DeprecationWarning,
                stacklevel=2,
            )

        if stub_frames is not None:
            warnings.warn(
                "The 'stub_frames' argument is deprecated and will be removed at some point after February 2025"
                "Please set 'stub_frames' during the initialization of the BrukerTiffMultiPlaneConverter instance.",
                DeprecationWarning,
                stacklevel=2,
            )

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
            self.add_to_nwbfile(
                nwbfile=nwbfile_out,
                metadata=metadata,
                stub_test=stub_test,
                stub_frames=stub_frames,
                conversion_options=conversion_options,
            )
