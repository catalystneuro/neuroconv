"""DataInterfaces for SpikeGLX."""

from pathlib import Path
from typing import Optional

import numpy as np

from .spikeglx_utils import (
    fetch_stream_id_for_spikelgx_file,
    get_device_metadata,
    get_session_start_time,
)
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import FilePathType, get_schema_from_method_signature


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    display_name = "SpikeGLX Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("Neuropixels",)
    associated_suffixes = (".imec{probe_number}", ".ap", ".lf", ".meta", ".bin")
    info = "Interface for SpikeGLX recording data."

    ExtractorName = "SpikeGLXRecordingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_schema_from_method_signature(method=cls.__init__, exclude=["x_pitch", "y_pitch"])
        source_schema["properties"]["file_path"]["description"] = "Path to SpikeGLX ap.bin or lf.bin file."
        return source_schema

    def __init__(
        self,
        file_path: FilePathType,
        verbose: bool = True,
        es_key: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        file_path : FilePathType
            Path to .bin file. Point to .ap.bin for SpikeGLXRecordingInterface and .lf.bin for SpikeGLXLFPInterface.
        verbose : bool, default: True
            Whether to output verbose text.
        es_key : str, default: "ElectricalSeries"
        """

        self.stream_id = fetch_stream_id_for_spikelgx_file(file_path)
        if es_key is None:
            if "lf" in self.stream_id:
                es_key = "ElectricalSeriesLF"
            elif "ap" in self.stream_id:
                es_key = "ElectricalSeriesAP"
            else:
                raise ValueError("Cannot automatically determine es_key from path")
        file_path = Path(file_path)
        folder_path = file_path.parent
        super().__init__(
            folder_path=folder_path,
            stream_id=self.stream_id,
            verbose=verbose,
            es_key=es_key,
            all_annotations=True,
        )
        self.source_data["file_path"] = str(file_path)
        self.meta = self.recording_extractor.neo_reader.signals_info_dict[(0, self.stream_id)]["meta"]

        # Setting "group_name" should create the electrode groups based on the probe
        # Note that SpikeGLX interface defaults to create groups by shank which we don't want in this case
        recording = self.recording_extractor
        probe_name = recording.get_annotation("stream_name").split(".")[0]
        self.es_key = self.es_key + f"{probe_name.upper()}"
        number_of_channels = recording.get_num_channels()
        recording.set_property(key="group_name", values=[probe_name] * number_of_channels)

        # Also add a probe port as a property to the recording to make explicit where the probe is in the imec card
        probe_info = recording.get_annotation("probes_info")[0]
        self.probe_port = probe_info["port"]
        probe_slot = probe_info["slot"]
        recording.set_property(key="probe_port", values=[self.probe_port] * number_of_channels)
        recording.set_property(key="probe_slot", values=[probe_slot] * number_of_channels)

        # This is the probe represented as a numpy structured array
        contact_vector = recording.get_property("contact_vector")
        shank_ids = contact_vector["shank_ids"]

        # Add the contact ids
        contact_ids = contact_vector["contact_ids"]
        recording.set_property(key="contact_ids", values=contact_ids)

        # Add the contact shapes
        contact_shapes = contact_vector["contact_shapes"]
        recording.set_property(key="contact_shapes", values=contact_shapes)

        # This is true for neuropixel 2.0 but I rather just checked directly if the metadata is available
        self.probe_has_shanks = not all([id == "" for id in shank_ids])
        if self.probe_has_shanks:
            shank_ids = contact_vector["shank_ids"]
            recording.set_property(key="shank_ids", values=shank_ids)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        session_start_time = get_session_start_time(self.meta)
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Device metadata
        device = get_device_metadata(self.meta)
        device["name"] = device["name"] + f" In Port {self.probe_port}"

        # Add groups metadata
        metadata["Ecephys"]["Device"] = [device]
        electrode_groups = [
            dict(
                name=group_name,
                description=f"a group representing probe {group_name}",
                location="unknown",
                device=device["name"],
            )
            for group_name in set(self.recording_extractor.get_property("group_name"))
        ]
        metadata["Ecephys"]["ElectrodeGroup"] = electrode_groups

        # Electrodes columns descriptions
        metadata["Ecephys"]["Electrodes"] = [
            dict(name="group_name", description="Probe that contact corresponding to the electrode is a part of."),
            dict(name="contact_ids", description="The contact id of the electrode"),
            dict(name="contact_shapes", description="The shape of the electrode"),
            dict(name="probe_port", description="The port in the imec card where the probe is connected"),
            dict(name="probe_slot", description="The probe slot in the PXIe-1071"),
        ]

        if self.probe_has_shanks:
            metadata["Ecephys"]["Electrodes"].append(
                dict(name="shank_ids", description="The shank id of the electrode")
            )

        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        new_recording = self.get_extractor()(
            folder_path=self.source_data["folder_path"], stream_id=self.source_data["stream_id"]
        )  # TODO: add generic method for aliasing from NeuroConv signature to SI init
        if self._number_of_segments == 1:
            return new_recording.get_times()
        else:
            return [
                new_recording.get_times(segment_index=segment_index)
                for segment_index in range(self._number_of_segments)
            ]
