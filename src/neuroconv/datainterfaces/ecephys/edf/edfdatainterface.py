"""Authors: Heberto Mayorquin"""
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface

from ....tools import get_package
from ....utils.types import FilePathType


class EDFRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting European Data Format (EDF) data
    using the :py:class:`~spikeinterface.extractors.EDFRecordingExtractor`."""

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """
        Load and prepare data for EDF
        Currently only continuous EDF+ files (EDF+C) and original EDF files (EDF) are supported


        Parameters
        ----------
        folder_path: str or Path
            Path to the edf file
        verbose: bool, True by default
            Allows verbose.
        """
        _ = get_package(package_name="pyedflib")

        super().__init__(file_path=file_path, verbose=verbose)
        self.edf_header = self.recording_extractor.neo_reader.edf_header

    def extract_nwb_file_metadata(self):

        nwbfile_metadata = dict(
            session_start_time=self.edf_header["startdate"],
            experimenter=self.edf_header["technician"],
        )

        # Filter empty values
        nwbfile_metadata = {property: value for property, value in nwbfile_metadata.items() if value}

        return nwbfile_metadata

    def extract_subject_metadata(self):

        subject_metadata = dict(
            subject_id=self.edf_header["patientcode"],
            date_of_birth=self.edf_header["birthdate"],
        )

        # Filfter empty values
        subject_metadata = {property: value for property, value in subject_metadata.items() if value}

        return subject_metadata

    def get_metadata(self):

        metadata = super().get_metadata()
        nwbfile_metadata = self.extract_nwb_file_metadata()
        metadata["NWBFile"].update(nwbfile_metadata)

        subject_metadata = self.extract_subject_metadata()
        metadata.get("Subject", dict()).update(subject_metadata)

        return metadata
