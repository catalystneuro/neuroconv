"""Contains core class definitions for the NWBConverter and ConverterPipe."""

import inspect
import json
from collections import Counter
from pathlib import Path
from typing import Literal, Optional, Type, Union

from jsonschema import validate
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from .basedatainterface import BaseDataInterface
from .tools.nwb_helpers import (
    HDF5BackendConfiguration,
    ZarrBackendConfiguration,
    configure_and_write_nwbfile,
    configure_backend,
    get_default_backend_configuration,
    get_default_nwbfile_metadata,
    make_nwbfile_from_metadata,
    make_or_load_nwbfile,
)
from .tools.nwb_helpers._metadata_and_file_helpers import _resolve_backend
from .utils import (
    dict_deep_update,
    fill_defaults,
    get_base_schema,
    load_dict_from_file,
    unroot_schema,
)
from .utils.dict import DeepDict
from .utils.json_schema import (
    _NWBConversionOptionsEncoder,
    _NWBMetaDataEncoder,
    _NWBSourceDataEncoder,
)


class NWBConverter:
    """Primary class for all NWB conversion classes."""

    display_name: Union[str, None] = None
    keywords: tuple[str] = tuple()
    associated_suffixes: tuple[str] = tuple()
    info: Union[str, None] = None

    data_interface_classes: dict[str, Type[BaseDataInterface]] = {}

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Compile input schemas from each of the data interface classes.

        Returns
        -------
        dict
            The compiled source schema from all data interface classes.
        """
        source_schema = get_base_schema(
            root=True,
            id_="source.schema.json",
            title="Source data schema",
            description="Schema for the source data, files and directories",
            version="0.1.0",
        )
        for interface_name, data_interface in cls.data_interface_classes.items():
            source_schema["properties"].update({interface_name: unroot_schema(data_interface.get_source_schema())})
        return source_schema

    @classmethod
    def validate_source(cls, source_data: dict[str, dict], verbose: bool = False):
        """Validate source_data against Converter source_schema."""
        cls._validate_source_data(source_data=source_data, verbose=verbose)

    def _validate_source_data(self, source_data: dict[str, dict], verbose: bool = False):

        # We do this to ensure that python objects are in string format for the JSON schema
        encoder = _NWBSourceDataEncoder()
        encoded_source_data = encoder.encode(source_data)
        decoded_source_data = json.loads(encoded_source_data)

        validate(instance=decoded_source_data, schema=self.get_source_schema())
        if verbose:
            print("Source data is valid!")

    @validate_call
    def __init__(self, source_data: dict[str, dict], verbose: bool = False):
        """
        Initialize an NWBConverter instance by validating the provided source data and
        dynamically instantiating the data interfaces on the source_data dictionary.

        Parameters
        ----------
        source_data : dict[str, dict]
            A dictionary where keys are interface names and values are the corresponding
            parameters required to initialize each data interface.
        verbose : bool, optional
            If True, enables verbose mode, by default False.
            This is propagated to the data interfaces.

        """
        self.verbose = verbose

        # Only initialize interfaces that are present in the source_data dictionary.
        # This enables the NWBConverter class to flexibly handle multi-session scenarios
        # by dynamically selecting only the interface names that are present in the source_data.
        available_interfaces = {name: cls for name, cls in self.data_interface_classes.items() if name in source_data}

        self.data_interface_objects: dict[str, BaseDataInterface] = {}
        for interface_name, interface_class in available_interfaces.items():
            interface_kwargs = source_data[interface_name]

            # Pass the verbose argument if the interface's constructor supports it.
            if "verbose" in inspect.signature(interface_class.__init__).parameters:
                interface_kwargs["verbose"] = verbose

            interface_instance = interface_class(**interface_kwargs)
            self.data_interface_objects[interface_name] = interface_instance

    def get_metadata_schema(self) -> dict:
        """
        Compile metadata schemas from each of the data interface objects.

        Returns
        -------
        dict
            The compiled metadata schema from all data interface objects.
        """
        metadata_schema = load_dict_from_file(Path(__file__).parent / "schemas" / "base_metadata_schema.json")
        for data_interface in self.data_interface_objects.values():
            interface_schema = unroot_schema(data_interface.get_metadata_schema())
            metadata_schema = dict_deep_update(metadata_schema, interface_schema)

        default_values = self.get_metadata()
        fill_defaults(metadata_schema, default_values)
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        """
        Auto-fill as much of the metadata as possible. Must comply with metadata schema.

        Returns
        -------
        DeepDict
            The metadata dictionary containing auto-filled metadata from all interfaces.
        """
        metadata = get_default_nwbfile_metadata()
        for interface in self.data_interface_objects.values():
            interface_metadata = interface.get_metadata()
            metadata = dict_deep_update(metadata, interface_metadata)
        return metadata

    def validate_metadata(self, metadata: dict[str, dict], append_mode: bool = False):
        """Validate metadata against Converter metadata_schema."""
        encoder = _NWBMetaDataEncoder()

        # We do this to ensure that python objects are in string format for the JSON schema
        encoded_metadta = encoder.encode(metadata)
        decoded_metadata = json.loads(encoded_metadta)

        metadata_schema = self.get_metadata_schema()
        if append_mode:
            # Eliminate required from NWBFile
            nwbfile_schema = metadata_schema["properties"]["NWBFile"]
            nwbfile_schema.pop("required", None)

        validate(instance=decoded_metadata, schema=metadata_schema)
        if self.verbose:
            print("Metadata is valid!")

    def get_conversion_options_schema(self) -> dict:
        """
        Compile conversion option schemas from each of the data interface classes.

        Returns
        -------
        dict
            The compiled conversion options schema from all data interface classes.
        """
        conversion_options_schema = get_base_schema(
            root=True,
            id_="conversion_options.schema.json",
            title="Conversion options schema",
            description="Schema for the conversion options",
            version="0.1.0",
        )
        for interface_name, data_interface in self.data_interface_objects.items():
            conversion_options_schema["properties"].update(
                {interface_name: unroot_schema(data_interface.get_conversion_options_schema())}
            )

        return conversion_options_schema

    def validate_conversion_options(self, conversion_options: dict[str, dict]):
        """Validate conversion_options against Converter conversion_options_schema."""

        conversion_options = conversion_options or dict()

        # We do this to ensure that python objects are in string format for the JSON schema
        encoded_conversion_options = _NWBConversionOptionsEncoder().encode(conversion_options)
        decoded_conversion_options = json.loads(encoded_conversion_options)

        validate(instance=decoded_conversion_options, schema=self.get_conversion_options_schema())
        if self.verbose:
            print("conversion_options is valid!")

    def create_nwbfile(self, metadata: Optional[dict] = None, conversion_options: Optional[dict] = None) -> NWBFile:
        """
        Create and return an in-memory pynwb.NWBFile object with the conversion data added to it.

        Parameters
        ----------
        metadata : dict, optional
            Metadata dictionary with information used to create the NWBFile.
        conversion_options : dict, optional
            Similar to source_data, a dictionary containing keywords for each interface for which non-default
            conversion specification is requested.

        Returns
        -------
        nwbfile : pynwb.NWBFile
            The in-memory object with this interface's data added to it.
        """
        if metadata is None:
            metadata = self.get_metadata()

        nwbfile = make_nwbfile_from_metadata(metadata=metadata)
        self.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)
        return nwbfile

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata, conversion_options: Optional[dict] = None):
        """
        Add data from the instantiated data interfaces to the given NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file object to which the data from the data interfaces will be added.
        metadata : dict
            The metadata dictionary that contains information used to describe the data.
        conversion_options : dict, optional
            A dictionary containing conversion options for each interface, where non-default behavior is requested.
            Each key corresponds to a data interface name, and the values are dictionaries with options for that interface.
            By default, None.
        """
        conversion_options = conversion_options or dict()
        for interface_name, data_interface in self.data_interface_objects.items():
            data_interface.add_to_nwbfile(
                nwbfile=nwbfile, metadata=metadata, **conversion_options.get(interface_name, dict())
            )

    def run_conversion(
        self,
        nwbfile_path: FilePath,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        backend: Optional[Literal["hdf5", "zarr"]] = None,
        backend_configuration: Optional[Union[HDF5BackendConfiguration, ZarrBackendConfiguration]] = None,
        conversion_options: Optional[dict] = None,
        append_on_disk_nwbfile: bool = False,
    ) -> None:
        """
        Run the NWB conversion over all the instantiated data interfaces.

        Parameters
        ----------
        nwbfile_path : FilePath
            Path for where to write or load (if overwrite=False) the NWBFile.
            If specified, the context will always write to this location.
        nwbfile : NWBFile, optional
            An in-memory NWBFile object to write to the location.
        metadata : dict, optional
            Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
        overwrite : bool, default: False
            Whether to overwrite the NWBFile if one exists at the nwbfile_path.
            The default is False (append mode).
        backend : {"hdf5", "zarr"}, optional
            The type of backend to use when writing the file.
            If a `backend_configuration` is not specified, the default type will be "hdf5".
            If a `backend_configuration` is specified, then the type will be auto-detected.
        backend_configuration : HDF5BackendConfiguration or ZarrBackendConfiguration, optional
            The configuration model to use when configuring the datasets for this backend.
            To customize, call the `.get_default_backend_configuration(...)` method, modify the returned
            BackendConfiguration object, and pass that instead.
            Otherwise, all datasets will use default configuration settings.
        conversion_options : dict, optional
            Similar to source_data, a dictionary containing keywords for each interface for which non-default
            conversion specification is requested.
        append_on_disk_nwbfile : bool, default: False
            Whether to append to an existing NWBFile on disk. If True, the `nwbfile` parameter must be None.
            This is useful for appending data to an existing file without overwriting it.
        """

        appending_to_in_memory_nwbfile = nwbfile is not None
        file_initially_exists = Path(nwbfile_path).exists() if nwbfile_path is not None else False

        if file_initially_exists and not overwrite:
            raise ValueError(
                f"The file at {nwbfile_path} already exists. Set overwrite=True to overwrite the existing file."
            )

        if append_on_disk_nwbfile and appending_to_in_memory_nwbfile:
            raise ValueError(
                "Cannot append to an existing file while also providing an in-memory NWBFile. "
                "Either set overwrite=True to replace the existing file, or remove the nwbfile parameter to append to the existing file on disk."
            )

        if metadata is None:
            metadata = self.get_metadata()

        self.validate_metadata(metadata=metadata, append_mode=append_on_disk_nwbfile)
        self.validate_conversion_options(conversion_options=conversion_options)
        self.temporally_align_data_interfaces(metadata=metadata, conversion_options=conversion_options)

        if not append_on_disk_nwbfile:

            if appending_to_in_memory_nwbfile:
                self.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)
            else:
                nwbfile = self.create_nwbfile(metadata=metadata, conversion_options=conversion_options)

            configure_and_write_nwbfile(
                nwbfile=nwbfile,
                nwbfile_path=nwbfile_path,
                backend=backend,
                backend_configuration=backend_configuration,
            )

        else:  # We are only using the context in append mode, see issue #1143

            backend = _resolve_backend(backend, backend_configuration)
            with make_or_load_nwbfile(
                nwbfile_path=nwbfile_path,
                nwbfile=nwbfile,
                metadata=metadata,
                overwrite=overwrite,
                backend=backend,
                verbose=getattr(self, "verbose", False),
            ) as nwbfile_out:
                self.add_to_nwbfile(nwbfile=nwbfile_out, metadata=metadata, conversion_options=conversion_options)

                if backend_configuration is None:
                    backend_configuration = self.get_default_backend_configuration(nwbfile=nwbfile_out, backend=backend)

                configure_backend(nwbfile=nwbfile_out, backend_configuration=backend_configuration)

    def temporally_align_data_interfaces(
        self, metadata: Optional[dict] = None, conversion_options: Optional[dict] = None
    ):
        """Override this method to implement custom alignment."""
        pass

    @staticmethod
    def get_default_backend_configuration(
        nwbfile: NWBFile,
        backend: Literal["hdf5", "zarr"] = "hdf5",
    ) -> Union[HDF5BackendConfiguration, ZarrBackendConfiguration]:
        """
        Fill and return a default backend configuration to serve as a starting point for further customization.

        Parameters
        ----------
        nwbfile : pynwb.NWBFile
            The in-memory object with this interface's data already added to it.
        backend : "hdf5" or "zarr", default: "hdf5"
            The type of backend to use when creating the file.

        Returns
        -------
        Union[HDF5BackendConfiguration, ZarrBackendConfiguration]
            The default configuration for the specified backend type.
        """
        return get_default_backend_configuration(nwbfile=nwbfile, backend=backend)


class ConverterPipe(NWBConverter):
    """Takes a list or dict of pre-initialized interfaces as arguments to build an NWBConverter class."""

    @classmethod
    def get_source_schema(cls) -> dict:
        raise NotImplementedError("Source data not available with previously initialized classes.")

    @classmethod
    def validate_source(cls):
        raise NotImplementedError("Source data not available with previously initialized classes.")

    def __init__(self, data_interfaces: Union[list[BaseDataInterface], dict[str, BaseDataInterface]], verbose=False):
        self.verbose = verbose
        if isinstance(data_interfaces, list):
            # Create unique names for each interface
            counter = {interface.__class__.__name__: 0 for interface in data_interfaces}
            total_counts = Counter([interface.__class__.__name__ for interface in data_interfaces])
            self.data_interface_objects = dict()
            for interface in data_interfaces:
                class_name = interface.__class__.__name__
                counter[class_name] += 1
                unique_signature = f"{counter[class_name]:03}" if total_counts[class_name] > 1 else ""
                interface_name = f"{class_name}{unique_signature}"
                self.data_interface_objects[interface_name] = interface
        elif isinstance(data_interfaces, dict):
            self.data_interface_objects = data_interfaces

        self.data_interface_classes = {
            name: interface.__class__ for name, interface in self.data_interface_objects.items()
        }

    def get_conversion_options_schema(self) -> dict:
        """
        Compile conversion option schemas from each of the data interface classes.

        Returns
        -------
        dict
            The compiled conversion options schema containing:
            - root: True
            - id: "conversion_options.schema.json"
            - title: "Conversion options schema"
            - description: "Schema for the conversion options"
            - version: "0.1.0"
            - properties: Dictionary mapping interface names to their unrooted schemas
        """
        conversion_options_schema = get_base_schema(
            root=True,
            id_="conversion_options.schema.json",
            title="Conversion options schema",
            description="Schema for the conversion options",
            version="0.1.0",
        )
        for interface_name, data_interface in self.data_interface_objects.items():

            schema = data_interface.get_conversion_options_schema()
            conversion_options_schema["properties"].update({interface_name: unroot_schema(schema)})
        return conversion_options_schema
