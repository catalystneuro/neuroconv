"""DataInterfaces for SpikeGLX."""

from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import FilePath, validate_call

from .spikeglx_utils import (
    add_recording_extractor_properties,
    fetch_stream_id_for_spikelgx_file,
    get_device_metadata,
    get_session_start_time,
)
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import get_schema_from_method_signature


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary SpikeGLX interface for converting raw SpikeGLX data using a :py:class:`~spikeinterface.extractors.SpikeGLXRecordingExtractor`.
    """

    display_name = "SpikeGLX Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("Neuropixels",)
    associated_suffixes = (".imec{probe_index}", ".ap", ".lf", ".meta", ".bin")
    info = "Interface for SpikeGLX recording data."

    # TODO: Add probe_index to probeinterface and propagate it from there
    # Note to developer.
    # In a conversion with Jennifer Colonell she refers to the number after imec as the probe index
    # Quoting here:
    # imec0 is the probe in the lowest slot and port number, imec1 in the next highest, and so on.
    # If you have probes in {slot 2, port 3}, {slot 3, port1} and {slot3, port2},
    # the probe indices in the SGLX output will be 0, 1, and 2, respectively.

    ExtractorName = "SpikeGLXRecordingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_schema_from_method_signature(method=cls.__init__, exclude=["x_pitch", "y_pitch"])
        source_schema["properties"]["file_path"]["description"] = "Path to SpikeGLX ap.bin or lf.bin file."
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
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

        # Set electrodes properties
        add_recording_extractor_properties(self.recording_extractor)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        session_start_time = get_session_start_time(self.meta)
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Device metadata
        device = get_device_metadata(self.meta)

        # Should follow pattern 'Imec0', 'Imec1', etc.
        probe_name = self.stream_id[:5].capitalize()
        device["name"] = f"Neuropixel{probe_name}"

        # Add groups metadata
        metadata["Ecephys"]["Device"] = [device]
        electrode_groups = [
            dict(
                name=group_name,
                description=f"A group representing probe/shank '{group_name}'.",
                location="unknown",
                device=device["name"],
            )
            for group_name in set(self.recording_extractor.get_property("group_name"))
        ]
        metadata["Ecephys"]["ElectrodeGroup"] = electrode_groups

        # Electrodes columns descriptions
        metadata["Ecephys"]["Electrodes"] = [
            dict(name="group_name", description="Name of the ElectrodeGroup this electrode is a part of."),
            dict(name="contact_shapes", description="The shape of the electrode"),
            dict(name="contact_ids", description="The id of the contact on the electrode"),
        ]

        if self.recording_extractor.get_probe().get_shank_count() > 1:
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
