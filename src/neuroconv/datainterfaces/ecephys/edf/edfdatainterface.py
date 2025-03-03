from typing import Optional

from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....tools import get_package


class EDFRecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface class for converting European Data Format (EDF) data using the
    :py:class:`~spikeinterface.extractors.EDFRecordingExtractor`.

    Not supported for Python 3.8 and 3.9 on M1 macs.
    """

    display_name = "EDF Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("European Data Format",)
    associated_suffixes = (".edf",)
    info = "Interface for European Data Format (EDF) recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Compile input schema for the EDF recording extractor.

        Returns
        -------
        dict
            The schema dictionary describing the source data requirements
            for the EDF recording interface.
        """
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .edf file."
        return source_schema

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        """
        Convert source data to keyword arguments for the EDF extractor.

        Parameters
        ----------
        source_data : dict
            Dictionary containing source data parameters.

        Returns
        -------
        dict
            Dictionary containing keyword arguments for the EDF extractor.
        """
        extractor_kwargs = source_data.copy()
        extractor_kwargs.pop("channels_to_skip")
        extractor_kwargs["all_annotations"] = True
        extractor_kwargs["use_names_as_ids"] = True

        return extractor_kwargs

    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
        channels_to_skip: Optional[list] = None,
    ):
        """
        Load and prepare data for EDF.
        Currently, only continuous EDF+ files (EDF+C) and original EDF files (EDF) are supported


        Parameters
        ----------
        file_path : str or Path
            Path to the edf file
        verbose : bool, default: Falseeeeee
            Allows verbose.
        es_key : str, default: "ElectricalSeries"
            Key for the ElectricalSeries metadata
        channels_to_skip : list, default: None
            Channels to skip when adding the data to the nwbfile. These parameter can be used to skip non-neural
            channels that are present in the EDF file.

        """
        get_package(
            package_name="pyedflib",
            excluded_platforms_and_python_versions=dict(darwin=dict(arm=["3.9"])),
        )

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key, channels_to_skip=channels_to_skip)
        self.edf_header = self.recording_extractor.neo_reader.edf_header

        # We remove the channels that are not neural
        if channels_to_skip:
            self.recording_extractor = self.recording_extractor.remove_channels(remove_channel_ids=channels_to_skip)

    def extract_nwb_file_metadata(self) -> dict:
        """
        Extract NWBFile metadata from the EDF header.

        Returns
        -------
        dict
            Dictionary containing NWBFile metadata extracted from the EDF header,
            including session_start_time and experimenter if available.
        """
        nwbfile_metadata = dict(
            session_start_time=self.edf_header["startdate"],
            experimenter=self.edf_header["technician"],
        )

        # Filter empty values
        nwbfile_metadata = {property: value for property, value in nwbfile_metadata.items() if value}

        return nwbfile_metadata

    def extract_subject_metadata(self) -> dict:
        """
        Extract subject metadata from the EDF header.

        Returns
        -------
        dict
            Dictionary containing subject metadata extracted from the EDF header,
            including subject_id and date_of_birth if available.
        """
        subject_metadata = dict(
            subject_id=self.edf_header["patientcode"],
            date_of_birth=self.edf_header["birthdate"],
        )

        # Filter empty values
        subject_metadata = {property: value for property, value in subject_metadata.items() if value}

        return subject_metadata

    def get_metadata(self) -> dict:
        """
        Get metadata for the EDF recording.

        Retrieves and organizes metadata from the EDF recording,
        including NWBFile and Subject metadata extracted from the EDF header.

        Returns
        -------
        dict
            Dictionary containing metadata for the EDF recording,
            including NWBFile and Subject sections with information
            extracted from the EDF header.
        """
        metadata = super().get_metadata()
        nwbfile_metadata = self.extract_nwb_file_metadata()
        metadata["NWBFile"].update(nwbfile_metadata)

        subject_metadata = self.extract_subject_metadata()
        metadata.get("Subject", dict()).update(subject_metadata)

        return metadata
