from pathlib import Path
from typing import Optional

import numpy as np
from pynwb.file import NWBFile

from .sleap_utils import extract_timestamps
from ....basedatainterface import BaseDataInterface
from ....tools import get_package
from ....utils import FilePathType, OptionalFilePathType, dict_deep_update


class SLEAPInterface(BaseDataInterface):
    """Data interface for SLEAP datasets."""

    def __init__(
        self,
        file_path: FilePathType,
        video_file_path: OptionalFilePathType = None,
        verbose: bool = True,
        frames_per_second: Optional[float] = None,
    ):
        """
        Interface for writing sleap .slp files to nwb using the sleap-io library.

        Parameters
        ----------
        file_path: FilePathType
            Path to the .slp file (the output of sleap)
        verbose: Bool
            controls verbosity. ``True`` by default.
        video_file_path: OptionalFilePathType
            The file path of the video for extracting timestamps
        frames_per_second: float
            The frames per second (fps) or sampling rate of the video
        """

        self.file_path = Path(file_path)
        self.sleap_io = get_package(package_name="sleap_io")
        self.video_file_path = video_file_path
        self.video_sample_rate = frames_per_second
        self.verbose = verbose
        super().__init__(file_path=file_path)

    def get_original_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to retrieve the original unaltered timestamps for this interface! "
            "Define the `get_original_timestamps` method for this interface."
        )

    def get_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to retrieve timestamps for this interface! Define the `get_timestamps` method for this interface."
        )

    def align_timestamps(self, aligned_timestamps: np.ndarray):
        raise NotImplementedError(
            "The protocol for synchronizing the timestamps of this interface has not been specified!"
        )

    def _run_conversion(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
    ):
        """
        Conversion from DLC output files to nwb. Derived from sleap-io library.

        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict
            metadata info for constructing the nwb file (optional).
        """

        base_metadata = self.get_metadata()
        metadata = dict_deep_update(base_metadata, metadata)

        pose_estimation_metadata = dict()
        if self.video_file_path:
            video_timestamps = extract_timestamps(self.video_file_path)
            pose_estimation_metadata.update(video_timestamps=video_timestamps)

        if self.video_sample_rate:
            pose_estimation_metadata.update(video_sample_rate=self.video_sample_rate)

        labels = self.sleap_io.load_slp(self.file_path)
        nwbfile = self.sleap_io.io.nwb.append_nwb_data(
            labels=labels, nwbfile=nwbfile, pose_estimation_metadata=pose_estimation_metadata
        )
        return nwbfile
