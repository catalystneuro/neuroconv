from pynwb.ophys import OpticalChannel, ImageSegmentation
from pynwb.device import Device

from nwb_conversion_tools.base import Convert2NWB
import numpy as np


class OphysProcessing2NWB(Convert2NWB):

    def __init__(self, nwbfile, emission_lambda=np.nan,
                 excitation_lambda=np.nan,
                 frame_rate=np.nan,
                 indicator='unknown',
                 location='unknown'):

        super(OphysProcessing2NWB, self).__init__(nwbfile)

        device = Device('microscope')
        self.nwbfile.add_device(device)
        optical_channel = OpticalChannel('OpticalChannel', 'description',
                                         emission_lambda=emission_lambda)
        imaging_plane = self.nwbfile.create_imaging_plane(
            'ImagingPlane', optical_channel,
            description='description',
            device=device,
            excitation_lambda=excitation_lambda,
            imaging_rate=frame_rate,
            indicator=indicator,
            location=location
        )

        self.ophys_mod = self.nwbfile.create_processing_module('ophys', 'contains optical physiology processed data')
        img_seg = ImageSegmentation()
        self.ophys_mod.add_data_interface(img_seg)
        self.ps = img_seg.create_plane_segmentation(
            'output from segmenting my favorite imaging plane', imaging_plane, 'PlaneSegmentation')
