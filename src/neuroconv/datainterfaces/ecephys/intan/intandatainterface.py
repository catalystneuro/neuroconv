"""Authors: Heberto Mayorquin, Cody Baker and Ben Dichter."""
from pathlib import Path

from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....tools import get_package
from ....utils import get_schema_from_hdmf_class, FilePathType


def extract_electrode_metadata_with_pyintan(file_path):
    pyintan = get_package(package_name="pyintan")

    if ".rhd" in Path(file_path).suffixes:
        intan_file_metadata = pyintan.intan.read_rhd(file_path)[1]
    else:
        intan_file_metadata = pyintan.intan.read_rhs(file_path)[1]

    exclude_chan_types = ["AUX", "ADC", "VDD", "_STIM", "ANALOG"]

    valid_channels = [
        x for x in intan_file_metadata if not any([y in x["native_channel_name"] for y in exclude_chan_types])
    ]

    group_names = [channel["native_channel_name"].split("-")[0] for channel in valid_channels]
    unique_group_names = set(group_names)
    group_electrode_numbers = [channel["native_order"] for channel in valid_channels]
    custom_names = [channel["custom_channel_name"] for channel in valid_channels]

    electrodes_metadata = dict(
        group_names=group_names,
        unique_group_names=unique_group_names,
        group_electrode_numbers=group_electrode_numbers,
        custom_names=custom_names,
    )

    return electrodes_metadata


def extract_electrode_metadata(recording_extractor):

    channel_name_array = recording_extractor.get_property("channel_name")

    group_names = [channel.split("-")[0] for channel in channel_name_array]
    unique_group_names = set(group_names)
    group_electrode_numbers = [int(channel.split("-")[1]) for channel in channel_name_array]
    custom_names = list()

    electrodes_metadata = dict(
        group_names=group_names,
        unique_group_names=unique_group_names,
        group_electrode_numbers=group_electrode_numbers,
        custom_names=custom_names,
    )

    return electrodes_metadata


class IntanRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting Intan data using the
    :py:class:`~spikeinterface.extractors.IntanRecordingExtractor`."""

    def __init__(
        self,
        file_path: FilePathType,
        stream_id: str = "0",
        spikeextractors_backend: bool = False,
        verbose: bool = True,
    ):
        """Load and prepare raw data and corresponding metadata from the Intan format (.rhd or .rhs files).


        Parameters
        ----------
        file_path : FilePathType
            Path to either a rhd or a rhs file
        stream_id : str, optional
            The stream of the data for spikeinterface, "0" by default.
        spikeextractors_backend : bool
            False by default. When True the interface uses the old extractor from the spikextractors library instead
            of a new spikeinterface object.
        verbose : bool
            Verbose
        """

        if spikeextractors_backend:
            _ = get_package(package_name="pyintan")
            from spikeextractors import IntanRecordingExtractor
            from spikeinterface.core.old_api_utils import OldToNewRecording

            self.Extractor = IntanRecordingExtractor
            super().__init__(file_path=file_path, verbose=verbose)
            self.recording_extractor = OldToNewRecording(oldapi_recording_extractor=self.recording_extractor)
            electrodes_metadata = extract_electrode_metadata_with_pyintan(file_path)
        else:
            self.stream_id = stream_id
            super().__init__(file_path=file_path, stream_id=self.stream_id, verbose=verbose)
            electrodes_metadata = extract_electrode_metadata(recording_extractor=self.recording_extractor)

        group_names = electrodes_metadata["group_names"]
        group_electrode_numbers = electrodes_metadata["group_electrode_numbers"]
        unique_group_names = electrodes_metadata["unique_group_names"]
        custom_names = electrodes_metadata["custom_names"]

        channel_ids = self.recording_extractor.get_channel_ids()
        self.recording_extractor.set_property(key="group_name", ids=channel_ids, values=group_names)
        if len(unique_group_names) > 1:
            self.recording_extractor.set_property(
                key="group_electrode_number", ids=channel_ids, values=group_electrode_numbers
            )

        if any(custom_names):
            self.recording_extractor.set_property(key="custom_channel_name", ids=channel_ids, values=custom_names)

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeriesRaw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        ecephys_metadata = metadata["Ecephys"]

        # Add device
        device = dict(
            name="Intan",
            description="Intan recording",
            manufacturer="Intan",
        )
        device_list = [device]
        ecephys_metadata.update(Device=device_list)

        # Add electrode group
        unique_group_name = set(self.recording_extractor.get_property("group_name"))
        electrode_group_list = [
            dict(
                name=group_name,
                description=f"Group {group_name} electrodes.",
                device="Intan",
                location="",
            )
            for group_name in unique_group_name
        ]
        ecephys_metadata.update(ElectrodeGroup=electrode_group_list)

        # Add electrodes and electrode groups
        ecephys_metadata.update(
            Electrodes=[
                dict(name="group_name", description="The name of the ElectrodeGroup this electrode is a part of.")
            ],
            ElectricalSeriesRaw=dict(name="ElectricalSeriesRaw", description="Raw acquisition traces."),
        )

        # Add group electrode number if available
        recording_extractor_properties = self.recording_extractor.get_property_keys()
        if "group_electrode_number" in recording_extractor_properties:
            ecephys_metadata["Electrodes"].append(
                dict(name="group_electrode_number", description="0-indexed channel within a group.")
            )
        if "custom_channel_name" in recording_extractor_properties:
            ecephys_metadata["Electrodes"].append(
                dict(name="custom_channel_name", description="Custom channel name assigned in Intan.")
            )

        return metadata
