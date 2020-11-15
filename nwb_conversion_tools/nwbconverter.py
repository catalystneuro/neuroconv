"""Authors: Cody Baker and Ben Dichter."""
import uuid
from datetime import datetime

from pynwb import NWBHDF5IO, NWBFile
from pynwb.file import Subject

from .utils import (get_schema_from_hdmf_class, get_metadata_schema, get_input_schema,
                    get_schema_for_NWBFile, dict_deep_update)


class NWBConverter:
    """Primary class for all NWB conversion classes."""

    data_interface_classes = None

    @classmethod
    def get_input_schema(cls):
        """Compile input schemas from each of the data interface classes."""
        input_schema = get_input_schema()
        for name, data_interface in cls.data_interface_classes.items():
            input_schema['properties'].update(name=data_interface.get_input_schema())
        return input_schema

    def __init__(self, **input_data):
        """
        Initialize all of the underlying data interfaces.

        This dictionary routes the user options (input_data and conversion_options) to the respective data interfaces.
        It automatically checks with the interface schemas which data belongs to each
        """
        self.data_interface_objects = {name: data_interface(**input_data[name])
                                       for name, data_interface in
                                       self.data_interface_classes.items()}

    def get_metadata_schema(self):
        """Compile metadata schemas from each of the data interface objects."""
        metadata_schema = get_metadata_schema()
        metadata_schema['properties'] = dict(
            NWBFile=get_schema_for_NWBFile(),
            Subject=get_schema_from_hdmf_class(Subject)
        )
        metadata_schema['required'].append('NWBFile')
        for name, data_interface in self.data_interface_objects.items():
            interface_schema = data_interface.get_metadata_schema()
            metadata_schema = dict_deep_update(metadata_schema, interface_schema)
        return metadata_schema

    def get_metadata(self):
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        metadata = dict(
            NWBFile=dict(
                session_description="no description",
                identifier=str(uuid.uuid4()),
            )
        )
        for interface in self.data_interface_objects.values():
            interface_metadata = interface.get_metadata()
            metadata = dict_deep_update(metadata, interface_metadata)
        return metadata

    def run_conversion(self, metadata_dict, nwbfile_path=None, save_to_file=True, conversion_options=None):
        """Build nwbfile object, auto-populate with minimal values if missing."""

        if conversion_options is None:
            conversion_options = dict()


        if 'NWBFile' in metadata_dict:
            nwbfile_kwargs.update(metadata_dict['NWBFile'])

            # convert ISO 8601 string to datetime
            if isinstance(nwbfile_kwargs['session_start_time'], str):
                nwbfile_kwargs['session_start_time'] = datetime.fromisoformat(
                    metadata_dict['NWBFile']['session_start_time'])

        if 'Subject' in metadata_dict:
            nwbfile_kwargs.update(subject=Subject(**metadata_dict['Subject']))
        nwbfile = NWBFile(**nwbfile_kwargs)

        for interface_name, data_interface in self.data_interface_objects.items():
            these_conversion_options = get_schema_data(
                conversion_options,
                data_interface.get_conversion_options_schema()
            )
            data_interface.convert_data(nwbfile, metadata_dict, **these_conversion_options)

        # Save result to file or return object
        if save_to_file:
            if nwbfile_path is None:
                raise TypeError('A path to the output file must be provided, but nwbfile_path got value None')
            # run_conversion will always overwrite the existing nwbfile_path
            with NWBHDF5IO(nwbfile_path, mode='w') as io:
                io.write(nwbfile)
            print(f'NWB file saved at {nwbfile_path}')
        else:
            return nwbfile
