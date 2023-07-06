import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Union

from jsonschema import validate
from pynwb import NWBFile

from .basedatainterface import BaseDataInterface
from .tools.nwb_helpers import get_default_nwbfile_metadata, make_or_load_nwbfile
from .utils import (
    dict_deep_update,
    fill_defaults,
    get_base_schema,
    load_dict_from_file,
    unroot_schema,
)
from .utils.dict import DeepDict
from .utils.json_schema import NWBMetaDataEncoder


class NWBConverter:
    """Primary class for all NWB conversion classes."""

    data_interface_classes = None

    @classmethod
    def get_source_schema(cls) -> dict:
        """Compile input schemas from each of the data interface classes."""
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

    def get_conversion_options_schema(self) -> dict:
        """Compile conversion option schemas from each of the data interface classes."""
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

    @classmethod
    def validate_source(cls, source_data: Dict[str, dict], verbose: bool = True):
        """Validate source_data against Converter source_schema."""
        cls._validate_source_data(source_data=source_data, verbose=verbose)

    def __init__(self, source_data: Dict[str, dict], verbose: bool = True):
        """Validate source_data against source_schema and initialize all data interfaces."""
        self.verbose = verbose
        self._validate_source_data(source_data=source_data, verbose=self.verbose)
        self.data_interface_objects = {
            name: data_interface(**source_data[name])
            for name, data_interface in self.data_interface_classes.items()
            if name in source_data
        }

    def get_metadata_schema(self) -> dict:
        """Compile metadata schemas from each of the data interface objects."""
        metadata_schema = load_dict_from_file(Path(__file__).parent / "schemas" / "base_metadata_schema.json")
        for data_interface in self.data_interface_objects.values():
            interface_schema = unroot_schema(data_interface.get_metadata_schema())
            metadata_schema = dict_deep_update(metadata_schema, interface_schema)

        default_values = self.get_metadata()
        fill_defaults(metadata_schema, default_values)
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        metadata = get_default_nwbfile_metadata()
        for interface in self.data_interface_objects.values():
            interface_metadata = interface.get_metadata()
            metadata = dict_deep_update(metadata, interface_metadata)
        return metadata

    def validate_metadata(self, metadata: Dict[str, dict]):
        """Validate metadata against Converter metadata_schema."""
        encoder = NWBMetaDataEncoder()
        # The encoder produces a serialiazed object so we de serialized it for comparison
        serialized_metadata = encoder.encode(metadata)
        decoded_metadata = json.loads(serialized_metadata)
        validate(instance=decoded_metadata, schema=self.get_metadata_schema())
        if self.verbose:
            print("Metadata is valid!")

    def validate_conversion_options(self, conversion_options: Dict[str, dict]):
        """Validate conversion_options against Converter conversion_options_schema."""
        validate(instance=conversion_options or {}, schema=self.get_conversion_options_schema())
        if self.verbose:
            print("conversion_options is valid!")

    def _validate_source_data(self, source_data: Dict[str, dict], verbose: bool = True):
        validate(instance=source_data, schema=self.get_source_schema())
        if verbose:
            print("Source data is valid!")

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata, conversion_options: Optional[dict] = None) -> None:
        conversion_options = conversion_options or dict()
        for interface_name, data_interface in self.data_interface_objects.items():
            data_interface.add_to_nwbfile(
                nwbfile=nwbfile, metadata=metadata, **conversion_options.get(interface_name, dict())
            )

    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        conversion_options: Optional[dict] = None,
    ) -> None:
        """
        Run the NWB conversion over all the instantiated data interfaces.
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
        conversion_options : dict, optional
            Similar to source_data, a dictionary containing keywords for each interface for which non-default
            conversion specification is requested.
        """
        if metadata is None:
            metadata = self.get_metadata()

        self.validate_metadata(metadata=metadata)

        self.validate_conversion_options(conversion_options=conversion_options)

        self.temporally_align_data_interfaces()

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
        ) as nwbfile_out:
            self.add_to_nwbfile(nwbfile_out, metadata, conversion_options)

    def temporally_align_data_interfaces(self):
        """Override this method to implement custom alignment"""
        pass


class ConverterPipe(NWBConverter):
    """Takes a list or dict of pre-initialized interfaces as arguments to build an NWBConverter class"""

    def get_conversion_options_schema(self) -> dict:
        """Compile conversion option schemas from each of the data interface classes."""
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

    def get_source_schema(self) -> dict:
        raise NotImplementedError("Source data not available with previously initialized classes")

    def validate_source(self):
        raise NotImplementedError("Source data not available with previously initialized classes")

    def __init__(self, data_interfaces: Union[List[BaseDataInterface], Dict[str, BaseDataInterface]], verbose=True):
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
