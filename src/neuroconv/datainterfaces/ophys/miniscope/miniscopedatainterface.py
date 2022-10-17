import os
from typing import Optional
from glob import glob

from natsort import natsorted
from pynwb.file import NWBFile
from pynwb.image import ImageSeries

from ....basedatainterface import BaseDataInterface
from ....tools.nwb_helpers import make_or_load_nwbfile
from ....utils import FolderPathType


class MiniscopeImagingInterface(BaseDataInterface):
    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)

    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        verbose: bool = False,
    ):
        from ndx_miniscope import read_settings, read_notes, read_miniscope_timestamps, get_starting_frames

        data_dir = self.source_data["folder_path"]
        miniscope = read_settings()
        annotations = read_notes(data_dir)

        ms_files = natsorted(glob(os.path.join(data_dir, "msCam*.avi")))
        behav_files = natsorted(glob(os.path.join(data_dir, "behavCam*.avi")))

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
        ) as nwb:

            nwb.add_device(miniscope)
            if annotations is not None:
                nwb.add_acquisition(annotations)

            nwb.add_acquisition(
                ImageSeries(
                    name="OnePhotonSeries",
                    format="external",
                    external_file=[os.path.split(x)[1] for x in ms_files],
                    timestamps=read_miniscope_timestamps(data_dir),
                    starting_frame=get_starting_frames(ms_files),
                )
            )

            nwb.add_acquisition(
                ImageSeries(
                    name="behaviorCam",
                    format="external",
                    external_file=[os.path.split(x)[1] for x in behav_files],
                    timestamps=read_miniscope_timestamps(data_dir, cam_num=2),
                    starting_frame=get_starting_frames(behav_files),
                )
            )
