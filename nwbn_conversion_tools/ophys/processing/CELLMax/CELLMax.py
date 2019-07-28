from h5py import File
import numpy as np

from pynwb.ophys import Fluorescence

from nwbn_conversion_tools.ophys.processing.ophys_processing2NWB import OphysProcessing2NWB


class CellMax2NWB(OphysProcessing2NWB):

    def __init__(self, nwbfile, from_path):
        super(CellMax2NWB, self).__init__(nwbfile)
        self.from_path = from_path

    def add_img_masks(self):
        with File(self.from_path, 'r') as f:
            img_masks = f['emAnalysisOutput/cellImages'][:]
        for img_mask in img_masks:
            self.ps.add_roi(image_mask=img_mask)

    def add_fluorescence_traces(self, roi_ids=None, region_label=None):
        if roi_ids is None:
            roi_ids = np.arange(len(self.ps))
            region_label = 'all ROIs'

        rt_region = self.ps.create_roi_table_region(region_label, region=roi_ids)

        frame_rate = self.get_frame_rate()

        with File(self.from_path, 'r') as f:
            data = f['emAnalysisOutput/cellTraces'][:]

        fl = Fluorescence()
        self.ophys_mod.add_data_interface(fl)
        fl.create_roi_response_series('my_rrs', data, 'lumens', rt_region, rate=frame_rate)

    def get_frame_rate(self):
        with File(self.from_path, 'r') as f:
            frame_rate = f['emAnalysisOutput/eventOptions/framerate'][:]

        return frame_rate







