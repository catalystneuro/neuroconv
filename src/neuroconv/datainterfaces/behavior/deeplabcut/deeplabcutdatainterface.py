from pathlib import Path
from typing import Optional

import numpy as np
from pynwb.file import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_package
from ....utils import FilePathType


def write_subject_to_nwb(nwbfile: NWBFile, h5file: FilePathType, individual_name: str, config_file: FilePathType):
    """
    Given, subject name, write h5file to an existing nwbfile.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        The in-memory nwbfile object to which the subject specific pose estimation series will be added.
    h5file : str or path
        Path to the DeepLabCut .h5 output file.
    individual_name : str
        Name of the subject (whose pose is predicted) for single-animal DLC project.
        For multi-animal projects, the names from the DLC project will be used directly.
    config_file : str or path
        Path to a project config.yaml file

    Returns
    -------
    nwbfile : pynwb.NWBFile
        nwbfile with pes written in the behavior module
    """
    dlc2nwb = get_package(package_name="dlc2nwb")

    scorer, df, video, paf_graph, timestamps, _ = dlc2nwb.utils._get_pes_args(config_file, h5file, individual_name)
    df_animal = df.groupby(level="individuals", axis=1).get_group(individual_name)
    return dlc2nwb.utils._write_pes_to_nwbfile(
        nwbfile, individual_name, df_animal, scorer, video, paf_graph, timestamps, exclude_nans=False
    )


class DeepLabCutInterface(BaseTemporalAlignmentInterface):
    """Data interface for DeepLabCut datasets."""

    keywords = BaseTemporalAlignmentInterface.keywords + ["DLC"]

    def __init__(
        self,
        file_path: FilePathType,
        config_file_path: FilePathType,
        subject_name: str = "ind1",
        verbose: bool = True,
    ):
        """
        Interface for writing DLC's h5 files to nwb using dlc2nwb.

        Parameters
        ----------
        file_path : FilePathType
            path to the h5 file output by dlc.
        config_file_path : FilePathType
            path to .yml config file
        subject_name : str, default: "ind1"
            the name of the subject for which the :py:class:`~pynwb.file.NWBFile` is to be created.
        verbose: bool, default: True
            controls verbosity.
        """
        dlc2nwb = get_package(package_name="dlc2nwb")

        file_path = Path(file_path)
        if "DLC" not in file_path.stem or ".h5" not in file_path.suffixes:
            raise IOError("The file passed in is not a DeepLabCut h5 data file.")

        self._config_file = dlc2nwb.utils.read_config(config_file_path)
        self.subject_name = subject_name
        self.verbose = verbose
        super().__init__(file_path=file_path, config_file_path=config_file_path)

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata["NWBFile"].update(
            session_description=self._config_file["Task"],
            experimenter=[self._config_file["scorer"]],
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

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        raise NotImplementedError(
            "The protocol for synchronizing the timestamps of this interface has not been specified!"
        )

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
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

        write_subject_to_nwb(
            nwbfile=nwbfile,
            h5file=str(self.source_data["file_path"]),
            individual_name=self.subject_name,
            config_file=str(self.source_data["config_file_path"]),
        )
