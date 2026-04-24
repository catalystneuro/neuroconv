import importlib
import json
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from jsonschema.validators import validate
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from .tools.nwb_helpers import (
    BACKEND_NWB_IO,
    HDF5BackendConfiguration,
    ZarrBackendConfiguration,
    configure_backend,
    get_default_backend_configuration,
    make_nwbfile_from_metadata,
)
from .tools.nwb_helpers._metadata_and_file_helpers import (
    _resolve_backend,
    configure_and_write_nwbfile,
)
from .utils import (
    get_json_schema_from_method_signature,
    load_dict_from_file,
)
from .utils.dict import DeepDict
from .utils.json_schema import _NWBMetaDataEncoder, _NWBSourceDataEncoder


class BaseDataInterface(ABC):
    """Abstract class defining the structure of all DataInterfaces."""

    display_name: str | None = None
    keywords: tuple[str] = tuple()
    associated_suffixes: tuple[str] = tuple()
    info: str | None = None

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Infer the JSON schema for the source_data from the method signature (annotation typing).

        Returns
        -------
        dict
            The JSON schema for the source_data.
        """
        return get_json_schema_from_method_signature(cls, exclude=["source_data"])

    @classmethod
    def validate_source(cls, source_data: dict, verbose: bool = False):
        """Validate source_data against Converter source_schema."""
        cls._validate_source_data(source_data=source_data, verbose=verbose)

    def _validate_source_data(self, source_data: dict, verbose: bool = False):

        encoder = _NWBSourceDataEncoder()
        # The encoder produces a serialized object, so we deserialized it for comparison

        serialized_source_data = encoder.encode(source_data)
        decoded_source_data = json.loads(serialized_source_data)
        source_schema = self.get_source_schema()
        validate(instance=decoded_source_data, schema=source_schema)
        if verbose:
            print("Source data is valid!")

    @validate_call
    def __init__(self, verbose: bool = False, **source_data):
        self.verbose = verbose
        self.source_data = source_data

    def get_metadata_schema(self) -> dict:
        """
        Retrieve JSON schema for metadata.

        Returns
        -------
        dict
            The JSON schema defining the metadata structure.
        """
        metadata_schema = load_dict_from_file(Path(__file__).parent / "schemas" / "base_metadata_schema.json")
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        """
        Child DataInterface classes should override this to match their metadata.

        Returns
        -------
        DeepDict
            The metadata dictionary containing basic NWBFile metadata.
        """
        metadata = DeepDict()
        metadata["NWBFile"]["session_description"] = ""
        metadata["NWBFile"]["identifier"] = str(uuid.uuid4())

        # Add NeuroConv watermark (overridden if going through the GUIDE)
        neuroconv_version = importlib.metadata.version("neuroconv")
        metadata["NWBFile"]["source_script"] = f"Created using NeuroConv v{neuroconv_version}"
        metadata["NWBFile"]["source_script_file_name"] = __file__  # Required for validation

        return metadata

    def validate_metadata(self, metadata: dict, append_mode: bool = False) -> None:
        """Validate the metadata against the schema."""
        encoder = _NWBMetaDataEncoder()
        # The encoder produces a serialized object, so we deserialized it for comparison

        serialized_metadata = encoder.encode(metadata)
        decoded_metadata = json.loads(serialized_metadata)
        metdata_schema = self.get_metadata_schema()
        if append_mode:
            # Eliminate required from NWBFile
            nwbfile_schema = metdata_schema["properties"]["NWBFile"]
            nwbfile_schema.pop("required", None)

        validate(instance=decoded_metadata, schema=metdata_schema)

    def get_conversion_options_schema(self) -> dict:
        """
        Infer the JSON schema for the conversion options from the method signature (annotation typing).

        Returns
        -------
        dict
            The JSON schema for the conversion options.
        """
        return get_json_schema_from_method_signature(self.add_to_nwbfile, exclude=["nwbfile", "metadata"])

    def create_nwbfile(self, metadata: dict | None = None, **conversion_options) -> NWBFile:
        """
        Create and return an in-memory pynwb.NWBFile object with this interface's data added to it.

        Parameters
        ----------
        metadata : dict, optional
            Metadata dictionary with information used to create the NWBFile.
        **conversion_options
            Additional keyword arguments to pass to the `.add_to_nwbfile` method.

        Returns
        -------
        nwbfile : pynwb.NWBFile
            The in-memory object with this interface's data added to it.
        """
        if metadata is None:
            metadata = self.get_metadata()

        nwbfile = make_nwbfile_from_metadata(metadata=metadata)
        self.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **conversion_options)

        return nwbfile

    @abstractmethod
    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None, **conversion_options) -> None:
        """
        Define a protocol for mapping the data from this interface to NWB neurodata objects.

        These neurodata objects should also be added to the in-memory pynwb.NWBFile object in this step.

        Parameters
        ----------
        nwbfile : pynwb.NWBFile
            The in-memory object to add the data to.
        metadata : dict
            Metadata dictionary with information used to create the NWBFile.
        **conversion_options
            Additional keyword arguments to pass to the `.add_to_nwbfile` method.
        """
        raise NotImplementedError

    def run_conversion(
        self,
        nwbfile_path: FilePath,
        nwbfile: NWBFile | None = None,
        metadata: dict | None = None,
        overwrite: bool = False,
        backend: Literal["hdf5", "zarr"] | None = None,
        backend_configuration: HDF5BackendConfiguration | ZarrBackendConfiguration | None = None,
        append_on_disk_nwbfile: bool = False,
        **conversion_options,
    ):
        """
        Run the NWB conversion for the instantiated data interface.

        Parameters
        ----------
        nwbfile_path : FilePath
            Path for where to write or load (if overwrite=False) the NWBFile.
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
        append_on_disk_nwbfile : bool, default: False
            Whether to append to an existing NWBFile on disk. If True, the `nwbfile` parameter must be None.
            This is useful for appending data to an existing file without overwriting it.
        """

        appending_to_in_memory_nwbfile = nwbfile is not None
        file_initially_exists = Path(nwbfile_path).exists() if nwbfile_path is not None else False
        allowed_to_modify_existing = overwrite or append_on_disk_nwbfile

        if file_initially_exists and not allowed_to_modify_existing:
            raise ValueError(
                f"The file at '{nwbfile_path}' already exists. Set overwrite=True to overwrite the existing file "
                "or append_on_disk_nwbfile=True to append to the existing file."
            )

        if append_on_disk_nwbfile and appending_to_in_memory_nwbfile:
            raise ValueError(
                "Cannot append to an existing file while also providing an in-memory NWBFile. "
                "Either set overwrite=True to replace the existing file, or remove the nwbfile parameter to append to the existing file on disk."
            )

        if metadata is None:
            metadata = self.get_metadata()
        self.validate_metadata(metadata=metadata, append_mode=append_on_disk_nwbfile)

        writing_new_file = not append_on_disk_nwbfile

        if writing_new_file:
            self._write_nwbfile(
                nwbfile_path=nwbfile_path,
                nwbfile=nwbfile,
                metadata=metadata,
                backend=backend,
                backend_configuration=backend_configuration,
                conversion_options=conversion_options,
            )
        else:
            self._append_nwbfile(
                nwbfile_path=nwbfile_path,
                metadata=metadata,
                backend=backend,
                backend_configuration=backend_configuration,
                conversion_options=conversion_options,
            )

    def _write_nwbfile(
        self,
        nwbfile_path: FilePath,
        nwbfile: NWBFile | None,
        metadata: dict,
        backend: Literal["hdf5", "zarr"],
        backend_configuration: dict,
        conversion_options: dict,
    ) -> None:
        """
        Write NWBFile to a file path on disk.

        Private helper method for run_conversion in write mode.
        Creates a new NWBFile or uses provided one, then writes to disk.
        """
        if nwbfile is not None:
            self.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **conversion_options)
        else:
            nwbfile = self.create_nwbfile(metadata=metadata, **conversion_options)

        configure_and_write_nwbfile(
            nwbfile=nwbfile,
            nwbfile_path=nwbfile_path,
            backend=backend,
            backend_configuration=backend_configuration,
        )

    def _append_nwbfile(
        self,
        nwbfile_path: FilePath,
        metadata: dict,
        backend: Literal["hdf5", "zarr"],
        backend_configuration: dict,
        conversion_options: dict,
    ) -> None:
        """
        Append data to an existing NWB file.

        Private helper method for run_conversion in append mode.
        Reads existing file, adds interface data, and writes back.
        """
        backend = _resolve_backend(backend, backend_configuration)
        IO = BACKEND_NWB_IO[backend]

        with IO(path=str(nwbfile_path), mode="r+", load_namespaces=True) as io:
            nwbfile = io.read()

            self.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **conversion_options)

            if backend_configuration is None:
                backend_configuration = self.get_default_backend_configuration(nwbfile=nwbfile, backend=backend)

            configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

            io.write(nwbfile)

    @staticmethod
    def get_default_backend_configuration(
        nwbfile: NWBFile,
        backend: Literal["hdf5", "zarr"] = "hdf5",
    ) -> HDF5BackendConfiguration | ZarrBackendConfiguration:
        """
        Fill and return a default backend configuration to serve as a starting point for further customization.

        Parameters
        ----------
        nwbfile : pynwb.NWBFile
            The in-memory object with this interface's data already added to it.
        backend : "hdf5", default: "hdf5"
            The type of backend to use when creating the file.
            Additional backend types will be added soon.

        Returns
        -------
        HDF5BackendConfiguration | ZarrBackendConfiguration
            The default configuration for the specified backend type.
        """
        return get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
