import warnings
from typing import Literal

from pydantic import DirectoryPath, FilePath
from pynwb import NWBFile

from ... import (
    BrukerTiffMultiPlaneImagingInterface,
    BrukerTiffSinglePlaneImagingInterface,
)
from ....nwbconverter import NWBConverter
from ....tools.nwb_helpers import HDF5BackendConfiguration, ZarrBackendConfiguration
from ....utils import get_json_schema_from_method_signature


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
        source_schema = get_json_schema_from_method_signature(cls)
        source_schema["properties"]["folder_path"][
            "description"
        ] = "The folder that contains the Bruker TIF image files (.ome.tif) and configuration files (.xml, .env)."
        return source_schema

    def get_conversion_options_schema(self) -> dict:
        """
        Get the schema for the conversion options.

        Returns
        -------
        dict
            The schema dictionary containing conversion options for the Bruker TIFF converter.
        """
        return get_json_schema_from_method_signature(
            self.add_to_nwbfile, exclude=["nwbfile", "metadata", "conversion_options"]
        )

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
        verbose : bool, default: False
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
        stub_frames: int | None = None,
        stub_samples: int = 100,
        conversion_options: dict | None = None,
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
        stub_frames : int, optional
            .. deprecated:: February 2026
                Use `stub_samples` instead.
        stub_samples : int, default: 100
            The number of samples (frames) to use for testing. When provided, takes precedence over `stub_frames`.
        conversion_options : dict, optional
            Dictionary of conversion options. If provided, these values will override the direct parameters.
        """
        # Handle conversion_options if provided (from parent's run_conversion)
        if conversion_options:
            stub_test = conversion_options.get("stub_test", stub_test)
            stub_frames = conversion_options.get("stub_frames", stub_frames)
            stub_samples = conversion_options.get("stub_samples", stub_samples)

        # Handle deprecation of stub_frames in favor of stub_samples
        if stub_frames is not None and stub_samples != 100:
            raise ValueError("Cannot specify both 'stub_frames' and 'stub_samples'. Use 'stub_samples' only.")

        if stub_frames is not None:
            warnings.warn(
                "The 'stub_frames' parameter is deprecated and will be removed on or after February 2026. "
                "Use 'stub_samples' instead.",
                FutureWarning,
                stacklevel=2,
            )
            effective_stub_samples = stub_frames
        else:
            effective_stub_samples = stub_samples

        for photon_series_index, (interface_name, data_interface) in enumerate(self.data_interface_objects.items()):
            data_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                photon_series_index=photon_series_index,
                stub_test=stub_test,
                stub_samples=effective_stub_samples,
            )

    def run_conversion(
        self,
        nwbfile_path: FilePath,
        nwbfile: NWBFile | None = None,
        metadata: dict | None = None,
        overwrite: bool = False,
        stub_test: bool = False,
        stub_frames: int | None = None,
        stub_samples: int = 100,
        *,
        backend: Literal["hdf5", "zarr"] | None = None,
        backend_configuration: HDF5BackendConfiguration | ZarrBackendConfiguration | None = None,
    ) -> None:
        """
        Run the conversion process for the instantiated data interfaces and add data to the NWB file.

        Parameters
        ----------
        nwbfile_path : FilePath
            Path where the NWB file will be written.
        nwbfile : NWBFile, optional
            An in-memory NWBFile object. If None, a new NWBFile object will be created.
        metadata : dict, optional
            Metadata dictionary for describing the NWB file. If None, it will be auto-generated.
        overwrite : bool, optional
            If True, overwrites the existing NWB file at `nwbfile_path`. Default is False.
        stub_test : bool, optional
            If True, only a subset of the data will be added for testing purposes. Default is False.
        stub_frames : int, optional
            .. deprecated:: February 2026
                Use `stub_samples` instead.
        stub_samples : int, default: 100
            The number of samples (frames) to use for testing.
        backend : {"hdf5", "zarr"}, optional
            The type of backend to use when writing the file.
        backend_configuration : HDF5BackendConfiguration or ZarrBackendConfiguration, optional
            The configuration model to use when configuring the datasets for this backend.
        """
        # Pack the direct kwargs into conversion_options and delegate to parent
        conversion_options = {"stub_test": stub_test, "stub_samples": stub_samples}
        if stub_frames is not None:
            conversion_options["stub_frames"] = stub_frames

        super().run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            backend=backend,
            backend_configuration=backend_configuration,
            conversion_options=conversion_options,
        )


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
        return get_json_schema_from_method_signature(cls)

    def get_conversion_options_schema(self) -> dict:
        """
        Get the schema for the conversion options.

        Returns
        -------
        dict
            The schema dictionary containing conversion options for the Bruker TIFF converter.
        """
        return get_json_schema_from_method_signature(
            self.add_to_nwbfile, exclude=["nwbfile", "metadata", "conversion_options"]
        )

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
        stub_frames: int | None = None,
        stub_samples: int = 100,
        conversion_options: dict | None = None,
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
        stub_frames : int, optional
            .. deprecated:: February 2026
                Use `stub_samples` instead.
        stub_samples : int, default: 100
            The number of samples (frames) to use for testing. When provided, takes precedence over `stub_frames`.
        conversion_options : dict, optional
            Dictionary of conversion options. If provided, these values will override the direct parameters.
        """
        # Handle conversion_options if provided (from parent's run_conversion)
        if conversion_options:
            stub_test = conversion_options.get("stub_test", stub_test)
            stub_frames = conversion_options.get("stub_frames", stub_frames)
            stub_samples = conversion_options.get("stub_samples", stub_samples)

        # Handle deprecation of stub_frames in favor of stub_samples
        if stub_frames is not None and stub_samples != 100:
            raise ValueError("Cannot specify both 'stub_frames' and 'stub_samples'. Use 'stub_samples' only.")

        if stub_frames is not None:
            warnings.warn(
                "The 'stub_frames' parameter is deprecated and will be removed on or after February 2026. "
                "Use 'stub_samples' instead.",
                FutureWarning,
                stacklevel=2,
            )
            effective_stub_samples = stub_frames
        else:
            effective_stub_samples = stub_samples

        for photon_series_index, (interface_name, data_interface) in enumerate(self.data_interface_objects.items()):
            data_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                photon_series_index=photon_series_index,
                stub_test=stub_test,
                stub_samples=effective_stub_samples,
            )

    def run_conversion(
        self,
        nwbfile_path: FilePath,
        nwbfile: NWBFile | None = None,
        metadata: dict | None = None,
        overwrite: bool = False,
        stub_test: bool = False,
        stub_frames: int | None = None,
        stub_samples: int = 100,
        *,
        backend: Literal["hdf5", "zarr"] | None = None,
        backend_configuration: HDF5BackendConfiguration | ZarrBackendConfiguration | None = None,
    ) -> None:
        """
        Run the NWB conversion process for all instantiated data interfaces.

        Parameters
        ----------
        nwbfile_path : FilePath
            The file path where the NWB file will be written.
        nwbfile : NWBFile, optional
            An existing in-memory NWBFile object. If None, a new NWBFile object will be created.
        metadata : dict, optional
            Metadata dictionary. If None, metadata is automatically generated.
        overwrite : bool, optional
            If True, the NWBFile at `nwbfile_path` is overwritten if it exists. Default is False.
        stub_test : bool, optional
            If True, only a subset of the data is used for testing purposes. Default is False.
        stub_frames : int, optional
            .. deprecated:: February 2026
                Use `stub_samples` instead.
        stub_samples : int, default: 100
            The number of samples (frames) to use for testing.
        backend : {"hdf5", "zarr"}, optional
            The type of backend to use when writing the file.
        backend_configuration : HDF5BackendConfiguration or ZarrBackendConfiguration, optional
            The configuration model to use when configuring the datasets for this backend.
        """
        # Pack the direct kwargs into conversion_options and delegate to parent
        conversion_options = {"stub_test": stub_test, "stub_samples": stub_samples}
        if stub_frames is not None:
            conversion_options["stub_frames"] = stub_frames

        super().run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            backend=backend,
            backend_configuration=backend_configuration,
            conversion_options=conversion_options,
        )
