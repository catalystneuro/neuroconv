import importlib
import json
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal, Optional, Union

from jsonschema.validators import validate
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from .tools.nwb_helpers import (
    HDF5BackendConfiguration,
    ZarrBackendConfiguration,
    configure_backend,
    get_default_backend_configuration,
    make_nwbfile_from_metadata,
    make_or_load_nwbfile,
)
from .tools.nwb_helpers._metadata_and_file_helpers import _resolve_backend
from .utils import (
    _NWBMetaDataEncoder,
    get_json_schema_from_method_signature,
    load_dict_from_file,
)
from .utils.dict import DeepDict


class BaseDataInterface(ABC):
    """Abstract class defining the structure of all DataInterfaces."""

    display_name: Union[str, None] = None
    keywords: tuple[str] = tuple()
    associated_suffixes: tuple[str] = tuple()
    info: Union[str, None] = None

    @classmethod
    def get_source_schema(cls) -> dict:
        """Infer the JSON schema for the source_data from the method signature (annotation typing)."""
        return get_json_schema_from_method_signature(cls, exclude=["source_data"])

    @validate_call
    def __init__(self, verbose: bool = False, **source_data):
        self.verbose = verbose
        self.source_data = source_data

    def get_metadata_schema(self) -> dict:
        """Retrieve JSON schema for metadata."""
        metadata_schema = load_dict_from_file(Path(__file__).parent / "schemas" / "base_metadata_schema.json")
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        """Child DataInterface classes should override this to match their metadata."""
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
        """Infer the JSON schema for the conversion options from the method signature (annotation typing)."""
        return get_json_schema_from_method_signature(self.add_to_nwbfile, exclude=["nwbfile", "metadata"])

    def create_nwbfile(self, metadata: Optional[dict] = None, **conversion_options) -> NWBFile:
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
    def add_to_nwbfile(self, nwbfile: NWBFile, **conversion_options) -> None:
        """
        Define a protocol for mapping the data from this interface to NWB neurodata objects.

        These neurodata objects should also be added to the in-memory pynwb.NWBFile object in this step.

        Parameters
        ----------
        nwbfile : pynwb.NWBFile
            The in-memory object to add the data to.
        **conversion_options
            Additional keyword arguments to pass to the `.add_to_nwbfile` method.
        """
        raise NotImplementedError

    def run_conversion(
        self,
        nwbfile_path: FilePath,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        backend: Optional[Literal["hdf5", "zarr"]] = None,
        backend_configuration: Optional[Union[HDF5BackendConfiguration, ZarrBackendConfiguration]] = None,
        **conversion_options,
    ):
        """
        Run the NWB conversion for the instantiated data interface.

        Parameters
        ----------
        nwbfile_path : FilePathType
            Path for where the data will be written or appended.
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
        """

        backend = _resolve_backend(backend, backend_configuration)
        no_nwbfile_provided = nwbfile is None  # Otherwise, variable reference may mutate later on inside the context

        if metadata is None:
            metadata = self.get_metadata()

        file_initially_exists = Path(nwbfile_path).exists() if nwbfile_path is not None else False
        append_mode = file_initially_exists and not overwrite

        self.validate_metadata(metadata=metadata, append_mode=append_mode)

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            backend=backend,
            verbose=getattr(self, "verbose", False),
        ) as nwbfile_out:
            if no_nwbfile_provided:
                self.add_to_nwbfile(nwbfile=nwbfile_out, metadata=metadata, **conversion_options)

            if backend_configuration is None:
                backend_configuration = self.get_default_backend_configuration(nwbfile=nwbfile_out, backend=backend)

            configure_backend(nwbfile=nwbfile_out, backend_configuration=backend_configuration)

    @staticmethod
    def get_default_backend_configuration(
        nwbfile: NWBFile,
        # TODO: when all H5DataIO prewraps are gone, introduce Zarr safely
        # backend: Union[Literal["hdf5", "zarr"]],
        backend: Literal["hdf5"] = "hdf5",
    ) -> Union[HDF5BackendConfiguration, ZarrBackendConfiguration]:
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
        backend_configuration : HDF5BackendConfiguration or ZarrBackendConfiguration
            The default configuration for the specified backend type.
        """
        return get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
