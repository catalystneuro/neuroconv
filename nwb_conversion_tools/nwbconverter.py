"""Authors: Cody Baker and Ben Dichter."""
from jsonschema import validate
from pathlib import Path
from typing import Optional

from pynwb import NWBHDF5IO, NWBFile
from pynwb.file import Subject

from .utils.conversion_tools import get_default_nwbfile_metadata, make_nwbfile_from_metadata
from .utils.json_schema import (
    get_schema_from_hdmf_class,
    get_schema_for_NWBFile,
    dict_deep_update,
    get_base_schema,
    fill_defaults,
    unroot_schema,
)


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
    def validate_source(cls, source_data):
        """Validate source_data against Converter source_schema."""
        validate(instance=source_data, schema=cls.get_source_schema())
        print("Source data is valid!")

    def __init__(self, source_data):
        """Validate source_data against source_schema and initialize all data interfaces."""
        self.validate_source(source_data=source_data)
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

        fill_defaults(metadata_schema, self.get_metadata())
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

    def validate_metadata(self, metadata):
        """Validate metadata against Converter metadata_schema."""
        validate(instance=metadata, schema=self.get_metadata_schema())
        print("Metadata is valid!")

    def validate_conversion_options(self, conversion_options):
        """Validate conversion_options against Converter conversion_options_schema."""
        validate(instance=conversion_options, schema=self.get_conversion_options_schema())
        print("conversion_options is valid!")

    def run_conversion(
        self,
        metadata: Optional[dict] = None,
        save_to_file: Optional[bool] = True,
        nwbfile_path: Optional[str] = None,
        overwrite: Optional[bool] = False,
        nwbfile: Optional[NWBFile] = None,
        conversion_options: Optional[dict] = None,
    ):
        """
        Run the NWB conversion over all the instantiated data interfaces.

        Parameters
        ----------
        metadata : dict, optional
        save_to_file : bool, optional
            If False, returns an NWBFile object instead of writing it to the nwbfile_path. The default is True.
        nwbfile_path : str, optional
            Location to save the NWBFile, if save_to_file is True. The default is None.
        overwrite : bool, optional
            If True, replaces any existing NWBFile at the nwbfile_path location, if save_to_file is True.
            If False, appends the existing NWBFile at the nwbfile_path location, if save_to_file is True.
            The default is False.
        nwbfile : NWBFile, optional
            A pre-existing NWBFile object to be appended (instead of reading from nwbfile_path).
        conversion_options : dict, optional
            Similar to source_data, a dictionary containing keywords for each interface for which non-default
            conversion specification is requested.
        """
        assert (
            not save_to_file and nwbfile_path is None
        ) or nwbfile is None, (
            "Either pass a nwbfile_path location with save_to_file=True, or a nwbfile object, but not both!"
        )

        if metadata is None:
            metadata = self.get_metadata()
        if conversion_options is None:
            conversion_options = self.get_conversion_options()

        self.validate_metadata(metadata=metadata)
        self.validate_conversion_options(conversion_options=conversion_options)
        if save_to_file:
            load_kwargs = dict(path=nwbfile_path)
            if nwbfile_path is None:
                raise TypeError("A path to the output file must be provided, but nwbfile_path got value None")

            if Path(nwbfile_path).is_file() and not overwrite:
                load_kwargs.update(mode="r+", load_namespaces=True)
            else:
                load_kwargs.update(mode="w")

            with NWBHDF5IO(**load_kwargs) as io:
                if load_kwargs["mode"] == "r+":
                    nwbfile = io.read()
                elif nwbfile is None:
                    nwbfile = make_nwbfile_from_metadata(metadata=metadata)

                for interface_name, data_interface in self.data_interface_objects.items():
                    data_interface.run_conversion(nwbfile, metadata, **conversion_options.get(interface_name, dict()))

                io.write(nwbfile)
            print(f"NWB file saved at {nwbfile_path}!")
        else:
            if nwbfile is None:
                nwbfile = make_nwbfile_from_metadata(metadata=metadata)
            for interface_name, data_interface in self.data_interface_objects.items():
                data_interface.run_conversion(nwbfile, metadata, **conversion_options.get(interface_name, dict()))
            return nwbfile
