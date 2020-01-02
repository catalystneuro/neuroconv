import uuid

from pynwb import NWBFile, NWBHDF5IO
from pynwb.file import Subject


class NWBConverter:

    def __init__(self, metadata, nwbfile=None):
        """

        Parameters
        ----------
        metadata: dict
        nwbfile: pynwb.NWBFile
        """
        if nwbfile is None:
            nwbfile_args = dict(
                identifier=str(uuid.uuid4()),
            )
            nwbfile_args.update(metadata['NWBFile'])
            self.nwbfile = NWBFile(**nwbfile_args)
        else:
            self.nwbfile = nwbfile

        if 'Subject' in metadata:
            self.nwbfile.subject = Subject(**metadata['Subject'])

        # add devices
        self.devices = dict()
        for domain in ('Icephys', 'Ecephys', 'Ophys'):
            if domain in metadata and 'Device' in metadata[domain]:
                self.devices.update(self.create_devices(metadata[domain]['Device']))

        if 'Icephys' in metadata and 'Electrodes' in metadata['Icephys']:
            self.elecs = self.create_icephys_elecs(metadata['Icephys']['Electrodes'])

    def create_devices(self, device_meta):
        devices = dict()
        if isinstance(device_meta, list):
            for idevice_meta in device_meta:
                if 'tag' in device_meta:
                    devices[idevice_meta['tag']] = self.nwbfile.create_device(**idevice_meta)
        else:
            devices[str(uuid.uuid4())] = self.nwbfile.create_device(**device_meta)
        return devices

    def create_icephys_elecs(self, elec_meta):
        if isinstance(elec_meta, list):
            for ielec_meta in elec_meta:
                if ielec_meta['device'] in self.devices:
                    device = self.devices[ielec_meta['device']]
                else:
                    raise ValueError('device not found for icephys electrode {}'.format(ielec_meta['name']))
                self.nwbfile.create_ic_electrode(device=device, **ielec_meta)
        else:
            if len(list(self.devices)) == 1:
                self.nwbfile.create_ic_electrode(device=list(self.devices.values())[0], **elec_meta)
            else:
                raise ValueError('must specify device for icephys electrode {}'.format(elec_meta['name']))

    def save(self, to_path, read_check=True):
        """

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
        """Check if processing module exists. If not, create it. Then return module

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
