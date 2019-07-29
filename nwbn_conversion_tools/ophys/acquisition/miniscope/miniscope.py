import os
from ndx_miniscope import read_settings, read_notes, load_miniscope_timestamps
from pynwb.image import ImageSeries
from natsort import natsorted
from glob import glob

from nwbn_conversion_tools.ophys.acquisition.acquisition2NWB import Acquisition2NWB


class Miniscope2NWB(Acquisition2NWB):

    def __init__(self, nwbfile, from_path=None):
        super(Miniscope2NWB).__init__(nwbfile)
        self.from_path = from_path

    def add_microscopy(self, from_path):
        miniscope = read_settings(from_path)
        self.nwbfile.add_device(miniscope)
        annotations = read_notes(from_path)
        if annotations:
            self.nwbfile.add_acquisition(annotations)

        ms_files = [os.path.split(x)[1] for x in natsorted(glob(os.path.join(from_path, 'msCam*.avi')))]

        self.nwbfile.add_acquisition(
            ImageSeries(
                name='OnePhotonSeries',
                format='external',
                external_file=ms_files,
                timestamps=load_miniscope_timestamps(from_path),
                starting_frame=[0] * len(ms_files)
            )
        )

    def add_behavior_video(self, from_path):
        behav_files = [os.path.split(x)[1] for x in natsorted(glob(os.path.join(from_path, 'behavCam*.avi')))]

        self.nwbfile.add_acquisition(
            ImageSeries(
                name='behaviorCam',
                format='external',
                external_file=behav_files,
                timestamps=load_miniscope_timestamps(from_path, cam_num=2),
                starting_frame=[0] * len(behav_files)
            )
        )