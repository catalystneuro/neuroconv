from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import ConfigDict, DirectoryPath, FilePath, validate_call

from .spikeglx_utils import get_session_start_time
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....tools.signal_processing import get_rising_frames_from_ttl
from ....utils import get_json_schema_from_method_signature


class SpikeGLXNIDQInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting the high-pass (ap) SpikeGLX format."""

    display_name = "NIDQ Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("Neuropixels",)
    associated_suffixes = (".nidq", ".meta", ".bin")
    info = "Interface for NIDQ board recording data."

    ExtractorName = "SpikeGLXRecordingExtractor"
    stream_id = "nidq"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["x_pitch", "y_pitch"])
        source_schema["properties"]["file_path"]["description"] = "Path to SpikeGLX .nidq file."
        return source_schema

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:

        extractor_kwargs = source_data.copy()
        extractor_kwargs["folder_path"] = self.folder_path
        extractor_kwargs["stream_id"] = self.stream_id
        return extractor_kwargs

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __init__(
        self,
        file_path: Optional[FilePath] = None,
        verbose: bool = True,
        load_sync_channel: bool = False,
        es_key: str = "ElectricalSeriesNIDQ",
        folder_path: Optional[DirectoryPath] = None,
    ):
        """
        Read channel data from the NIDQ board for the SpikeGLX recording.

        Useful for synchronizing multiple data streams into the common time basis of the SpikeGLX system.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing the .nidq.bin file.
        file_path : FilePathType
            Path to .nidq.bin file.
        verbose : bool, default: True
            Whether to output verbose text.
        load_sync_channel : bool, default: False
            Whether to load the last channel in the stream, which is typically used for synchronization.
            If True, then the probe is not loaded.
        es_key : str, default: "ElectricalSeriesNIDQ"
        """

        if file_path is None and folder_path is None:
            raise ValueError("Either 'file_path' or 'folder_path' must be provided.")

        if file_path is not None:
            file_path = Path(file_path)
            self.folder_path = file_path.parent

        if folder_path is not None:
            self.folder_path = Path(folder_path)

        super().__init__(
            verbose=verbose,
            load_sync_channel=load_sync_channel,
            es_key=es_key,
        )
        self.source_data.update(file_path=str(file_path))

        self.recording_extractor.set_property(
            key="group_name", values=["NIDQChannelGroup"] * self.recording_extractor.get_num_channels()
        )

        signal_info_key = (0, self.stream_id)  # Key format is (segment_index, stream_id)
        self._signals_info_dict = self.recording_extractor.neo_reader.signals_info_dict[signal_info_key]
        self.meta = self._signals_info_dict["meta"]

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        session_start_time = get_session_start_time(self.meta)
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Device metadata
        device = dict(
            name="NIDQBoard",
            description="A NIDQ board used in conjunction with SpikeGLX.",
            manufacturer="National Instruments",
        )

        # Add groups metadata
        metadata["Ecephys"]["Device"] = [device]

        metadata["Ecephys"]["ElectrodeGroup"][0].update(
            name="NIDQChannelGroup", description="A group representing the NIDQ channels.", device=device["name"]
        )
        metadata["Ecephys"]["Electrodes"] = [
            dict(name="group_name", description="Name of the ElectrodeGroup this electrode is a part of."),
        ]
        metadata["Ecephys"]["ElectricalSeriesNIDQ"][
            "description"
        ] = "Raw acquisition traces from the NIDQ (.nidq.bin) channels."
        return metadata

    def get_channel_names(self) -> list[str]:
        """Return a list of channel names as set in the recording extractor."""
        return list(self.recording_extractor.get_channel_ids())

    def get_event_times_from_ttl(self, channel_name: str) -> np.ndarray:
        """
        Return the start of event times from the rising part of TTL pulses on one of the NIDQ channels.

        Parameters
        ----------
        channel_name : str
            Name of the channel in the .nidq.bin file.

        Returns
        -------
        rising_times : numpy.ndarray
            The times of the rising TTL pulses.
        """
        # TODO: consider RAM cost of these operations and implement safer buffering version
        rising_frames = get_rising_frames_from_ttl(
            trace=self.recording_extractor.get_traces(channel_ids=[channel_name])
        )

        nidq_timestamps = self.recording_extractor.get_times()
        rising_times = nidq_timestamps[rising_frames]

        return rising_times
