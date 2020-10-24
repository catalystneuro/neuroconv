"""Authors: Cody Baker and Ben Dichter."""
from .utils import (get_schema_from_hdmf_class, get_root_schema, get_input_schema,
                    get_schema_for_NWBFile)
from pynwb import NWBHDF5IO, NWBFile
from pynwb.file import Subject
from datetime import datetime
import uuid
import collections.abc
import numpy as np


def dict_deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = dict_deep_update(d.get(k, {}), v)
        elif isinstance(v, list):
            d[k] = d.get(k, []) + v
            # Remove repeated items if they exist
            if len(v) > 0 and not isinstance(v[0], dict):
                d[k] = list(np.unique(d[k]))
        else:
            d[k] = v
    return d


class NWBConverter:
    """Primary class for all NWB conversion classes."""

    data_interface_classes = None

    @classmethod
    def get_input_schema(cls):
        """Compile input schemas from each of the data interface classes."""
        input_schema = get_input_schema()
        for name, data_interface in cls.data_interface_classes.items():
            input_schema['properties'] = dict_deep_update(input_schema['properties'], data_interface.get_input_schema())
        return input_schema

    def __init__(self, **input_data):
        """Initialize all of the underlying data interfaces."""
        # This dictionary routes the user options (source_data and conversion_options)
        # to the respective data interfaces
        # It automatically checks with the interface schemas which data belongs to each
        self.data_interface_objects = dict()
        input_data_routed = dict()
        for interface_name, interface in self.data_interface_classes.items():
            input_data_routed[interface_name] = dict()
            interface_schema = interface.get_input_schema()
            for b in set(interface_schema.keys()).intersection(set(['source_data', 'conversion_options'])):
                input_data_routed[interface_name].update({
                    k: input_data[b].get(k, None)
                    for k in interface_schema[b]['properties'].keys()
                })

        self.data_interface_objects = {
            name: data_interface(**input_data_routed[name])
            for name, data_interface in self.data_interface_classes.items()
        }

    def get_metadata_schema(self):
        """Compile metadata schemas from each of the data interface objects."""
        metadata_schema = get_root_schema()
        metadata_schema['properties'] = dict(
            NWBFile=get_schema_for_NWBFile(),
            Subject=get_schema_from_hdmf_class(Subject)
        )
        for name, data_interface in self.data_interface_objects.items():
            interface_schema = data_interface.get_metadata_schema()
            metadata_schema = dict_deep_update(metadata_schema, interface_schema)

        return metadata_schema

    def get_metadata(self):
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        metadata = dict()
        for interface_name, interface in self.data_interface_objects.items():
            interface_metadada = interface.get_metadata(metadata=metadata)
            metadata = dict_deep_update(metadata, interface_metadada)

        return metadata

    def run_conversion(self, metadata_dict, nwbfile_path=None, save_to_file=True,
                       stub_test=False):
        """Build nwbfile object, auto-populate with minimal values if missing."""
        if 'NWBFile' not in metadata_dict:
            metadata_dict['NWBFile'] = dict(
                session_description="no description",
                identifier=str(uuid.uuid4()),
                session_start_time=datetime.now()
            )

        # add Subject
        if 'Subject' not in metadata_dict:
            metadata_dict['Subject'] = {}
        subject = Subject(**metadata_dict['Subject'])
        nwbfile = NWBFile(subject=subject, **metadata_dict['NWBFile'])

        # add devices
        for domain in ('Icephys', 'Ecephys', 'Ophys'):
            if domain in metadata_dict:
                dev_keys = [k for k in metadata_dict[domain].keys() if 'Device' in k]
                for dev in dev_keys:
                    nwbfile.create_device(**metadata_dict[domain][dev])

        # Run data interfaces data conversion
        for name, data_interface in self.data_interface_objects.items():
            data_interface.convert_data(nwbfile, metadata_dict[name], stub_test)

        if save_to_file:
            if nwbfile_path is None:
                raise TypeError('A path to the output file must be provided, but nwbfile_path got value None')
            # run_conversion will always overwrite the existing nwbfile_path
            with NWBHDF5IO(nwbfile_path, mode='w') as io:
                io.write(nwbfile)
            print(f'NWB file saved at {nwbfile_path}')
        else:
            return nwbfile
