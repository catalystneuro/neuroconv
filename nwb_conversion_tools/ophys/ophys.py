import numpy as np

from pynwb.ophys import OpticalChannel, ImageSegmentation
from pynwb.device import Device

from nwb_conversion_tools.converter import NWBConverter


class OphysNWBConverter(NWBConverter):

    def __init__(self, metadata, nwbfile=None, source_paths=None):

        super(OphysNWBConverter, self).__init__(metadata, nwbfile=nwbfile, source_paths=source_paths)

        device = Device('microscope')
        self.nwbfile.add_device(device)

        self.imaging_plane = self.add_imaging_plane()
        self.ophys_mod = self.nwbfile.create_processing_module('ophys', 'contains optical physiology processed data')

    def create_optical_channel(self, metadata=None):

        input_kwargs = dict(
            name='OpticalChannel',
            description='no description',
            emission_lambda=np.nan
        )

        if metadata is None and 'Ophys' in self.metadata and 'OpticalChannel' in self.metadata['Ophys']:
            metadata = self.metadata['Ophys']['OpticalChannel']

        input_kwargs.update(metadata)

        return OpticalChannel(**input_kwargs)

    def add_imaging_plane(self, metadata=None, optical_channel=None):

        if optical_channel is None:
            optical_channel = self.create_optical_channel()

        input_kwargs = dict(
            name='ImagingPlane',
            optical_channel=optical_channel,
            description='no description',
            device=self.devices[0],
            excitation_lambda=np.nan,
            indicator='unknown',
            location='unknown'
        )

        if metadata is None and 'Ophys' in self.metadata and 'ImagingPlane' in self.metadata['Ophys']:
            input_kwargs.update(self.metadata['Ophys']['ImagingPlane'])

        return self.nwbfile.create_imaging_plane(**input_kwargs)


class ProcessedOphysNWBConverter(OphysNWBConverter):

    def __init__(self, metadata, nwbfile=None, source_paths=None):
        super(ProcessedOphysNWBConverter, self).__init__(metadata, nwbfile=nwbfile, source_paths=source_paths)

        self.image_segmentation = ImageSegmentation()
        self.ophys_mod.add_data_interface(self.image_segmentation)

    def create_plane_segmentation(self, metadata):

        input_kwargs = dict(
            name='PlaneSegmentation',
            description='output from segmenting my favorite imaging plane',
            imaging_plane=self.imaging_plane
        )

        if metadata:
            input_kwargs.update(metadata)
        elif 'Ophys' in self.metadata and 'PlaneSegmentation' in self.metadata['Ophys']:
            input_kwargs.update(self.metadata['Ophys']['PlaneSegmentation'])

        self.plane_segmentation = self.image_segmentation.create_plane_segmentation(**input_kwargs)




