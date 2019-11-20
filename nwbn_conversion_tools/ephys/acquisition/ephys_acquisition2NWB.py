from nwbn_conversion_tools.base import Convert2NWB
import pynwb
import spikesorters as ss
import spiketoolkit as st
import numpy as np


class EphysAcquisition2NWB(Convert2NWB):
    def __init__(self, nwbfile, metadata={}):
        super(EphysAcquisition2NWB, self).__init__(nwbfile=nwbfile, metadata=metadata)
        self.RX = None
        self.SX = None

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
        aux = [i.name == es_name for i in self.nwbfile.children]
        if any(aux):
            es = self.nwbfile.children[np.where(aux)[0][0]]
            print(es_name+' already exists in current NWBFile.')
            return es
        else:  # ElectricalSeries can be created in acquisition
            self.add_electrode_group(
                eg_name=metadata['ElectrodeGroup'][0]['name'],
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
        aux = [i.name == dev_name for i in self.nwbfile.children]
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
        aux = [i.name == eg_name for i in self.nwbfile.children]
        if any(aux):
            electrode_group = self.nwbfile.children[np.where(aux)[0][0]]
            print(eg_name+' already exists in current NWBFile.')
        else:
            device = self.add_device(dev_name=metadata['ElectrodeGroup'][0]['device'])

            eg_description = metadata['ElectrodeGroup'][0]['description']
            eg_location = metadata['ElectrodeGroup'][0]['location']
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

    def add_units(self):
        """
        Adds Units group to current NWBFile.
        """
        if self.SX is None:
            print("There are no sorted units to be added. Please run "
                  "'run_spike_sorting' to get sorted units.")
            return None
        # Tests if Units already exists
        aux = [i.name == 'Units' for i in self.nwbfile.children]
        if any(aux):
            print('Units already exists in current NWBFile.')
            return
        else:
            ids = self.SX.get_unit_ids()
            fs = self.SX.get_sampling_frequency()
            # Stores spike times for each detected cell (unit)
            for id in ids:
                spkt = self.SX.get_unit_spike_train(unit_id=id) / fs
                if 'waveforms' in self.SX.get_unit_spike_feature_names(unit_id=id):
                    # Stores average and std of spike traces
                    wf = self.SX.get_unit_spike_features(unit_id=id,
                                                         feature_name='waveforms')
                    relevant_ch = most_relevant_ch(wf)
                    # Spike traces on the most relevant channel
                    traces = wf[:, relevant_ch, :]
                    traces_avg = np.mean(traces, axis=0)
                    traces_std = np.std(traces, axis=0)
                    self.nwbfile.add_unit(
                        id=id,
                        spike_times=spkt,
                        waveform_mean=traces_avg,
                        waveform_sd=traces_std
                    )
                else:
                    self.nwbfile.add_unit(id=id, spike_times=spkt)

    def run_spike_sorting(self, sorter_name='herdingspikes', add_to_nwb=True,
                          output_folder='my_sorter_output', delete_output_folder=True):
        """
        Performs spike sorting, using SpikeSorters:
        https://github.com/SpikeInterface/spikesorters

        Parameters
        ----------
        sorter_name : str
        add_to_nwb : boolean
            Whether to add the sorted units results to the NWB file or not. The
            results will still be available through the extractor attribute SX.
        output_folder : str or path
            Folder that is created to store the results from the spike sorting.
        delete_output_folder : boolean
            Whether to delete or not the content created in output_folder.
        """
        self.SX = ss.run_sorter(
            sorter_name_or_class=sorter_name,
            recording=self.RX,
            output_folder=output_folder,
            delete_output_folder=delete_output_folder
        )

        st.postprocessing.get_unit_waveforms(
            recording=self.RX,
            sorting=self.SX,
            ms_before=1,
            ms_after=2,
            save_as_features=True,
            verbose=False
        )

        if add_to_nwb:
            self.add_units()


def most_relevant_ch(traces):
    """
    Calculates the most relevant channel for an Unit.
    Estimates the channel where the max-min difference of the average traces is greatest.

    traces : ndarray
        ndarray of shape (nSpikes, nChannels, nSamples)
    """
    nChannels = traces.shape[1]
    avg = np.mean(traces, axis=0)

    max_min = np.zeros(nChannels)
    for ch in range(nChannels):
        max_min[ch] = avg[ch, :].max() - avg[ch, :].min()

    relevant_ch = np.argmax(max_min)
    return relevant_ch
