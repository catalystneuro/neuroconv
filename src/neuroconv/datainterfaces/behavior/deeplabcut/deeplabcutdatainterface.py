"""Authors: Saksham Sharda, Cody Baker, Ben Dichter, Heberto Mayorquin."""
from typing import Optional
from pathlib import Path

from pynwb.file import NWBFile

from ....basedatainterface import BaseDataInterface
from ....tools.nwb_helpers import make_or_load_nwbfile
from ....tools import get_package
from ....utils import dict_deep_update, FilePathType, OptionalFilePathType


class DeepLabCutInterface(BaseDataInterface):
    """Data interface for DeepLabCut datasets."""

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
        file_path: FilePathType
            path to the h5 file output by dlc.
        config_file_path: FilePathType
            path to .yml config file
        subject_name: str
            the name of the subject for which the :py:class:`~pynwb.file.NWBFile` is to be created.
        verbose: bool
            controls verbosity. ``True`` by default.
        """
        dlc2nwb = get_package(package_name="dlc2nwb")

        file_path = Path(file_path)
        if "DLC" not in file_path.stem or ".h5" not in file_path.suffixes:
            raise IOError("The file passed in is not a DeepLabCut h5 data file.")

        self._config_file = dlc2nwb.utils.auxiliaryfunctions.read_config(config_file_path)
        self.subject_name = subject_name
        self.verbose = verbose
        super().__init__(file_path=file_path, config_file_path=config_file_path)

    def get_metadata(self):
        metadata = dict(
            NWBFile=dict(session_description=self._config_file["Task"], experimenter=[self._config_file["scorer"]]),
        )
        return metadata

    def run_conversion(
        self,
        nwbfile_path: OptionalFilePathType = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
    ):
        """
        Conversion from DLC output files to nwb. Derived from dlc2nwb library.

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
        dlc2nwb = get_package(package_name="dlc2nwb")

        base_metadata = self.get_metadata()
        metadata = dict_deep_update(base_metadata, metadata)

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=self.verbose
        ) as nwbfile_out:
            dlc2nwb.utils.write_subject_to_nwb(
                nwbfile=nwbfile_out,
                h5file=str(self.source_data["file_path"]),
                individual_name=self.subject_name,
                config_file=str(self.source_data["config_file_path"]),
            )
