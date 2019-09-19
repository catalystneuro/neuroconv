from nwbn_conversion_tools.base import Convert2NWB
import numpy as np


class EphysAcquisition2NWB(Convert2NWB):

    def __init__(self, nwbfile):
        super(EphysAcquisition2NWB).__init__(nwbfile)


    def save(self, to_path, metadata={}):
        """
        Saves data to NWB file.

        Parameters
        ----------
        to_path: str
            Full path to NWB file to be saved/updated.
        metadata: dict
            Dictionary with Key:Value pairs containing meta info
        """
        # Arguments to include in the nwb file
        to_path = 'giocomo_data.nwb'
        metadata = {'experimenter':'Name',
                    'institution':'Institution',
                    'lab':'Giocomo lab'}

        # Write recording data (voltage traces) to nwb file
        M = recording.get_num_channels()

        if os.path.exists(to_path):
            io = NWBHDF5IO(to_path, 'r+')
            nwbfile = io.read()
        else:
            io = NWBHDF5IO(to_path, mode='w')
            input_nwbfile_kwargs = {
                'session_start_time': datetime.now(),
                'identifier': '',
                'session_description': ''}
            if 'NWBFile' in metadata:
                input_nwbfile_kwargs.update(metadata['NWBFile'])
            nwbfile = NWBFile(**input_nwbfile_kwargs)

        # Tests if specific Device already exists
        aux = [i.name == metadata['Ephys']['name'], pynwb.device.Device) for i in nwbfile.children]
        if any(aux):
            device = nwbfile.children[np.where(aux)[0][0]]
        else:
            dev_name = 'Device'
            device = nwbfile.create_device(name=dev_name)

        # Tests if ElectrodeGroup already exists
        aux = [isinstance(i, pynwb.ecephys.ElectrodeGroup) for i in nwbfile.children]
        if any(aux):
            electrode_group = nwbfile.children[np.where(aux)[0][0]]
        else:
            eg_name = 'electrode_group_name'
            eg_description = "electrode_group_description"
            eg_location = "electrode_group_location"
            electrode_group = nwbfile.create_electrode_group(
                name=eg_name,
                location=eg_location,
                device=device,
                description=eg_description
            )

            # add electrodes with locations
            for m in range(M):
                location = recording.get_channel_property(m, 'location')
                impedence = -1.0
                while len(location) < 3:
                    location = np.append(location, [0])
                nwbfile.add_electrode(
                    id=m,
                    x=float(location[0]), y=float(location[1]), z=float(location[2]),
                    imp=impedence,
                    location='electrode_location',
                    filtering='none',
                    group=electrode_group,
                )

            # add other existing electrode properties
            properties = recording.get_shared_channel_property_names()
            properties.remove('location')
            for pr in properties:
                pr_data = [recording.get_channel_property(ind, pr) for ind in range(M)]
                nwbfile.add_electrode_column(
                    name=pr,
                    description='',
                    data=pr_data,
                )

            electrode_table_region = nwbfile.create_electrode_table_region(
                list(range(M)),
                'electrode_table_region'
            )

        # Tests if Acquisition already exists
        aux = [isinstance(i, pynwb.ecephys.ElectricalSeries) for i in nwbfile.children]
        if any(aux):
            acquisition = nwbfile.children[np.where(aux)[0][0]]
        else:
            rate = recording.get_sampling_frequency()
            if 'gain' in recording.get_shared_channel_property_names():
                gains = np.array(recording.get_channel_gains())
            else:
                gains = np.ones(M)
            ephys_data = recording.get_traces().T
            ephys_data_V = 1e-6*gains*ephys_data
            acquisition_name = 'ElectricalSeries'
            ephys_ts = ElectricalSeries(
                name=acquisition_name,
                data=ephys_data_V,
                electrodes=electrode_table_region,
                starting_time=recording.frame_to_time(0),
                rate=rate,
                conversion=1.,
                comments='Generated from SpikeInterface::NwbRecordingExtractor',
                description='acquisition_description'
            )
            nwbfile.add_acquisition(ephys_ts)

        io.write(nwbfile)
        io.close()
