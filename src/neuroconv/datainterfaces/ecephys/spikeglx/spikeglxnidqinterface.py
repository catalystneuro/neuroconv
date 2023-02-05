"""Authors: Cody Baker."""
from pathlib import Path
from typing import List, Optional

import numpy as np
from pynwb import NWBFile
from pynwb.ecephys import ElectricalSeries

from .spikeglxdatainterface import SpikeGLXRecordingInterface
from ....tools.signal_processing import get_rising_frames_from_ttl
from ....utils import get_schema_from_method_signature, get_schema_from_hdmf_class, FilePathType


class SpikeGLXNIDQInterface(SpikeGLXRecordingInterface):
    """Primary data interface class for converting the high-pass (ap) SpikeGLX format."""

    ExtractorName = "SpikeGLXRecordingExtractor"

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(class_method=cls.__init__, exclude=["x_pitch", "y_pitch"])
        source_schema["properties"]["file_path"]["description"] = "Path to SpikeGLX .nidq file."
        return source_schema

    def __init__(
        self, file_path: FilePathType, stub_test: bool = False, verbose: bool = True, load_sync_channel: bool = False
    ):
        """
        Read channel data from the NIDQ board for the SpikeGLX recording.

        Useful for synchronizing multiple data streams into the common time basis of the SpikeGLX system.

        Parameters
        ----------
        file_path : FilePathType
            Path to .nidq.bin file.
        stub_test : bool, default: False
            Whether to shorten file for testing purposes.
        verbose : bool, default: True
            Whether to output verbose text.
        load_sync_channel : bool, default: False
            Whether or not to load the last channel in the stream, which is typically used for synchronization.
            If True, then the probe is not loaded.
        """
        self.stream_id = "nidq"

        folder_path = Path(file_path).parent
        super(SpikeGLXRecordingInterface, self).__init__(
            folder_path=folder_path,
            stream_id=self.stream_id,
            verbose=verbose,
            load_sync_channel=load_sync_channel,
        )
        self.source_data.update(file_path=str(file_path))

        self.recording_extractor.set_property(
            key="group_name", values=["NIDQChannelGroup"] * self.recording_extractor.get_num_channels()
        )
        self.meta = self.recording_extractor.neo_reader.signals_info_dict[(0, self.stream_id)]["meta"]

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeriesNIDQ=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()

        metadata["Ecephys"]["ElectrodeGroup"][0]["description"] = "A group representing the NIDQ channels."
        metadata["Ecephys"]["Electrodes"] = [
            dict(name="group_name", description="Name of the ElectrodeGroup this electrode is a part of."),
        ]
        metadata["Ecephys"].pop("ElectricalSeriesRaw")
        metadata["Ecephys"]["ElectricalSeriesNIDQ"] = dict(
            name="ElectricalSeriesNIDQ", description="Raw acquisition traces from the NIDQ (.nidq.bin) channels."
        )
        return metadata

    def get_channel_names(self) -> List[str]:
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

    def get_conversion_options(self) -> dict:
        # Currently this method is only used by NWBConverter classes
        # We still need a similar override for run_conversion default es_key for stand-alone interface conversion
        conversion_options = dict(write_as="raw", es_key="ElectricalSeriesNIDQ")
        return conversion_options

    def run_conversion(
        self,
        nwbfile_path: Optional[FilePathType] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        stub_test: bool = False,
        write_as: Optional[str] = None,
        write_electrical_series: bool = True,
        es_key: str = None,
        compression: Optional[str] = None,
        compression_opts: Optional[int] = None,
        iterator_type: str = "v2",
        iterator_opts: Optional[dict] = None,
    ):
        super().run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            stub_test=stub_test,
            write_as=write_as,
            write_electrical_series=write_electrical_series,
            es_key=es_key or "ElectricalSeriesNIDQ",
            compression=compression,
            compression_opts=compression_opts,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
        )
