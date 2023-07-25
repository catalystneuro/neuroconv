"""Interface for converting and parsing data in auxiliary or digital channels from the intan .rhd or .rhs file."""
from typing import Literal
from pathlib import Path

from pynwb.ecephys import ElectricalSeries

from .intan_utils import extract_electrode_metadata
from ..baseauxiliaryextractorinterface import BaseAuxiliaryExtractorInterface
from ....tools import get_package
from ....utils import FilePathType, get_schema_from_hdmf_class


class IntanAuxiliaryInterface(BaseAuxiliaryExtractorInterface):
    """Interface for converting and parsing data in auxiliary or digital channels from the intan .rhd or .rhs file."""

    ExtractorName = "IntanRecordingExtractor"

    def __init__(
        self,
        file_path: FilePathType,
        stream_name: Literal[
            "RHD2000 auxiliary input channel", "RHD2000 supply voltage channel", "USB board ADC input channel"
        ] = "RHD2000 auxiliary input channel",
        verbose: bool = True,
        es_key: str = "AuxiliaryElectricalSeries",
    ):
        """
        Load and prepare raw data and corresponding metadata from the Intan format (.rhd or .rhs files).

        Parameters
        ----------
        file_path : FilePathType
            Path to either a rhd or a rhs file
        stream_id : str, optional
            The stream of the data for spikeinterface, "0" by default.
        verbose : bool, default: True
            Verbose
        es_key : str, default: "ElectricalSeries"
        """
        self.stream_name = stream_name
        super().__init__(file_path=file_path, stream_id=self.stream_id, verbose=verbose, es_key=es_key)
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

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            AuxiliaryElectricalSeries=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self) -> dict:
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
                device="IntanAuxiliaryBoard",
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
            AuxiliaryElectricalSeries=dict(name="AuxiliaryElectricalSeries", description="Raw acquisition traces."),
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
