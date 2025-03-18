from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from .sleap_utils import extract_timestamps
from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_package


class SLEAPInterface(BaseTemporalAlignmentInterface):
    """Data interface for SLEAP datasets."""

    display_name = "SLEAP"
    keywords = ("pose estimation", "tracking", "video")
    associated_suffixes = (".slp", ".mp4")
    info = "Interface for SLEAP pose estimation datasets."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .slp file (the output of sleap)"
        source_schema["properties"]["video_file_path"][
            "description"
        ] = "Path of the video for extracting timestamps (optional)."
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        video_file_path: Optional[FilePath] = None,
        verbose: bool = False,
        frames_per_second: Optional[float] = None,
    ):
        """
        Interface for writing sleap .slp files to nwb using the sleap-io library.

        Parameters
        ----------
        file_path : FilePath
            Path to the .slp file (the output of sleap)
        verbose : bool, default: Falsee
            controls verbosity. ``True`` by default.
        video_file_path : FilePath, optional
            The file path of the video for extracting timestamps.
        frames_per_second : float, optional
            The frames per second (fps) or sampling rate of the video.
        """

        # This import is to assure that the ndx_pose is in the global namespace when an pynwb.io object is created
        # For more detail, see https://github.com/rly/ndx-pose/issues/36
        from importlib.metadata import version

        import ndx_pose  # noqa: F401
        from packaging import version as version_parse

        ndx_pose_version = version("ndx-pose")

        # TODO: remove after this is merged https://github.com/talmolab/sleap-io/pull/143 and released
        if version_parse.parse(ndx_pose_version) != version_parse.parse("0.1.1"):
            raise ImportError(
                "SLEAP interface requires ndx-pose version 0.1.1. "
                f"Found version {ndx_pose_version}. Please install the required version: "
                "pip install 'ndx-pose==0.1.1'"
            )

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

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        self._timestamps = aligned_timestamps

    def add_to_nwbfile(
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

        pose_estimation_metadata = dict()
        if self.video_file_path or self._timestamps:
            video_timestamps = self.get_timestamps()
            pose_estimation_metadata.update(video_timestamps=video_timestamps)

        if self.video_sample_rate:
            pose_estimation_metadata.update(video_sample_rate=self.video_sample_rate)

        labels = self.sleap_io.load_slp(self.file_path)
        self.sleap_io.io.nwb.append_nwb_data(
            labels=labels, nwbfile=nwbfile, pose_estimation_metadata=pose_estimation_metadata
        )
