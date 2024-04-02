import json
import uuid
import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal, Optional, Tuple, Union

from jsonschema.validators import validate
from pynwb import NWBFile

from .tools.nwb_helpers import (
    HDF5BackendConfiguration,
    ZarrBackendConfiguration,
    configure_backend,
    get_default_backend_configuration,
    make_nwbfile_from_metadata,
    make_or_load_nwbfile,
)
from .utils import (
    NWBMetaDataEncoder,
    get_schema_from_method_signature,
    load_dict_from_file,
)
from .utils.dict import DeepDict


class BaseDataInterface(ABC):
    """Abstract class defining the structure of all DataInterfaces."""

    display_name: Union[str, None] = None
    keywords: Tuple[str] = tuple()
    associated_suffixes: Tuple[str] = tuple()
    info: Union[str, None] = None

    @classmethod
    def get_source_schema(cls) -> dict:
        """Infer the JSON schema for the source_data from the method signature (annotation typing)."""
        return get_schema_from_method_signature(cls, exclude=["source_data"])

    def __init__(self, verbose: bool = False, **source_data):
        self.verbose = verbose
        self.source_data = source_data

    def get_conversion_options_schema(self) -> dict:
        """Infer the JSON schema for the conversion options from the method signature (annotation typing)."""
        return get_schema_from_method_signature(self.add_to_nwbfile, exclude=["nwbfile", "metadata"])

    def get_metadata_schema(self) -> dict:
        """Retrieve JSON schema for metadata."""
        metadata_schema = load_dict_from_file(Path(__file__).parent / "schemas" / "base_metadata_schema.json")
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        """Child DataInterface classes should override this to match their metadata."""
        metadata = DeepDict()
        metadata["NWBFile"]["session_description"] = "Auto-generated by neuroconv"
        metadata["NWBFile"]["identifier"] = str(uuid.uuid4())

        return metadata

    def validate_metadata(self, metadata: dict) -> None:
        """Validate the metadata against the schema."""
        encoder = NWBMetaDataEncoder()
        # The encoder produces a serialized object, so we deserialized it for comparison

        serialized_metadata = encoder.encode(metadata)
        decoded_metadata = json.loads(serialized_metadata)
        validate(instance=decoded_metadata, schema=self.get_metadata_schema())

    def get_default_backend_configuration(
        self,
        backend: Literal["hdf5", "zarr"] = "hdf5",
        metadata: Optional[dict] = None,
        conversion_options: Optional[dict] = None,
    ) -> Union[HDF5BackendConfiguration, ZarrBackendConfiguration]:
        """
        Fill and return a default backend configuration to serve as a starting point for further customization.

        Parameters
        ----------
        backend : "hdf5" or "zarr", default: "hdf5"
            The type of backend used to create the file.
        metadata : dict, optional
            Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
        conversion_options : dict, optional
            Similar to source_data, a dictionary containing keywords for each interface for which non-default
            conversion specification is requested.
        """
        if metadata is None:
            metadata = self.get_metadata()
        if conversion_options is None:
            conversion_options = dict()

        with make_or_load_nwbfile(metadata=metadata, verbose=self.verbose) as nwbfile:
            self.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **conversion_options)
            return get_default_backend_configuration(nwbfile=nwbfile, backend=backend)

    def create_nwbfile(self, metadata=None, **conversion_options) -> NWBFile:
        nwbfile = make_nwbfile_from_metadata(metadata)
        self.add_to_nwbfile(nwbfile, metadata=metadata, **conversion_options)
        return nwbfile

    @abstractmethod
    def add_to_nwbfile(self, nwbfile: NWBFile, **conversion_options) -> None:
        raise NotImplementedError

    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        backend: Union[Literal["hdf5", "zarr"], HDF5BackendConfiguration, ZarrBackendConfiguration] = "hdf5",
        **conversion_options,
    ):
        """
        Run the NWB conversion for the instantiated data interface.

        Parameters
        ----------
        nwbfile_path : FilePathType
            Path for where to write or load (if overwrite=False) the NWBFile.
            If specified, the context will always write to this location.
        nwbfile : NWBFile, optional
            An in-memory NWBFile object to write to the location.
        metadata : dict, optional
            Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
        overwrite : bool, default: False
            Whether to overwrite the NWBFile if one exists at the nwbfile_path.
            The default is False (append mode).
        backend : "hdf5", "zarr", a HDF5BackendConfiguration, or a ZarrBackendConfiguration, default: "hdf5"
            If "hdf5" or "zarr", this type of backend will be used to create the file,
            with all datasets using the default values.
            To customize, call the `.get_default_backend_configuration(...)` method, modify the returned
            BackendConfiguration object, and pass that instead.
        """
        if nwbfile_path is None:
            warnings.warn(  # TODO: remove on or after 6/21/2024
                "Using DataInterface.run_conversion without specifying nwbfile_path is deprecated. To create an "
                "NWBFile object in memory, use DataInterface.create_nwbfile. To append to an existing NWBFile object,"
                " use DataInterface.add_to_nwbfile."
            )

        if metadata is None:
            metadata = self.get_metadata()

        if isinstance(backend, str):
            backend_configuration = self.get_default_backend_configuration(
                backend=backend, metadata=metadata, conversion_options=conversion_options
            )
            print(backend_configuration)
        else:
            backend_configuration = backend

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            backend=backend,
            verbose=getattr(self, "verbose", False),
        ) as nwbfile_out:
            self.add_to_nwbfile(nwbfile_out, metadata=metadata, **conversion_options)
            configure_backend(nwbfile=nwbfile_out, backend_configuration=backend_configuration)
