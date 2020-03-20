import uuid
from typing import Dict

from pynwb import NWBFile, NWBHDF5IO
from pynwb.file import Subject

from spikeextractors import SortingExtractor, RecordingExtractor, NwbSortingExtractor, NwbRecordingExtractor


class NWBConverter:
    """
    Common conversion code factored out so it can be used by multiple conversion projects
    """

    def __init__(self, metadata, nwbfile=None):
        """

        Parameters
        ----------
        metadata: dict
        nwbfile: pynwb.NWBFile
        """
        if nwbfile is None:
            self.create_nwbfile(metadata['NWBFile'])
        else:
            self.nwbfile = nwbfile

        if 'Subject' in metadata:
            self.create_subject(metadata['Subject'])

        # add devices
        self.devices = dict()
        for domain in ('Icephys', 'Ecephys', 'Ophys'):
            if domain in metadata and 'Device' in metadata[domain]:
                self.devices.update(self.create_devices(metadata[domain]['Device']))

        if 'Icephys' in metadata and ('Electrode' in metadata['Icephys']):
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

    def create_devices(self, device_meta) -> Dict:
        """
        Use metadata to generate device object(s) in the NWBFile

        Parameters
        ----------
        device_meta: list or dict

        Returns
        -------
        dict

        """

        if isinstance(device_meta, list):
            devices = dict()
            [devices.update(self.create_devices(idevice_meta)) for idevice_meta in device_meta]
            return devices
        else:
            if 'tag' in device_meta:
                key = device_meta['tag']
            else:
                key = device_meta['name']
            return {key: self.nwbfile.create_device(**device_meta)}

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
