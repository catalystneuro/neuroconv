"""DataInterfaces for SpikeGLX."""
import warnings
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


def add_recording_extractor_properties(recording_extractor) -> None:
    """Automatically add shankgroup_name and shank_electrode_number for spikeglx."""
    probe = recording_extractor.get_probe()
    channel_ids = recording_extractor.get_channel_ids()

    if probe.get_shank_count() > 1:
        group_name = [contact_id.split("e")[0] for contact_id in probe.contact_ids]
        shank_electrode_number = [int(contact_id.split("e")[1]) for contact_id in probe.contact_ids]
    else:
        shank_electrode_number = recording_extractor.ids_to_indices(channel_ids)
        group_name = ["s0"] * len(channel_ids)

    recording_extractor.set_property(key="shank_electrode_number", ids=channel_ids, values=shank_electrode_number)
    recording_extractor.set_property(key="group_name", ids=channel_ids, values=group_name)

    contact_shapes = probe.contact_shapes  # The geometry of the contact shapes
    recording_extractor.set_property(key="contact_shapes", ids=channel_ids, values=contact_shapes)


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    keywords = BaseRecordingExtractorInterface.keywords + [
        "Neuropixels",
    ]

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
        from probeinterface import read_spikeglx

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
        )
        self.source_data["file_path"] = str(file_path)
        self.meta = self.recording_extractor.neo_reader.signals_info_dict[(0, self.stream_id)]["meta"]

        # Mount the probe
        # TODO - this can be removed in the next release of SpikeInterface (probe mounts automatically)
        meta_filename = str(file_path).replace(".bin", ".meta").replace(".lf", ".ap")
        probe = read_spikeglx(meta_filename)
        self.recording_extractor.set_probe(probe, in_place=True)
        # Set electrodes properties
        add_recording_extractor_properties(self.recording_extractor)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        session_start_time = get_session_start_time(self.meta)
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Device metadata
        device = get_device_metadata(self.meta)

        # Add groups metadata
        metadata["Ecephys"]["Device"] = [device]
        electrode_groups = [
            dict(
                name=group_name,
                description=f"a group representing shank {group_name}",
                location="unknown",
                device=device["name"],
            )
            for group_name in set(self.recording_extractor.get_property("group_name"))
        ]
        metadata["Ecephys"]["ElectrodeGroup"] = electrode_groups

        # Electrodes columns descriptions
        metadata["Ecephys"]["Electrodes"] = [
            dict(name="shank_electrode_number", description="0-indexed channel within a shank."),
            dict(name="group_name", description="Name of the ElectrodeGroup this electrode is a part of."),
            dict(name="contact_shapes", description="The shape of the electrode"),
        ]

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


# include for backwards compatibility
class SpikeGLXLFPInterface(SpikeGLXRecordingInterface):
    """Primary data interface class for converting the low-pass (lf) SpikeGLX format."""

    ExtractorName = "SpikeGLXRecordingExtractor"

    def __init__(
        self,
        file_path: FilePathType,
        verbose: bool = True,
        es_key: str = "ElectricalSeriesLF",
    ):
        warnings.warn(
            "SpikeGLXLFPExtractor will be deprecated. Use SpikeGLXRecordingExtractor instead.", DeprecationWarning
        )
        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)
