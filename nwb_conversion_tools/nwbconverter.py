"""Authors: Cody Baker and Ben Dichter."""
import uuid
from datetime import datetime
from jsonschema import validate
from pathlib import Path
from typing import Optional

from pynwb import NWBHDF5IO, NWBFile
from pynwb.file import Subject

from .utils import get_schema_from_hdmf_class, get_schema_for_NWBFile
from .json_schema_utils import dict_deep_update, get_base_schema, fill_defaults, \
    unroot_schema


class NWBConverter:
    """Primary class for all NWB conversion classes."""

    data_interface_classes = None

    @classmethod
    def get_source_schema(cls):
        """Compile input schemas from each of the data interface classes."""
        source_schema = get_base_schema(
            root=True,
            id_='source.schema.json',
            title='Source data schema',
            description='Schema for the source data, files and directories',
            version='0.1.0'
        )
        for interface_name, data_interface in cls.data_interface_classes.items():
            source_schema['properties'].update(
                {interface_name: unroot_schema(data_interface.get_source_schema())})
        return source_schema

    @classmethod
    def get_conversion_options_schema(cls):
        """Compile conversion option schemas from each of the data interface classes."""
        conversion_options_schema = get_base_schema(
            root=True,
            id_='conversion_options.schema.json',
            title="Conversion options schema",
            description="Schema for the conversion options",
            version="0.1.0"
        )
        for interface_name, data_interface in cls.data_interface_classes.items():
            conversion_options_schema['properties'].update({
                interface_name: unroot_schema(data_interface.get_conversion_options_schema())
            })
        return conversion_options_schema

    def __init__(self, source_data):
        """Validate source_data against source_schema and initialize all data interfaces."""
        # Validate source_data against source_schema
        validate(instance=source_data, schema=self.get_source_schema())

        # If data is valid, proceed to instantiate DataInterface objects
        self.data_interface_objects = {
            name: data_interface(**source_data[name])
            for name, data_interface in self.data_interface_classes.items()
            if name in source_data
        }

    def get_metadata_schema(self):
        """Compile metadata schemas from each of the data interface objects."""
        metadata_schema = get_base_schema(
            id_='metadata.schema.json',
            root=True,
            title='Metadata',
            description='Schema for the metadata',
            version="0.1.0",
            required=["NWBFile"],
            properties=dict(
                NWBFile=get_schema_for_NWBFile(),
                Subject=get_schema_from_hdmf_class(Subject)
            )
        )
        for data_interface in self.data_interface_objects.values():
            interface_schema = unroot_schema(data_interface.get_metadata_schema())
            metadata_schema = dict_deep_update(metadata_schema, interface_schema)

        # fill_defaults(metadata_schema, self.get_metadata())
        return metadata_schema

    def get_metadata(self):
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        metadata = dict(
            NWBFile=dict(
                session_description="no description",
                identifier=str(uuid.uuid4()),
                session_start_time=datetime(1970, 1, 1)
            )
        )
        for interface in self.data_interface_objects.values():
            interface_metadata = interface.get_metadata()
            metadata = dict_deep_update(metadata, interface_metadata)
        return metadata

    def run_conversion(self, metadata: dict, save_to_file: bool = True, nwbfile_path: Optional[str] = None,
                       overwrite: bool = False, nwbfile: Optional[NWBFile] = None,
                       conversion_options: Optional[dict] = None):
        """Build nwbfile object, auto-populate with minimal values if missing."""
        assert (not save_to_file and nwbfile_path is None) or nwbfile is None, \
            "Either pass a nwbfile_path location with save_to_file=True, or a nwbfile object, but not both!"
        if conversion_options is None:
            conversion_options = dict()
        else:
            validate(instance=conversion_options, schema=self.get_conversion_options_schema())

        if nwbfile is None:
            nwbfile_kwargs = metadata['NWBFile']
            if 'Subject' in metadata:
                # convert ISO 8601 string to datetime
                if 'date_of_birth' in metadata['Subject'] \
                        and isinstance(metadata['Subject']['date_of_birth'], str):
                    metadata['Subject']['date_of_birth'] = datetime.fromisoformat(
                        metadata['Subject']['date_of_birth']
                    )
                nwbfile_kwargs.update(subject=Subject(**metadata['Subject']))
            # convert ISO 8601 string to datetime
            if isinstance(nwbfile_kwargs['session_start_time'], str):
                nwbfile_kwargs['session_start_time'] = datetime.fromisoformat(
                    metadata['NWBFile']['session_start_time']
                )
            nwbfile = NWBFile(**nwbfile_kwargs)

        # Save result to file or return object
        if save_to_file:
            if nwbfile_path is None:
                raise TypeError("A path to the output file must be provided, but nwbfile_path got value None")

            if Path(nwbfile_path).is_file() and not overwrite:
                mode = "r+"
            else:
                mode = "w"

            with NWBHDF5IO(nwbfile_path, mode=mode) as io:
                if mode == "r+":
                    nwbfile = io.read()

                for interface_name, data_interface in self.data_interface_objects.items():
                    data_interface.run_conversion(nwbfile, metadata, **conversion_options.get(interface_name, dict()))

                io.write(nwbfile)
            print(f"NWB file saved at {nwbfile_path}!")
        else:
            for interface_name, data_interface in self.data_interface_objects.items():
                data_interface.run_conversion(nwbfile, metadata, **conversion_options.get(interface_name, dict()))
            return nwbfile
