from pynwb import NWBFile
from pynwb.ecephys import ElectricalSeries
from hdmf.data_utils import DataChunkIterator
from nwbn_conversion_tools.converter import NWBConverter
from nwbn_conversion_tools.ecephys.intan.load_intan import load_intan, read_header

from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import uuid


class Intan2NWB(NWBConverter):
    def __init__(self, nwbfile=None, metadata=None, source_paths=None):
        """
        Reads data from Intantech .rhd files, using an adapted version of the
        rhd reader scripts: http://intantech.com/downloads.html?tabSelect=Software

        Parameters
        ----------
        nwbfile: pynwb.NWBFile
        metadata: dict
        """
        super().__init__(nwbfile=nwbfile, metadata=metadata, source_paths=source_paths)

    def create_nwbfile(self, metadata_nwbfile):
        """
        Overriding method to get session_start_time form rhd files.
        """
        nwbfile_args = dict(identifier=str(uuid.uuid4()),)
        nwbfile_args.update(**metadata_nwbfile)
        session_start_time = self.get_session_start_time(self.source_paths['dir_ecephys_rhd']['path'])
        nwbfile_args.update(**session_start_time)
        self.nwbfile = NWBFile(**nwbfile_args)

    def get_session_start_time(self, dir_ecephys_rhd):
        """
        Gets session_start_time from first rhd file in dir_ecephys_rhd.

        Parameters
        ----------
        dir_ecephys_rhd: string or Path

        Returns
        -------
        dict
        """
        dir_ecephys_rhd = Path(dir_ecephys_rhd)
        all_files_rhd = list(dir_ecephys_rhd.glob('*.rhd'))
        all_files_rhd.sort()
        # Gets data/time info from first file name
        date_string = Path(all_files_rhd[0]).name.split('.')[0].split('_')[1]
        time_string = Path(all_files_rhd[0]).name.split('.')[0].split('_')[2]
        date_time_string = date_string + ' ' + time_string
        date_time_obj = datetime.strptime(date_time_string, '%y%m%d %H%M%S')
        return {'session_start_time': date_time_obj}

    def run_conversion(self):
        """
        Reads extracellular electrophysiology data from .rhd files and adds data to nwbfile.
        """
        dir_ecephys_rhd = Path(self.source_paths['dir_ecephys_rhd']['path'])
        if 'file_electrodes' in self.source_paths:
            electrodes_file = Path(self.source_paths['file_electrodes']['path'])
        else:
            electrodes_file = None

        def data_gen(source_dir):
            all_files_rhd = list(dir_ecephys_rhd.glob('*.rhd'))
            n_files = len(all_files_rhd)
            # Iterates over all files within the directory
            for ii, fname in enumerate(all_files_rhd):
                print("Converting ecephys rhd data: {}%".format(100 * ii / n_files))
                file_data = load_intan.read_data(filename=fname)
                # Gets only valid timestamps
                valid_ts = file_data['board_dig_in_data'][0]
                analog_data = file_data['amplifier_data'][:, valid_ts]
                n_samples = analog_data.shape[1]
                for sample in range(n_samples):
                    yield analog_data[:, sample]

        # Gets header data from first file
        all_files_rhd = list(dir_ecephys_rhd.glob('*.rhd'))
        all_files_rhd.sort()
        fid = open(all_files_rhd[0], 'rb')
        header = read_header.read_header(fid)
        sampling_rate = header['sample_rate']

        self.create_electrodes_ecephys(
            all_files_rhd=all_files_rhd,
            electrodes_file=electrodes_file
        )

        # Gets electrodes info from first rhd file
        file_data = load_intan.read_data(filename=all_files_rhd[0])
        electrodes_info = file_data['amplifier_channels']
        n_electrodes = len(electrodes_info)
        electrode_table_region = self.nwbfile.create_electrode_table_region(
            region=list(np.arange(n_electrodes)),
            description='no description'
        )

        # Create iterator
        data_iter = DataChunkIterator(
            data=data_gen(source_dir=dir_ecephys_rhd),
            iter_axis=0,
            buffer_size=10000,
            maxshape=(None, n_electrodes)
        )

        # Electrical Series
        metadata_ecephys = self.metadata['Ecephys']
        # Gets electricalseries conversion factor
        es_conversion_factor = file_data['amplifier_data_conversion_factor']
        ephys_ts = ElectricalSeries(
            name=metadata_ecephys['ElectricalSeries'][0]['name'],
            description=metadata_ecephys['ElectricalSeries'][0]['description'],
            data=data_iter,
            electrodes=electrode_table_region,
            rate=sampling_rate,
            starting_time=0.0,
            conversion=es_conversion_factor
        )
        self.nwbfile.add_acquisition(ephys_ts)

    def create_electrodes_ecephys(self, all_files_rhd, electrodes_file):
        """
        Parameters
        ----------
        all_files_rhd: list
            List of paths to rhd files
        electrodes_file : str
            Path to CSV file containing extra electrodes information
        """
        # Gets electrodes info from first rhd file
        file_data = load_intan.read_data(filename=all_files_rhd[0])
        electrodes_info = file_data['amplifier_channels']
        n_electrodes = len(electrodes_info)

        # Electrodes
        if electrodes_file is not None:  # if an electrodes info file was provided
            df_electrodes = pd.read_csv(electrodes_file, index_col='Channel Number')
            for idx, elec in enumerate(electrodes_info):
                elec_name = elec['native_channel_name']
                elec_group = df_electrodes.loc[elec_name]['electrode_group']
                elec_imp = df_electrodes.loc[elec_name]['Impedance Magnitude at 1000 Hz (ohms)']
                self.nwbfile.add_electrode(
                    id=idx,
                    x=np.nan, y=np.nan, z=np.nan,
                    imp=float(elec_imp),
                    location='location',
                    filtering='none',
                    group=self.nwbfile.electrode_groups[elec_group]
                )
        else:  # if no electrodes file info was provided
            first_el_grp = list(self.nwbfile.electrode_groups.keys())[0]
            electrode_group = self.nwbfile.electrode_groups[first_el_grp]
            for idx in range(n_electrodes):
                self.nwbfile.add_electrode(
                    id=idx,
                    x=np.nan, y=np.nan, z=np.nan,
                    imp=np.nan,
                    location='location',
                    filtering='none',
                    group=electrode_group
                )
