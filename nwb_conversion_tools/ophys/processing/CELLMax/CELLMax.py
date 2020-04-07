from h5py import File
from pynwb.ophys import Fluorescence
from nwb_conversion_tools.ophys.processing.ophys_processing2NWB import OphysProcessing2NWB

import numpy as np


class CellMax2NWB(OphysProcessing2NWB):

    def __init__(self, nwbfile, from_path,
                 emission_lambda=np.nan,
                 excitation_lambda=np.nan,
                 indicator='unknown',
                 location='unknown',
                 add_all=True):
        self.from_path = from_path
        frame_rate = self.get_frame_rate()
        super(CellMax2NWB, self).__init__(nwbfile,
                                          emission_lambda=emission_lambda,
                                          excitation_lambda=excitation_lambda,
                                          frame_rate=frame_rate,
                                          indicator=indicator,
                                          location=location)

        if add_all:
            self.add_all()

    def add_all(self):
        self.add_img_masks()
        self.add_fluorescence_traces()

    def add_img_masks(self):
        with File(self.from_path, 'r') as f:
            img_masks = f['emAnalysisOutput/cellImages'][:]
        for img_mask in img_masks:
            self.ps.add_roi(image_mask=img_mask)

    def add_fluorescence_traces(self, roi_ids=None, region_label=None):
        if roi_ids is None:
            roi_ids = list(range(len(self.ps)))
            region_label = 'all ROIs'

        rt_region = self.ps.create_roi_table_region(region_label, region=roi_ids)

        frame_rate = self.get_frame_rate()

        with File(self.from_path, 'r') as f:
            data = f['emAnalysisOutput/cellTraces'][:]

        fl = Fluorescence()
        self.ophys_mod.add_data_interface(fl)
        fl.create_roi_response_series('RoiResponseSeries', data, 'lumens', rt_region, rate=frame_rate)

    def get_frame_rate(self):
        with File(self.from_path, 'r') as f:
            frame_rate = float(f['emAnalysisOutput/eventOptions/framerate'][:])

        return frame_rate







