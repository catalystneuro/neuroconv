"""Primary data interface for converting the NIDQ streams from SpikeGLX format."""
from pathlib import Path

from .spikeglx_utils import get_device_metadata, get_session_start_time
from ..baseauxiliaryextractorinterface import BaseAuxiliaryExtractorInterface
from ....utils import FilePathType, get_schema_from_method_signature


class SpikeGLXNIDQInterface(BaseAuxiliaryExtractorInterface):
    """Primary data interface for converting the NIDQ streams from SpikeGLX format."""

    ExtractorName = "SpikeGLXRecordingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_schema_from_method_signature(method=cls.__init__, exclude=["x_pitch", "y_pitch"])
        source_schema["properties"]["file_path"]["description"] = "Path to SpikeGLX .nidq file."
        return source_schema

    def __init__(
        self,
        file_path: FilePathType,
        verbose: bool = True,
        load_sync_channel: bool = False,
        es_key: str = "ElectricalSeriesNIDQ",
    ):
        """
        Read channel data from the NIDQ board for the SpikeGLX recording.

        Useful for synchronizing multiple data streams into the common time basis of the SpikeGLX system.

        Parameters
        ----------
        file_path : FilePathType
            Path to .nidq.bin file.
        verbose : bool, default: True
            Whether to output verbose text.
        load_sync_channel : bool, default: False
            Whether to load the last channel in the stream, which is typically used for synchronization.
            If True, then the probe is not loaded.
        es_key : str, default: "ElectricalSeriesNIDQ"
        """
        folder_path = Path(file_path).parent
        super().__init__(
            folder_path=folder_path,
            stream_id="nidq",
            verbose=verbose,
            load_sync_channel=load_sync_channel,
            es_key=es_key,
        )
        self.source_data.update(file_path=str(file_path))

        self.recording_extractor.set_property(
            key="group_name", values=["NIDQChannelGroup"] * self.recording_extractor.get_num_channels()
        )
        self.meta = self.recording_extractor.neo_reader.signals_info_dict[(0, "nidq")]["meta"]

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        session_start_time = get_session_start_time(self.meta)
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Device metadata
        device = get_device_metadata(self.meta)

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
