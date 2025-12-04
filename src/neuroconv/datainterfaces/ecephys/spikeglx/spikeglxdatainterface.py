"""DataInterfaces for SpikeGLX."""

from datetime import datetime
from pathlib import Path

import numpy as np
from pydantic import DirectoryPath, validate_call

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

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["x_pitch", "y_pitch"])
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to the folder containing the .ap.bin or .lf.bin SpikeGLX file."
        return source_schema

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import (
            SpikeGLXRecordingExtractor,
        )

        return SpikeGLXRecordingExtractor

    def _initialize_extractor(self, interface_kwargs: dict):
        """Override to add stream_id and set folder_path."""
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("es_key", None)
        self.extractor_kwargs["all_annotations"] = True
        self.extractor_kwargs["folder_path"] = self.folder_path
        self.extractor_kwargs["stream_id"] = self.stream_id

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        stream_id: str,
        verbose: bool = False,
        es_key: str | None = None,
    ):
        """
        Parameters
        ----------
        folder_path : DirectoryPath
            Folder path containing the binary files of the SpikeGLX recording.
        stream_id : str
            Stream ID of the SpikeGLX recording.
            Examples are 'imec0.ap', 'imec0.lf', 'imec1.ap', 'imec1.lf', etc.
        verbose : bool, default: False
            Whether to output verbose text.
        es_key : str, optional
            The key to access the metadata of the ElectricalSeries.
        """

        if stream_id == "nidq":
            raise ValueError(
                "SpikeGLXRecordingInterface is not designed to handle nidq files. Use SpikeGLXNIDQInterface instead"
            )

        if "SYNC" in stream_id:
            raise ValueError(
                "SpikeGLXRecordingInterface is not designed to handle the SYNC stream. "
                "Use SpikeGLXSyncChannelInterface instead to read synchronization channels."
            )

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

        # Set ADC multiplexing properties if available
        if "adc_group" in probe.contact_annotations:
            adc_group = probe.contact_annotations["adc_group"]
            self.recording_extractor.set_property(key="adc_group", ids=channel_ids, values=adc_group)

        if "adc_sample_order" in probe.contact_annotations:
            adc_sample_order = probe.contact_annotations["adc_sample_order"]
            self.recording_extractor.set_property(key="adc_sample_order", ids=channel_ids, values=adc_sample_order)

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

        # Remove inter_sample_shift property - internal spikeinterface property not relevant for NWB
        if "inter_sample_shift" in self.recording_extractor.get_property_keys():
            self.recording_extractor.delete_property(key="inter_sample_shift")

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        session_start_time = self._get_session_start_time()
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Device metadata
        device = self._get_device_metadata_from_probe()

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
            dict(
                name="adc_group",
                description=(
                    "The ADC (Analog-to-Digital Converter) index to which each electrode is connected. "
                    "This hardware configuration determines which channels are sampled simultaneously."
                ),
            ),
            dict(
                name="adc_sample_order",
                description=(
                    "The sampling order index (0-based) of this electrode within its ADC group. "
                    "Combined with adc_group, this determines the precise temporal offset of each channel's samples."
                ),
            ),
        ]

        if self.recording_extractor.get_probe().get_shank_count() > 1:
            metadata["Ecephys"]["Electrodes"].append(
                dict(name="shank_ids", description="The shank id of the electrode")
            )

        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        new_recording = self._initialize_extractor(
            self.source_data
        )  # TODO: add generic method for aliasing from NeuroConv signature to SI init
        if self._number_of_segments == 1:
            return new_recording.get_times()
        else:
            return [
                new_recording.get_times(segment_index=segment_index)
                for segment_index in range(self._number_of_segments)
            ]

    def _get_session_start_time(self) -> datetime | None:
        """
        Fetches the session start time from the recording metadata.

        Returns
        -------
        datetime or None
            the session start time in datetime format.
        """
        session_start_time = self.meta.get("fileCreateTime", None)
        if session_start_time.startswith("0000-00-00"):
            # date was removed. This sometimes happens with human data to protect the
            # anonymity of medical patients.
            return
        if session_start_time:
            session_start_time = datetime.fromisoformat(session_start_time)
        return session_start_time

    def _get_device_metadata_from_probe(self) -> dict:
        """Returns device metadata extracted from probe information.

        Returns
        -------
        dict
            A dict containing the metadata necessary for creating the device.
        """
        import json

        # Get probe info from recording extractor annotation
        probes_info = self.recording_extractor.get_annotation("probes_info")
        probe_info = probes_info[0]  # Get first probe info

        metadata_dict = dict()

        # Add available fields from probe_info

        # Serial number is a separate field in device metadata
        serial_number = probe_info.get("serial_number")

        if "part_number" in probe_info:
            metadata_dict.update(part_number=probe_info["part_number"])

        if "port" in probe_info:
            metadata_dict.update(port=probe_info["port"])

        if "slot" in probe_info:
            metadata_dict.update(slot=probe_info["slot"])

        if "model_name" in probe_info:
            metadata_dict.update(model_name=probe_info["model_name"])

        # Use description from probe_info if available
        description_string = probe_info.get("description", "A Neuropixel probe of unknown subtype.")

        # Get manufacturer from probe_info, default to "Imec"
        manufacturer = probe_info.get("manufacturer", "Imec")

        # Add manufacturer to metadata_dict
        metadata_dict.update(manufacturer=manufacturer)

        # Append additional metadata to description as JSON
        if metadata_dict:
            description_string = f"{description_string}. Additional metadata: {json.dumps(metadata_dict)}"

        device_metadata = dict(name="NeuropixelImec", description=description_string)

        # Add serial_number as a separate field if available
        if serial_number:
            device_metadata["serial_number"] = serial_number

        return device_metadata
