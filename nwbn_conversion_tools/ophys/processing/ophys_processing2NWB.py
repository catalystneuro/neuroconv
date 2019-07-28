from pynwb.ophys import TwoPhotonSeries, OpticalChannel, ImageSegmentation, Fluorescence
from pynwb.device import Device

from h5py import File

from nwbn_conversion_tools.base import Convert2NWB


class OphysProcessing2NWB(Convert2NWB):

    def __init__(self, nwbfile):

        super(OphysProcessing2NWB, self).__init__(nwbfile)

        device = Device('imaging_device_1')
        self.nwbfile.add_device(device)
        optical_channel = OpticalChannel('my_optchan', 'description', 500.)
        imaging_plane = self.nwbfile.create_imaging_plane(
            'my_imgpln', optical_channel, 'a very interesting part of the brain',
            device, 600., 300., 'GFP', 'my favorite brain location')

        self.ophys_mod = self.nwbfile.create_processing_module('ophys', 'contains optical physiology processed data')
        img_seg = ImageSegmentation()
        self.ophys_mod.add_data_interface(img_seg)
        self.ps = img_seg.create_plane_segmentation(
            'output from segmenting my favorite imaging plane', imaging_plane, 'my_planeseg')
