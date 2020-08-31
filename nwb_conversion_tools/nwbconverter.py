"""Authors: Cody Baker and Ben Dichter."""
from copy import deepcopy
from .utils import get_schema_from_hdmf_class, get_root_schema
from pynwb import NWBHDF5IO, NWBFile
from pynwb.file import Subject
from datetime import datetime
import uuid


class NWBConverter:
    data_interface_classes = None  # dict of all data interfaces

    @classmethod
    def get_input_schema(cls):
        """Compile input schemas from each of the data interface classes."""
        input_schema = deepcopy(get_root_schema())
        for name, data_interface in cls.data_interface_classes.items():
            input_schema['properties'].update(data_interface.get_input_schema())
        return input_schema

    def __init__(self, **input_paths):
        """Initialize all of the underlying data interfaces."""
        self.data_interface_objects = {name: data_interface(**input_paths[name])
                                       for name, data_interface in self.data_interface_classes.items()}

    def get_metadata_schema(self):
        """Compile metadata schemas from each of the data interface objects."""
        metadata_schema = deepcopy(get_root_schema())
        metadata_schema['properties'] = dict(
            NWBFile=get_schema_from_hdmf_class(NWBFile),
            Subject=get_schema_from_hdmf_class(Subject)
        )
        for name, data_interface in self.data_interface_objects.items():
            metadata_schema['properties'].update(data_interface.get_metadata_schema()['properties'])
            for field in data_interface.get_metadata_schema()['required']:
                metadata_schema['required'].append(field)

        return metadata_schema

    def run_conversion(self, nwbfile_path, metadata_dict, stub_test=False):
        """Build nwbfile object, auto-populate with minimal values if missing."""
        if 'NWBFile' not in metadata_dict:
            metadata_dict['NWBFile'] = {'session_description': 'no description',
                                        'identifier': str(uuid.uuid4()),
                                        'session_start_time': datetime.now()}
        if 'Subject' not in metadata_dict:
            metadata_dict['Subject'] = {}
        subject = Subject(**metadata_dict['Subject'])
        nwbfile = NWBFile(subject=subject, **metadata_dict['NWBFile'])

        """Run all of the data interfaces"""
        # default implementation will be to sequentially run each data interface, but this can be overridden as needed
        [data_interface.convert_data(nwbfile, metadata_dict[name], stub_test)
         for name, data_interface in self.data_interface_objects.items()]

        # run_conversion will always overwrite the existing nwbfile_path
        with NWBHDF5IO(nwbfile_path, mode='w') as io:
            io.write(nwbfile)
