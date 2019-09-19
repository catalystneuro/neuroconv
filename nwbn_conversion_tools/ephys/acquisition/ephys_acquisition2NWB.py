from nwbn_conversion_tools.base import Convert2NWB
import pynwb
from datetime import datetime
import numpy as np
import os


class EphysAcquisition2NWB(Convert2NWB):

    def __init__(self, nwbfile, metadata={}):
        super(EphysAcquisition2NWB, self).__init__(nwbfile=nwbfile, metadata=metadata)
        self.RX = None

    def add_acquisition(self, es_name, metadata):
        """
        Adds voltages traces in self.RX as ElectricalSeries at acquisition group
        of current NWBFile.

        Parameters
        ----------
        es_name : str
            Name of ElectricalSeries to be created.
        metadata : dict
            Dict with key:value pairs for defining the Ephys group from where this
            ElectricalSeries belongs. This should contain keys for required groups
            such as 'Device', 'ElectrodeGroup', etc.
        """
        # Tests if ElectricalSeries already exists
        aux = [i.name==es_name for i in self.nwbfile.children]
        if any(aux):
            es = self.nwbfile.children[np.where(aux)[0][0]]
            print(es_name+' already exists in current NWBFile.')
            return es
        else:  # ElectricalSeries can be created in acquisition
            electrode_group = self.add_electrode_group(
                eg_name=metadata['ElectrodeGroup']['name'],
                metadata=metadata
            )

            nChannels = self.RX.get_num_channels()
            electrode_table_region = self.nwbfile.create_electrode_table_region(
                region=list(range(nChannels)),
                description='electrode_table_region'
            )

            rate = self.RX.get_sampling_frequency()
            if 'gain' in self.RX.get_shared_channel_property_names():
                gains = np.array(self.RX.get_channel_gains())
            else:
                gains = np.ones(nChannels)
            es_data = self.RX.get_traces().T
            es_data_V = 1e-6*gains*es_data
            es = pynwb.ecephys.ElectricalSeries(
                name=es_name,
                data=es_data_V,
                electrodes=electrode_table_region,
                starting_time=self.RX.frame_to_time(0),
                rate=rate,
                conversion=1.,
                comments='Generated from SpikeInterface::NwbRecordingExtractor',
                description='acquisition_description'
            )
            self.nwbfile.add_acquisition(es)


    def add_device(self, dev_name):
        """
        Adds a Device group to current NWBFile.

        Parameters
        ----------
        dev_name : str
            Name of Device to be created.
        """
        # Tests if Device already exists
        aux = [i.name==dev_name for i in self.nwbfile.children]
        if any(aux):
            device = self.nwbfile.children[np.where(aux)[0][0]]
            print(dev_name+' already exists in current NWBFile.')
        else:
            device = self.nwbfile.create_device(name=dev_name)
        return device


    def add_electrode_group(self, eg_name, metadata):
        """
        Adds a ElectrodeGroup group to current NWBFile.

        Parameters
        ----------
        eg_name : str
            Name of ElectrodeGroup to be created.
        metadata : dict
            Dict with key:value pairs for defining the Ephys group from where this
            ElectrodeGroup belongs. This should contain keys for required groups
            such as 'Device', 'ElectrodeGroup', etc.
        """
        # Tests if ElectrodeGroup already exists
        aux = [i.name==eg_name for i in self.nwbfile.children]
        if any(aux):
            electrode_group = self.nwbfile.children[np.where(aux)[0][0]]
            print(eg_name+' already exists in current NWBFile.')
        else:
            device = self.add_device(dev_name=metadata[eg_name]['device'])

            eg_description = metadata[eg_name]['description']
            eg_location = metadata[eg_name]['location']
            electrode_group = self.nwbfile.create_electrode_group(
                name=eg_name,
                location=eg_location,
                device=device,
                description=eg_description
            )

            # add electrodes with locations
            nChannels = self.RX.get_num_channels()
            for m in range(nChannels):
                location = self.RX.get_channel_property(m, 'location')
                impedance = -1.0
                while len(location) < 3:
                    location = np.append(location, [0])
                self.nwbfile.add_electrode(
                    id=m,
                    x=float(location[0]), y=float(location[1]), z=float(location[2]),
                    imp=impedance,
                    location='electrode_location',
                    filtering='none',
                    group=electrode_group,
                )

            # add other existing electrode properties
            properties = self.RX.get_shared_channel_property_names()
            properties.remove('location')
            for pr in properties:
                pr_data = [self.RX.get_channel_property(ind, pr) for ind in range(nChannels)]
                self.nwbfile.add_electrode_column(
                    name=pr,
                    description='',
                    data=pr_data,
                )

        return electrode_group
