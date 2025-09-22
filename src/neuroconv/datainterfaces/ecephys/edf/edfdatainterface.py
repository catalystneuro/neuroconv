from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....tools import get_package
from ....utils import DeepDict


class EDFRecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface class for converting European Data Format (EDF) data.

    Uses the :py:func:`~spikeinterface.extractors.read_edf` reader from SpikeInterface.

    Not supported on M1 macs.
    """

    display_name = "EDF Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("European Data Format",)
    associated_suffixes = (".edf",)
    info = "Interface for European Data Format (EDF) recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .edf file."
        return source_schema

    @staticmethod
    def get_available_channel_ids(file_path: FilePath) -> list:
        """
        Get all available channel names from an EDF file.

        Parameters
        ----------
        file_path : FilePath
            Path to the EDF file

        Returns
        -------
        list
            List of all channel names in the EDF file
        """
        from spikeinterface.extractors import read_edf

        # Load the recording to inspect channels
        recording = read_edf(file_path=file_path, all_annotations=True, use_names_as_ids=True)

        # Get all channel IDs
        channel_ids = recording.get_channel_ids()

        # Clean up to avoid dangling references
        del recording

        return channel_ids.tolist()

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:

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
        channels_to_skip: list | None = None,
    ):
        """
        Load and prepare data for EDF.
        Currently, only continuous EDF+ files (EDF+C) and original EDF files (EDF) are supported


        Parameters
        ----------
        file_path : str or Path
            Path to the edf file
        verbose : bool, default: False
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
        nwbfile_metadata = dict(
            session_start_time=self.edf_header["startdate"],
            experimenter=self.edf_header["technician"],
        )

        # Filter empty values
        nwbfile_metadata = {property: value for property, value in nwbfile_metadata.items() if value}

        return nwbfile_metadata

    def extract_subject_metadata(self) -> dict:
        subject_metadata = dict(
            subject_id=self.edf_header["patientcode"],
            date_of_birth=self.edf_header["birthdate"],
        )

        # Filter empty values
        subject_metadata = {property: value for property, value in subject_metadata.items() if value}

        return subject_metadata

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        nwbfile_metadata = self.extract_nwb_file_metadata()
        metadata["NWBFile"].update(nwbfile_metadata)

        subject_metadata = self.extract_subject_metadata()
        metadata.get("Subject", dict()).update(subject_metadata)

        return metadata
