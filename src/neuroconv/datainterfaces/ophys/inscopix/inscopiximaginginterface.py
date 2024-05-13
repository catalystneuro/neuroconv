from datetime import datetime
from imaplib import Literal

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict, FilePathType


class InscopixImagingInterface(BaseImagingExtractorInterface):
    """Interface for Inscopix imaging data."""

    display_name = "Inscopix Imaging"
    associated_suffixes = (".isxd",)
    info = "Interface for Inscopix imaging data."

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """

        Parameters
        ----------
        file_path : FilePathType
            Path to .isxd file.
        verbose : bool, default: True
        """
        super().__init__(file_path=file_path, verbose=verbose)

    def get_metadata(
        self, photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries"
    ) -> DeepDict:
        metadata = super().get_metadata(photon_series_type=photon_series_type)

        extra_props = self.imaging_extractor.movie.footer["extraProperties"]

        if extra_props["animal"]["id"]:
            metadata["Subject"]["subject_id"] = extra_props["animal"]["id"]
        if extra_props["animal"]["species"]:
            metadata["Subject"]["species"] = extra_props["animal"]["species"]
        if extra_props["animal"]["sex"]:
            metadata["Subject"]["sex"] = extra_props["animal"]["sex"].upper()
        if extra_props["animal"]["dob"]:
            metadata["Subject"]["date_of_birth"] = extra_props["animal"]["dob"]
        if extra_props["animal"]["weight"]:
            metadata["Subject"]["weight"] = str(extra_props["animal"]["weight"])

        if extra_props["date"]:
            metadata["NWBFile"]["session_start_time"] = datetime.strptime(extra_props["date"], "%Y-%m-%dT%H:%M:%S.%fZ")

        return metadata
