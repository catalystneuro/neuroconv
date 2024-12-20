"""Collection of Axona interfaces."""

from pydantic import FilePath
from pynwb import NWBFile

from .axona_utils import (
    get_eeg_sampling_frequency,
    get_position_object,
    read_all_eeg_file_lfp_data,
)
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....basedatainterface import BaseDataInterface
from ....tools.nwb_helpers import get_module
from ....utils import get_json_schema_from_method_signature


class AxonaRecordingInterface(BaseRecordingExtractorInterface):
    """
    DataInterface for converting raw Axona data using a :py:class:`~spikeinterface.extractors.AxonaRecordingExtractor`.
    """

    display_name = "Axona Recording"
    associated_suffixes = (".bin", ".set")
    info = "Interface for Axona recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to .bin file."
        return source_schema

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        extractor_kwargs = source_data.copy()
        extractor_kwargs["all_annotations"] = True

        return extractor_kwargs

    def __init__(self, file_path: FilePath, verbose: bool = False, es_key: str = "ElectricalSeries"):
        """

        Parameters
        ----------
        file_path: FilePath
            Path to .bin file.
        verbose: bool, optional, default: True
        es_key: str, default: "ElectricalSeries"
        """

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)
        self.source_data = dict(file_path=file_path, verbose=verbose)
        self.metadata_in_set_file = self.recording_extractor.neo_reader.file_parameters["set"]["file_header"]

        # Set the channel groups
        tetrode_id = self.recording_extractor.get_property("tetrode_id")
        self.recording_extractor.set_channel_groups(tetrode_id)

    def extract_nwb_file_metadata(self) -> dict:
        raw_annotations = self.recording_extractor.neo_reader.raw_annotations
        session_start_time = raw_annotations["blocks"][0]["segments"][0]["rec_datetime"]
        session_description = self.metadata_in_set_file["comments"]
        experimenter = self.metadata_in_set_file["experimenter"]

        nwbfile_metadata = dict(
            session_start_time=session_start_time,
            session_description=session_description,
            experimenter=[experimenter] if experimenter else None,  # The schema expects an array of strings
        )

        # Filter empty values
        nwbfile_metadata = {property: value for property, value in nwbfile_metadata.items() if value}

        return nwbfile_metadata

    def extract_ecephys_metadata(self) -> dict:
        unique_elec_group_names = set(self.recording_extractor.get_channel_groups())
        sw_version = self.metadata_in_set_file["sw_version"]
        description = f"Axona DacqUSB, sw_version={sw_version}"

        ecephys_metadata = dict(
            Device=[
                dict(
                    name="Axona",
                    description=description,
                    manufacturer="Axona",
                ),
            ],
            ElectrodeGroup=[
                dict(
                    name=f"{group_name}",
                    location="",  # Not sure if this should be here
                    device="Axona",
                    description=f"Group {group_name} electrodes.",
                )
                for group_name in unique_elec_group_names
            ],
        )

        return ecephys_metadata

    def get_metadata(self):
        metadata = super().get_metadata()

        nwbfile_metadata = self.extract_nwb_file_metadata()
        metadata["NWBFile"].update(nwbfile_metadata)

        ecephys_metadata = self.extract_ecephys_metadata()
        metadata["Ecephys"].update(ecephys_metadata)

        return metadata


class AxonaUnitRecordingInterface(AxonaRecordingInterface):
    """Primary data interface class for converting a AxonaRecordingExtractor."""

    display_name = "Axona Units"
    associated_suffixes = (".bin", ".set")
    info = "Interface for Axona recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        return dict(
            required=["file_path"],
            properties=dict(
                file_path=dict(
                    type="string",
                    format="file",
                    description="Path to Axona file.",
                ),
                noise_std=dict(type="number"),
            ),
            type="object",
        )

    def __init__(self, file_path: FilePath, noise_std: float = 3.5):
        super().__init__(filename=file_path, noise_std=noise_std)
        self.source_data = dict(file_path=file_path, noise_std=noise_std)


class AxonaLFPDataInterface(BaseLFPExtractorInterface):
    """
    Primary data interface class for converting Axona LFP data.
    Note that this interface is not lazy and will load all data into memory.
    """

    display_name = "Axona LFP"
    associated_suffixes = (".bin", ".set")
    info = "Interface for Axona LFP data."

    ExtractorName = "NumpyRecording"

    @classmethod
    def get_source_schema(cls) -> dict:
        return dict(
            required=["file_path"],
            properties=dict(file_path=dict(type="string")),
            type="object",
            additionalProperties=False,
        )

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:

        extractor_kwargs = source_data.copy()
        extractor_kwargs.pop("file_path")
        extractor_kwargs["traces_list"] = self.traces_list
        extractor_kwargs["sampling_frequency"] = self.sampling_frequency

        return extractor_kwargs

    def __init__(self, file_path: FilePath):
        data = read_all_eeg_file_lfp_data(file_path).T
        self.traces_list = [data]
        self.sampling_frequency = get_eeg_sampling_frequency(file_path)
        super().__init__(file_path=file_path)

        self.source_data = dict(file_path=file_path)


class AxonaPositionDataInterface(BaseDataInterface):
    """Primary data interface class for converting Axona position data."""

    display_name = "Axona Position"
    keywords = ("position tracking",)
    associated_suffixes = (".bin", ".set")
    info = "Interface for Axona position data."

    @classmethod
    def get_source_schema(cls) -> dict:
        return get_json_schema_from_method_signature(cls.__init__)

    def __init__(self, file_path: str):
        """

        Parameters
        ----------
        file_path: str
            Path to .bin or .set file.
        """
        super().__init__(filename=file_path)
        self.source_data = dict(file_path=file_path)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        """
        Run conversion for this data interface.

        Parameters
        ----------
        nwbfile : NWBFile
        metadata : dict
        """
        file_path = self.source_data["file_path"]

        # Create or update processing module for behavioral data
        behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")
        behavior_module.add(get_position_object(file_path))
