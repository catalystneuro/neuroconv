from pathlib import Path
from typing import Optional, Union

import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface


class DeepLabCutInterface(BaseTemporalAlignmentInterface):
    """Data interface for DeepLabCut datasets."""

    display_name = "DeepLabCut"
    keywords = ("DLC",)
    associated_suffixes = (".h5",)
    info = "Interface for handling data from DeepLabCut."

    _timestamps = None

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .h5 file output by dlc."
        source_schema["properties"]["config_file_path"]["description"] = "Path to .yml config file"
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        config_file_path: Optional[FilePath] = None,
        subject_name: str = "ind1",
        verbose: bool = True,
    ):
        """
        Interface for writing DLC's h5 files to nwb using dlc2nwb.

        Parameters
        ----------
        file_path : FilePath
            path to the h5 file output by dlc.
        config_file_path : FilePath, optional
            path to .yml config file
        subject_name : str, default: "ind1"
            the name of the subject for which the :py:class:`~pynwb.file.NWBFile` is to be created.
        verbose: bool, default: True
            controls verbosity.
        """
        from ._dlc_utils import _read_config

        file_path = Path(file_path)
        if "DLC" not in file_path.stem or ".h5" not in file_path.suffixes:
            raise IOError("The file passed in is not a DeepLabCut h5 data file.")

        self.config_dict = dict()
        if config_file_path is not None:
            self.config_dict = _read_config(config_file_path=config_file_path)
        self.subject_name = subject_name
        self.verbose = verbose
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

    def set_aligned_timestamps(self, aligned_timestamps: Union[list, np.ndarray]):
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
        metadata: Optional[dict] = None,
        container_name: str = "PoseEstimation",
    ):
        """
        Conversion from DLC output files to nwb. Derived from dlc2nwb library.

        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict
            metadata info for constructing the nwb file (optional).
        """
        from ._dlc_utils import add_subject_to_nwbfile

        add_subject_to_nwbfile(
            nwbfile=nwbfile,
            h5file=str(self.source_data["file_path"]),
            individual_name=self.subject_name,
            config_file=self.source_data["config_file_path"],
            timestamps=self._timestamps,
            pose_estimation_container_kwargs=dict(name=container_name),
        )
