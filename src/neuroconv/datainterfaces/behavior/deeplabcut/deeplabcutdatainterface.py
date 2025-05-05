from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface


class DeepLabCutInterface(BaseTemporalAlignmentInterface):
    """Data interface for DeepLabCut datasets."""

    display_name = "DeepLabCut"
    keywords = ("DLC", "DeepLabCut", "pose estimation", "behavior")
    associated_suffixes = (".h5", ".csv")
    info = "Interface for handling data from DeepLabCut."

    _timestamps = None

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the file output by dlc (.h5 or .csv)."
        source_schema["properties"]["config_file_path"]["description"] = "Path to .yml config file."
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        config_file_path: FilePath | None = None,
        individual_name: str = "ind1",
        subject_id: str | None = None,
        verbose: bool = False,
    ):
        """
        Interface for writing DLC's output files to nwb using dlc2nwb.

        Parameters
        ----------
        file_path : FilePath
            Path to the file output by dlc (.h5 or .csv).
        config_file_path : FilePath, optional
            Path to .yml config file
        individual_name : str, default: "ind1"
            The name of the individual in the DeepLabCut output file.
        subject_id : str, optional
            The ID to use for the subject in the NWB file. If None, defaults to the individual_name.
        verbose: bool, default: False
            Controls verbosity.
        """
        # This import is to assure that the ndx_pose is in the global namespace when an pynwb.io object is created
        from importlib.metadata import version

        import ndx_pose  # noqa: F401
        from packaging import version as version_parse

        ndx_pose_version = version("ndx-pose")
        if version_parse.parse(ndx_pose_version) < version_parse.parse("0.2.0"):
            raise ImportError(
                "DeepLabCut interface requires ndx-pose version 0.2.0 or later. "
                f"Found version {ndx_pose_version}. Please upgrade: "
                "pip install 'ndx-pose>=0.2.0'"
            )

        from ._dlc_utils import _read_config

        file_path = Path(file_path)
        suffix_is_valid = ".h5" in file_path.suffixes or ".csv" in file_path.suffixes
        if not "DLC" in file_path.stem or not suffix_is_valid:
            raise IOError("The file passed in is not a valid DeepLabCut output data file.")

        self.config_dict = dict()
        if config_file_path is not None:
            self.config_dict = _read_config(config_file_path=config_file_path)
        self.individual_name = individual_name
        self.subject_id = subject_id if subject_id is not None else individual_name
        self.verbose = verbose
        self.pose_estimation_container_kwargs = dict()

        super().__init__(file_path=file_path, config_file_path=config_file_path)

    def get_metadata(self):
        metadata = super().get_metadata()

        if self.config_dict:
            metadata["NWBFile"].update(
                session_description=self.config_dict["Task"],
                experimenter=[self.config_dict["scorer"]],
            )

        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to retrieve the original unaltered timestamps for this interface! "
            "Define the `get_original_timestamps` method for this interface."
        )

    def get_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to retrieve timestamps for this interface! Define the `get_timestamps` method for this interface."
        )

    def set_aligned_timestamps(self, aligned_timestamps: list | np.ndarray):
        """
        Set aligned timestamps vector for DLC data with user defined timestamps

        Parameters
        ----------
        aligned_timestamps : list, np.ndarray
            A timestamps vector.
        """
        self._timestamps = np.asarray(aligned_timestamps)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        *,
        metadata: dict | None = None,
        container_name: str = "PoseEstimationDeepLabCut",
    ):
        """
        Conversion from DLC output files to nwb. Derived from dlc2nwb library.

        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict
            metadata info for constructing the nwb file (optional).
        container_name: str, default: "PoseEstimationDeepLabCut"
            name of the PoseEstimation container in the nwb

        """
        from ._dlc_utils import _add_subject_to_nwbfile

        self.pose_estimation_container_kwargs["name"] = container_name

        _add_subject_to_nwbfile(
            nwbfile=nwbfile,
            file_path=str(self.source_data["file_path"]),
            individual_name=self.individual_name,
            subject_id=self.subject_id,
            config_file=self.source_data["config_file_path"],
            timestamps=self._timestamps,
            pose_estimation_container_kwargs=self.pose_estimation_container_kwargs,
        )
