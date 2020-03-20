from pynwb.ecephys import ElectricalSeries
from hdmf.data_utils import DataChunkIterator
from nwbn_conversion_tools.ephys.acquisition.ephys_acquisition2NWB import EphysAcquisition2NWB
from nwbn_conversion_tools.ephys.acquisition.intan.load_intan import load_intan, read_header

from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import copy
import os


class Intan2NWB(EphysAcquisition2NWB):
    def __init__(self, nwbfile=None, metadata=None):
        """
        Reads data from Intantech .rhd files, using an adapted version of the
        rhd reader scripts: http://intantech.com/downloads.html?tabSelect=Software

        Parameters
        ----------
        nwbfile: pynwb.NWBFile
        metadata: dict
        """
        super(Intan2NWB, self).__init__(nwbfile=nwbfile, metadata=metadata)

    def add_acquisition(nwbfile, metadata, source_dir, electrodes_file=None):
        """
        Reads extracellular electrophysiology data from .rhd files and adds data to nwbfile.
        """
        def data_gen(source_dir):
            all_files = [os.path.join(source_dir, file) for file in os.listdir(source_dir) if file.endswith(".rhd")]
            n_files = len(all_files)
            # Iterates over all files within the directory
            for ii, fname in enumerate(all_files):
                print("Converting ecephys rhd data: {}%".format(100 * ii / n_files))
                file_data = load_intan.read_data(filename=fname)
                # Gets only valid timestamps
                valid_ts = file_data['board_dig_in_data'][0]
                analog_data = file_data['amplifier_data'][:, valid_ts]
                n_samples = analog_data.shape[1]
                for sample in range(n_samples):
                    yield analog_data[:, sample]

        # Gets header data from first file
        all_files = [os.path.join(source_dir, file) for file in os.listdir(source_dir) if file.endswith(".rhd")]
        all_files.sort()
        fid = open(all_files[0], 'rb')
        header = read_header.read_header(fid)
        sampling_rate = header['sample_rate']

        # Get initial metadata
        meta_init = copy.deepcopy(metadata)
        if nwbfile is None:
            date_string = Path(all_files[0]).name.split('.')[0].split('_')[1]
            time_string = Path(all_files[0]).name.split('.')[0].split('_')[2]
            date_time_string = date_string + ' ' + time_string
            date_time_obj = datetime.strptime(date_time_string, '%y%m%d %H%M%S')
            meta_init['NWBFile']['session_start_time'] = date_time_obj
            nwbfile = create_nwbfile(meta_init)

        # Adds Device
        device = nwbfile.create_device(name=metadata['Ecephys']['Device'][0]['name'])

        # Electrodes Groups
        meta_electrode_groups = metadata['Ecephys']['ElectrodeGroup']
        for meta in meta_electrode_groups:
            nwbfile.create_electrode_group(
                name=meta['name'],
                description=meta['description'],
                location=meta['location'],
                device=device
            )

        # Gets electrodes info from first rhd file
        file_data = load_intan.read_data(filename=all_files[0])
        electrodes_info = file_data['amplifier_channels']
        n_electrodes = len(electrodes_info)

        # Electrodes
        if electrodes_file is not None:  # if an electrodes info file was provided
            df_electrodes = pd.read_csv(electrodes_file, index_col='Channel Number')
            for idx, elec in enumerate(electrodes_info):
                elec_name = elec['native_channel_name']
                elec_group = df_electrodes.loc[elec_name]['electrode_group']
                elec_imp = df_electrodes.loc[elec_name]['Impedance Magnitude at 1000 Hz (ohms)']
                nwbfile.add_electrode(
                    id=idx,
                    x=np.nan, y=np.nan, z=np.nan,
                    imp=float(elec_imp),
                    location='location',
                    filtering='none',
                    group=nwbfile.electrode_groups[elec_group]
                )
        else:  # if no electrodes file info was provided
            first_el_grp = list(nwbfile.electrode_groups.keys())[0]
            electrode_group = nwbfile.electrode_groups[first_el_grp]
            for idx in range(n_electrodes):
                nwbfile.add_electrode(
                    id=idx,
                    x=np.nan, y=np.nan, z=np.nan,
                    imp=np.nan,
                    location='location',
                    filtering='none',
                    group=electrode_group
                )

        electrode_table_region = nwbfile.create_electrode_table_region(
            region=list(np.arange(n_electrodes)),
            description='no description'
        )

        # Create iterator
        data_iter = DataChunkIterator(
            data=data_gen(source_dir=source_dir),
            iter_axis=0,
            buffer_size=10000,
            maxshape=(None, n_electrodes)
        )

        # Electrical Series
        # Gets electricalseries conversion factor
        es_conversion_factor = file_data['amplifier_data_conversion_factor']
        ephys_ts = ElectricalSeries(
            name=metadata['Ecephys']['ElectricalSeries'][0]['name'],
            description=metadata['Ecephys']['ElectricalSeries'][0]['description'],
            data=data_iter,
            electrodes=electrode_table_region,
            rate=sampling_rate,
            starting_time=0.0,
            conversion=es_conversion_factor
        )
        nwbfile.add_acquisition(ephys_ts)

        return nwbfile
