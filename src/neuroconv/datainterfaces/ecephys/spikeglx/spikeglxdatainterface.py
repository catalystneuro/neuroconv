"""DataInterfaces for SpikeGLX."""

import warnings
from pathlib import Path

import numpy as np
from pydantic import DirectoryPath, FilePath, validate_call

from .spikeglx_utils import (
    fetch_stream_id_for_spikelgx_file,
    get_device_metadata,
    get_session_start_time,
)
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import DeepDict, get_json_schema_from_method_signature


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary SpikeGLX interface for converting raw SpikeGLX data.

    Uses the :py:func:`~spikeinterface.extractors.read_spikeglx` reader from SpikeInterface.
    """

    display_name = "SpikeGLX Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("Neuropixels",)
    associated_suffixes = (".imec{probe_index}", ".ap", ".lf", ".meta", ".bin")
    info = "Interface for SpikeGLX recording data."

    ExtractorName = "SpikeGLXRecordingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["x_pitch", "y_pitch"])
        source_schema["properties"]["file_path"]["description"] = "Path to SpikeGLX ap.bin or lf.bin file."
        return source_schema

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:

        extractor_kwargs = source_data.copy()
        extractor_kwargs["folder_path"] = self.folder_path
        extractor_kwargs["all_annotations"] = True
        extractor_kwargs["stream_id"] = self.stream_id
        return extractor_kwargs

    @validate_call
    def __init__(
        self,
        file_path: FilePath | None = None,
        verbose: bool = False,
        es_key: str | None = None,
        folder_path: DirectoryPath | None = None,
        stream_id: str | None = None,
    ):
        """
        Parameters
        ----------
        folder_path: DirectoryPath
            Folder path containing the binary files of the SpikeGLX recording.
        stream_id: str, optional
            Stream ID of the SpikeGLX recording.
            Examples are 'imec0.ap', 'imec0.lf', 'imec1.ap', 'imec1.lf', etc.
        file_path : FilePath
            Path to .bin file. Point to .ap.bin for SpikeGLXRecordingInterface and .lf.bin for SpikeGLXLFPInterface.
        verbose : bool, default: False
            Whether to output verbose text.
        es_key : str, the key to access the metadata of the ElectricalSeries.
        """

        if stream_id == "nidq":
            raise ValueError(
                "SpikeGLXRecordingInterface is not designed to handle nidq files. Use SpikeGLXNIDQInterface instead"
            )

        if stream_id is not None and "SYNC" in stream_id:
            raise ValueError(
                "SpikeGLXRecordingInterface is not designed to handle the SYNC stream. Open an issue if you need this functionality."
            )

        if file_path is not None:
            warnings.warn(
                "file_path is deprecated and will be removed by the end of 2025. "
                "The first argument of this interface will be `folder_path` afterwards. "
                "Use folder_path and stream_id instead.",
                DeprecationWarning,
                stacklevel=2,
            )

        if file_path is not None and stream_id is None:
            self.stream_id = fetch_stream_id_for_spikelgx_file(file_path)
            self.folder_path = Path(file_path).parent
        else:
            self.stream_id = stream_id
            self.folder_path = Path(folder_path)

        super().__init__(
            folder_path=folder_path,
            verbose=verbose,
            es_key=es_key,
        )

        signal_info_key = (0, self.stream_id)  # Key format is (segment_index, stream_id)
        self._signals_info_dict = self.recording_extractor.neo_reader.signals_info_dict[signal_info_key]
        self.meta = self._signals_info_dict["meta"]

        if es_key is None:
            stream_kind = self._signals_info_dict["stream_kind"]  # ap or lf
            stream_kind_caps = stream_kind.upper()
            device = self._signals_info_dict["device"].capitalize()  # imec0, imec1, etc.

            electrical_series_name = f"ElectricalSeries{stream_kind_caps}"

            # Add imec{probe_index} to the electrical series name when there are multiple probes
            # or undefined, `typeImEnabled` is present in the meta of all the production probes
            self.probes_enabled_in_run = int(self.meta.get("typeImEnabled", 0))
            if self.probes_enabled_in_run != 1:
                electrical_series_name += f"{device}"

            self.es_key = electrical_series_name

        # Set electrode properties from probe information
        probe = self.recording_extractor.get_probe()
        channel_ids = self.recording_extractor.get_channel_ids()

        # Should follow pattern 'Imec0', 'Imec1', etc.
        probe_name = self.recording_extractor.stream_id[:5].capitalize()

        # Set group_name property based on shank count
        if probe.get_shank_count() > 1:
            shank_ids = probe.shank_ids
            self.recording_extractor.set_property(key="shank_ids", values=shank_ids)
            group_name = [f"Neuropixels{probe_name}Shank{shank_id}" for shank_id in shank_ids]
        else:
            group_name = [f"Neuropixels{probe_name}"] * len(channel_ids)

        self.recording_extractor.set_property(key="group_name", ids=channel_ids, values=group_name)

        # Set contact geometry properties
        contact_shapes = probe.contact_shapes
        self.recording_extractor.set_property(key="contact_shapes", ids=channel_ids, values=contact_shapes)

        contact_ids = probe.contact_ids  # Format: "e0", "e1" or "s0e0", "s0e1" for multi-shank
        self.recording_extractor.set_property(key="contact_ids", ids=channel_ids, values=contact_ids)

        # Set channel_name property for multi-stream deduplication
        # For SpikeGLX, multiple streams (AP, LF) can record from the same electrodes
        # We set channel_name to show all streams for each electrode (e.g., "AP0,LF0")
        current_stream_kind = self._signals_info_dict["stream_kind"]  # "ap" or "lf"

        # Check if companion stream exists (AP has LF, LF has AP)
        device = self._signals_info_dict["device"]  # e.g., "imec0"
        companion_stream_kind = "lf" if current_stream_kind == "ap" else "ap"
        companion_stream_id = f"{device}.{companion_stream_kind}"
        companion_key = (0, companion_stream_id)

        signals_info_dict = self.recording_extractor.neo_reader.signals_info_dict
        has_companion_stream = companion_key in signals_info_dict

        # Build channel names
        channel_names = []
        for channel_id in channel_ids:
            # Extract channel number from channel_id (e.g., "imec0.ap#AP0" -> "0")
            channel_number = channel_id.split("#")[-1][2:]

            if has_companion_stream:
                # Multi-stream: show both AP and LF (alphabetically sorted)
                channel_name = f"AP{channel_number},LF{channel_number}"
            else:
                # Single stream: just use the current stream name
                channel_name = f"{current_stream_kind.upper()}{channel_number}"

            channel_names.append(channel_name)

        self.recording_extractor.set_property(key="channel_name", ids=channel_ids, values=channel_names)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        session_start_time = get_session_start_time(self.meta)
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Device metadata
        device = get_device_metadata(self.meta)

        # Should follow pattern 'Imec0', 'Imec1', etc.
        probe_name = self._signals_info_dict["device"].capitalize()
        device["name"] = f"Neuropixels{probe_name}"

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
            dict(
                name="electrode_name",
                description=(
                    "The unique name of this electrode. Derived from probe contact identifiers. "
                    "Multiple channels (e.g., AP and LF bands) from the same physical electrode "
                    "will share the same electrode_name."
                ),
            ),
            dict(name="contact_shapes", description="The shape of the electrode"),
            dict(name="contact_ids", description="The id of the contact on the electrode"),
            dict(
                name="inter_sample_shift",
                description=(
                    "Array of relative phase shifts for each channel, with values ranging from 0 to 1, "
                    "representing the fractional delay within the sampling period due to sequential ADC."
                ),
            ),
        ]

        if self.recording_extractor.get_probe().get_shank_count() > 1:
            metadata["Ecephys"]["Electrodes"].append(
                dict(name="shank_ids", description="The shank id of the electrode")
            )

        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        new_recording = self.get_extractor()(
            folder_path=self.folder_path,
            stream_id=self.stream_id,
        )  # TODO: add generic method for aliasing from NeuroConv signature to SI init
        if self._number_of_segments == 1:
            return new_recording.get_times()
        else:
            return [
                new_recording.get_times(segment_index=segment_index)
                for segment_index in range(self._number_of_segments)
            ]
