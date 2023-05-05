from pathlib import Path
from typing import Optional

import numpy as np
from pynwb.file import NWBFile

from .sleap_utils import extract_timestamps
from ....basedatainterface import BaseDataInterface
from ....tools import get_package
from ....tools.nwb_helpers import make_or_load_nwbfile
from ....utils import FilePathType, dict_deep_update


class SLEAPInterface(BaseDataInterface):
    """Data interface for SLEAP datasets."""

    def __init__(
        self,
        file_path: FilePathType,
        video_file_path: Optional[FilePathType] = None,
        verbose: bool = True,
        frames_per_second: Optional[float] = None,
    ):
        """
        Interface for writing sleap .slp files to nwb using the sleap-io library.

        Parameters
        ----------
        file_path : FilePathType
            Path to the .slp file (the output of sleap)
        verbose : bool, default: True
            controls verbosity. ``True`` by default.
        video_file_path : FilePath, optional
            The file path of the video for extracting timestamps.
        frames_per_second : float, optional
            The frames per second (fps) or sampling rate of the video.
        """
        self.file_path = Path(file_path)
        self.sleap_io = get_package(package_name="sleap_io")
        self.video_file_path = video_file_path
        self.video_sample_rate = frames_per_second
        self.verbose = verbose
        self._timestamps = None
        super().__init__(file_path=file_path)

    def get_original_timestamps(self) -> np.ndarray:
        if self.video_file_path is None:
            raise ValueError(
                "Unable to fetch the original timestamps from the video! "
                "Please specify 'video_file_path' when initializing the interface."
            )
        return np.array(extract_timestamps(self.video_file_path))

    def get_timestamps(self) -> np.ndarray:
        timestamps = self._timestamps if self._timestamps is not None else self.get_original_timestamps()
        return timestamps

    def align_timestamps(self, aligned_timestamps: np.ndarray):
        self._timestamps = aligned_timestamps

    def run_conversion(
        self,
        nwbfile_path: Optional[FilePathType] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
    ):
        """
        Conversion from DLC output files to nwb. Derived from sleap-io library.

        Parameters
        ----------
        nwbfile_path: FilePathType
            Path for where to write or load (if overwrite=False) the NWBFile.
            If specified, this context will always write to this location.
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict
            metadata info for constructing the nwb file (optional).
        overwrite: bool, optional
            Whether or not to overwrite the NWBFile if one exists at the nwbfile_path.
        """
        base_metadata = self.get_metadata()
        metadata = dict_deep_update(base_metadata, metadata)

        pose_estimation_metadata = dict()
        if self.video_file_path or self._timestamps:
            video_timestamps = self.get_timestamps()
            pose_estimation_metadata.update(video_timestamps=video_timestamps)

        if self.video_sample_rate:
            pose_estimation_metadata.update(video_sample_rate=self.video_sample_rate)

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=self.verbose
        ) as nwbfile_out:
            labels = self.sleap_io.load_slp(self.file_path)
            nwbfile_out = self.sleap_io.io.nwb.append_nwb_data(
                labels=labels, nwbfile=nwbfile_out, pose_estimation_metadata=pose_estimation_metadata
            )
