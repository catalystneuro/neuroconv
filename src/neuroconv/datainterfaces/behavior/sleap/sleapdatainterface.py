"""Author: Heberto Mayorquin."""
from typing import Optional
from pathlib import Path

from pynwb.file import NWBFile

from ....basedatainterface import BaseDataInterface
from ....tools.nwb_helpers import make_or_load_nwbfile
from ....tools import get_package
from ....utils import dict_deep_update, FilePathType, OptionalFilePathType


class SLEAPInterface(BaseDataInterface):
    """Data interface for SLEAP datasets."""

    def __init__(
        self,
        file_path: FilePathType,
        verbose: bool = True,
    ):
        """
        Interface for writing sleap .slp files to nwb using the sleap-io library.

        Parameters
        ----------
        file_path: FilePathType
            path to the slp file output by slp.
            controls verbosity. ``True`` by default.
        """

        self.file_path = Path(file_path)
        self.sleap_io = get_package(package_name="sleap_io")

        self.verbose = verbose
        super().__init__(file_path=file_path)

    def run_conversion(
        self,
        nwbfile_path: OptionalFilePathType = None,
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

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=self.verbose
        ) as nwbfile_out:

            labels = self.sleap_io.load_slp(self.file_path)
            nwbfile_out = self.sleap_io.append_labels_data_to_nwb(labels, nwbfile_out)
