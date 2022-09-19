"""Authors: Cody Baker and Ben Dichter."""
import json
from jsonschema import validate
from typing import Optional, Dict
from pathlib import Path

from pynwb import NWBFile
from pynwb.file import Subject

from .tools.nwb_helpers import get_default_nwbfile_metadata, make_nwbfile_from_metadata, make_or_load_nwbfile
from .utils import (
    get_schema_from_hdmf_class,
    get_schema_for_NWBFile,
    dict_deep_update,
    get_base_schema,
    unroot_schema,
    fill_defaults,
)

from .utils.json_schema import NWBMetaDataEncoder


class NWBConverter:
    """Primary class for all NWB conversion classes."""

    data_interface_classes = None

    @classmethod
    def get_source_schema(cls):
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

    @classmethod
    def get_conversion_options_schema(cls):
        """Compile conversion option schemas from each of the data interface classes."""
        conversion_options_schema = get_base_schema(
            root=True,
            id_="conversion_options.schema.json",
            title="Conversion options schema",
            description="Schema for the conversion options",
            version="0.1.0",
        )
        for interface_name, data_interface in cls.data_interface_classes.items():
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

    def get_metadata_schema(self):
        """Compile metadata schemas from each of the data interface objects."""
        metadata_schema = get_base_schema(
            id_="metadata.schema.json",
            root=True,
            title="Metadata",
            description="Schema for the metadata",
            version="0.1.0",
            required=["NWBFile"],
            properties=dict(NWBFile=get_schema_for_NWBFile(), Subject=get_schema_from_hdmf_class(Subject)),
        )
        for data_interface in self.data_interface_objects.values():
            interface_schema = unroot_schema(data_interface.get_metadata_schema())
            metadata_schema = dict_deep_update(metadata_schema, interface_schema)

        default_values = self.get_metadata()
        fill_defaults(metadata_schema, default_values)
        return metadata_schema

    def get_metadata(self):
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        metadata = get_default_nwbfile_metadata()
        for interface in self.data_interface_objects.values():
            interface_metadata = interface.get_metadata()
            metadata = dict_deep_update(metadata, interface_metadata)
        return metadata

    def get_conversion_options(self):
        """Auto-fill as much of the conversion options as possible. Must comply with conversion_options_schema."""
        conversion_options = dict()
        for interface_name, interface in self.data_interface_objects.items():
            conversion_options[interface_name] = interface.get_conversion_options()
        return conversion_options

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
        validate(instance=conversion_options, schema=self.get_conversion_options_schema())
        if self.verbose:
            print("conversion_options is valid!")

    def _validate_source_data(self, source_data: Dict[str, dict], verbose: bool = True):
        validate(instance=source_data, schema=self.get_source_schema())
        if verbose:
            print("Source data is valid!")

    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        conversion_options: Optional[dict] = None,
    ) -> NWBFile:
        """
        Run the NWB conversion over all the instantiated data interfaces.

        Parameters
        ----------
        nwbfile_path: FilePathType
            Path for where to write or load (if overwrite=False) the NWBFile.
            If specified, the context will always write to this location.
        nwbfile: NWBFile, optional
            An in-memory NWBFile object to write to the location.
        metadata: dict, optional
            Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
        overwrite: bool, optional
            Whether or not to overwrite the NWBFile if one exists at the nwbfile_path.
            The default is False (append mode).
        verbose: bool, optional
            If 'nwbfile_path' is specified, informs user after a successful write operation.
            The default is True.
        conversion_options: dict, optional
            Similar to source_data, a dictionary containing keywords for each interface for which non-default
            conversion specification is requested.

        Returns
        -------
        nwbfile: NWBFile
            The in-memory NWBFile object after all conversion operations are complete.
        """
        if metadata is None:
            metadata = self.get_metadata()
        self.validate_metadata(metadata=metadata)

        if conversion_options is None:
            conversion_options = dict()
        default_conversion_options = self.get_conversion_options()
        conversion_options_to_run = dict_deep_update(default_conversion_options, conversion_options)
        self.validate_conversion_options(conversion_options=conversion_options_to_run)

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
        ) as nwbfile_out:

            for interface_name, data_interface in self.data_interface_objects.items():
                data_interface.run_conversion(
                    nwbfile=nwbfile_out, metadata=metadata, **conversion_options_to_run.get(interface_name, dict())
                )

        return nwbfile_out
