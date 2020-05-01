import uuid
from typing import Dict

from pynwb import NWBFile, NWBHDF5IO
from pynwb.file import Subject

from spikeextractors import SortingExtractor, RecordingExtractor, NwbSortingExtractor, NwbRecordingExtractor


class NWBConverter:
    """
    Common conversion code factored out so it can be used by multiple conversion projects
    """

    def __init__(self, metadata, nwbfile=None, source_paths=None):
        """

        Parameters
        ----------
        metadata: dict
        nwbfile: pynwb.NWBFile
        source_paths: dict
        """
        self.metadata = metadata
        self.source_paths = source_paths

        # create self.nwbfile object
        if nwbfile is None:
            self.create_nwbfile(metadata['NWBFile'])
        else:
            self.nwbfile = nwbfile

        # add subject information
        if 'Subject' in metadata:
            self.create_subject(metadata['Subject'])

        # add devices
        self.devices = dict()
        for domain in ('Icephys', 'Ecephys', 'Ophys'):
            if domain in metadata and 'Device' in metadata[domain]:
                self.devices.update(self.create_devices(metadata[domain]['Device']))

        if 'Ecephys' in metadata:
            if 'ElectrodeGroup' in metadata['Ecephys']:
                self.create_electrode_groups(metadata['Ecephys'])

        if 'Icephys' in metadata:
            if 'Electrode' in metadata['Icephys']:
                self.ic_elecs = self.create_icephys_elecs(metadata['Icephys']['Electrode'])

    def create_nwbfile(self, metadata_nwbfile):
        """
        This method is called at __init__.
        This method can be overridden by child classes if necessary.
        Creates self.nwbfile object.

        Parameters
        ----------
        metadata_nwbfile: dict
        """
        nwbfile_args = dict(identifier=str(uuid.uuid4()),)
        nwbfile_args.update(**metadata_nwbfile)
        self.nwbfile = NWBFile(**nwbfile_args)

    def create_subject(self, metadata_subject):
        """
        This method is called at __init__.
        This method can be overridden by child classes if necessary.
        Adds information about Subject to self.nwbfile.

        Parameters
        ----------
        metadata_subject: dict
        """
        self.nwbfile.subject = Subject(**metadata_subject)

    def create_devices(self, metadata_device) -> Dict:
        """
        This method is called at __init__.
        This method should not be overridden.
        Use metadata to create Device object(s) in the NWBFile

        Parameters
        ----------
        metadata_device: list or dict

        Returns
        -------
        dict

        """
        if isinstance(metadata_device, list):
            devices = dict()
            [devices.update(self.create_devices(idevice_meta)) for idevice_meta in metadata_device]
            return devices
        else:
            if 'tag' in metadata_device:
                key = metadata_device['tag']
            else:
                key = metadata_device['name']
            return {key: self.nwbfile.create_device(**metadata_device)}

    def create_electrode_groups(self, metadata_ecephys):
        """
        This method is called at __init__.
        This method should not be overridden.
        Use metadata to create ElectrodeGroup object(s) in the NWBFile

        Parameters
        ----------
        metadata_ecephys : dict
            Dict with key:value pairs for defining the Ecephys group from where this
            ElectrodeGroup belongs. This should contain keys for required groups
            such as 'Device', 'ElectrodeGroup', etc.
        """
        for metadata_elec_group in metadata_ecephys['ElectrodeGroup']:
            eg_name = metadata_elec_group['name']
            # Tests if ElectrodeGroup already exists
            aux = [i.name == eg_name for i in self.nwbfile.children]
            if any(aux):
                print(eg_name + ' already exists in current NWBFile.')
            else:
                device_name = metadata_elec_group['device']
                if device_name in self.nwbfile.devices:
                    device = self.nwbfile.devices[device_name]
                else:
                    print('Device ', device_name, ' for ElectrodeGroup ', eg_name, ' does not exist.')
                    print('Make sure ', device_name, ' is defined in metadata.')

                eg_description = metadata_elec_group['description']
                eg_location = metadata_elec_group['location']
                self.nwbfile.create_electrode_group(
                    name=eg_name,
                    location=eg_location,
                    device=device,
                    description=eg_description
                )

    def create_electrodes_ecephys(self):
        """
        This method should be overridden by child classes if necessary.
        Create electrodes in the NWBFile.
        """
        pass

    def create_icephys_elecs(self, elec_meta) -> Dict:
        """
        Use metadata to generate intracellular electrode object(s) in the NWBFile

        Parameters
        ----------
        elec_meta: list or dict

        Returns
        -------
        list

        """
        if isinstance(elec_meta, list):
            elecs = dict()
            [elecs.update(self.create_icephys_elecs(**ielec_meta)) for ielec_meta in elec_meta]
            return elecs

        else:
            if len(self.devices) == 1:
                device = list(self.devices.values())[0]
            elif elec_meta['device'] in self.devices:
                device = self.devices[elec_meta['device']]
            else:
                raise ValueError('device not found for icephys electrode {}'.format(elec_meta['name']))
            if 'tag' in elec_meta:
                key = elec_meta['tag']
            else:
                key = elec_meta['name']
            return {key: self.nwbfile.create_ic_electrode(device=device, **elec_meta)}

    def create_trials_from_df(self, df):
        """
        This method should not be overridden.
        Creates a trials table in self.nwbfile from a Pandas DataFrame.

        Parameters
        ----------
        df: Pandas DataFrame
        """
        # Tests if trials table already exists
        if self.nwbfile.trials is not None:
            print("Trials table already exist in current nwb file.\n"
                  "Use 'add_trials_columns_from_df' to include new columns.\n"
                  "Use 'add_trials_from_df' to include new trials.")
            pass
        # Tests if required column names are present in df
        if 'start_time' not in df.columns:
            print("Required column 'start_time' not present in DataFrame.")
            pass
        if 'stop_time' not in df.columns:
            print("Required column 'stop_time' not present in DataFrame.")
            pass
        # Creates new columns
        for colname in df.columns:
            if colname not in ['start_time', 'stop_time']:
                # Indexed columns should be of type 'object' in the dataframe
                if df[colname].dtype == 'object':
                    self.nwbfile.add_trial_column(name=colname, description='no description', index=True)
                else:
                    self.nwbfile.add_trial_column(name=colname, description='no description')
        # Populates trials table from df values
        for index, row in df.iterrows():
            self.nwbfile.add_trial(**dict(row))

    def add_trials_from_df(self, df):
        """
        This method should not be overridden.
        Adds trials from a Pandas DataFrame to existing trials table in self.nwbfile.

        Parameters
        ----------
        df: Pandas DataFrame
        """
        # Tests for mismatch between trials table columns and dataframe columns
        A = set(self.nwbfile.trials.colnames)
        B = set(df.columns)
        if len(A - B) > 0:
            print("Missing columns in DataFrame: ", A - B)
            pass
        if len(B - A) > 0:
            print("NWBFile trials table does not contain: ", B - A)
            pass
        # Adds trials from df values
        for index, row in df.iterrows():
            self.nwbfile.add_trial(**dict(row))

    def add_trials_columns_from_df(self, df):
        """
        This method should not be overridden.
        Adds trials columns from a Pandas DataFrame to existing trials table in self.nwbfile.

        Parameters
        ----------
        df: Pandas DataFrame
        """
        # Tests if dataframe columns already exist in nwbfile trials table
        A = set(self.nwbfile.trials.colnames)
        B = set(df.columns)
        intersection = A.intersection(B)
        if len(intersection) > 0:
            print("These columns already exist in nwbfile trials: ", intersection)
            pass
        # Adds trials columns with data from df values
        for (colname, coldata) in df.iteritems():
            # Indexed columns should be of type 'object' in the dataframe
            if df[colname].dtype == 'object':
                index = True
            else:
                index = False
            self.nwbfile.add_trial_column(
                name=colname,
                description='no description',
                data=coldata,
                index=index
            )

    def save(self, to_path, read_check=True):
        """
        This method should not be overridden.
        Saves object self.nwbfile.

        Parameters
        ----------
        to_path: str
        read_check: bool
            If True, try to read the file after writing
        """

        with NWBHDF5IO(to_path, 'w') as io:
            io.write(self.nwbfile)

        if read_check:
            with NWBHDF5IO(to_path, 'r') as io:
                io.read()

    def check_module(self, name, description=None):
        """
        Check if processing module exists. If not, create it. Then return module

        Parameters
        ----------
        name: str
        description: str | None (optional)

        Returns
        -------
        pynwb.module

        """

        if name in self.nwbfile.processing:
            return self.nwbfile.processing[name]
        else:
            if description is None:
                description = name
            return self.nwbfile.create_processing_module(name, description)

    def add_sortingxtractor(self, sortingextractor: SortingExtractor):
        self.nwbfile = NwbSortingExtractor.read_sorting(sortingextractor, self.nwbfile)

    def add_recordingextractor(self, recordingextractor: RecordingExtractor):
        self.nwbfile = NwbSortingExtractor.read_recording(recordingextractor, self.nwbfile)
