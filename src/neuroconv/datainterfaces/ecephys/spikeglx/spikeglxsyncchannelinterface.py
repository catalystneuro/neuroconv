from datetime import datetime
from pathlib import Path

from pydantic import ConfigDict, DirectoryPath, validate_call
from pynwb import NWBFile

from ....basedatainterface import BaseDataInterface
from ....utils import DeepDict, get_json_schema_from_method_signature


class SpikeGLXSyncChannelInterface(BaseDataInterface):
    """
    Data interface for SpikeGLX synchronization channels from Neuropixel probes.

    SpikeGLX records synchronization channels (labeled as SY0) as the last channel in Neuropixel
    probe data streams. These channels contain a 16-bit status word where bit 6 carries a 1 Hz
    square wave (toggling between 0 and 1 every 0.5 seconds) used for sub-millisecond timing
    alignment across multiple acquisition devices and data streams. The other bits in the status
    word carry hardware status and error flags.

    Technical Details
    -----------------
    - **Neuropixels 1.0**: The sync channel appears identically in both AP and LF files, providing
      redundant timing information for alignment.
    - **Neuropixels 2.0** (full-band): The sync channel appears in the single AP file.
    - **Sync Generation**: Can be generated internally by the Imec module (PXIe or OneBox) or
      externally by an NI-DAQ device acting as the master sync generator.
    - **Multi-probe setups**: The same 1 Hz sync pulse is distributed to all probes, enabling
      precise cross-probe alignment by matching the rising edges in each stream's sync channel.
    - **NIDQ**: When using NIDQ, the sync pulse is typically recorded on a designated analog or
      digital input channel rather than in a dedicated status word.

    When to Use
    -----------
    Use this interface when you need explicit control over which sync channel to convert. For most
    use cases, the :py:class:`~neuroconv.converters.SpikeGLXConverterPipe` is recommended, which
    automatically includes all the neural streams plus the sync channels (one per probe, preferring AP over LF)
    by default.

    Use this interface directly when you need to:
    - Convert only a specific sync channel stream
    - Handle sync channels separately from neural data

    The sync channel is stored as a TimeSeries in the NWB file's acquisition group
    """

    display_name = "SpikeGLX Sync Channel"
    keywords = ("Neuropixels", "sync", "synchronization", "SpikeGLX")
    associated_suffixes = (".imec", ".ap", ".lf", ".meta", ".bin")
    info = "Interface for SpikeGLX synchronization channel data from Neuropixel probes."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=[])
        source_schema["properties"]["folder_path"]["description"] = "Path to SpikeGLX folder containing .imec files."
        source_schema["properties"]["stream_id"][
            "description"
        ] = "The stream ID for the sync channel (e.g., 'imec0.ap-SYNC' or 'imec1.lf-SYNC')."
        source_schema["properties"]["metadata_key"]["description"] = (
            "Key used to organize metadata in the metadata dictionary. This is especially useful "
            "when multiple sync channel interfaces are used in the same conversion. The metadata_key is used "
            "to organize TimeSeries metadata."
        )
        return source_schema

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __init__(
        self,
        folder_path: DirectoryPath,
        stream_id: str,
        verbose: bool = False,
        metadata_key: str = "SpikeGLXSync",
    ):
        """
        Read synchronization channel data from SpikeGLX Neuropixel probe recordings.

        The synchronization channel (SY0) is recorded as the last channel in imec probe streams
        and is used for timing alignment across multiple acquisition devices.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing the SpikeGLX .imec.ap.bin or .imec.lf.bin files.
        stream_id : str
            The stream ID for the sync channel. Must contain '-SYNC' and 'imec'.
            Examples: 'imec0.ap-SYNC', 'imec1.lf-SYNC'
        verbose : bool, default: False
            Whether to output verbose text.
        metadata_key : str, default: "SpikeGLXSync"
            Key used to organize metadata in the metadata dictionary. This is especially useful
            when multiple sync channel interfaces are used in the same conversion. The metadata_key is used
            to organize TimeSeries metadata.

        Raises
        ------
        ValueError
            If stream_id does not contain '-SYNC' and 'imec'.
        NotImplementedError
            If stream_id contains 'obx' (OneBox support not yet implemented).
        """
        # Validate stream_id
        if "-SYNC" not in stream_id:
            raise ValueError(
                f"stream_id must contain '-SYNC' for synchronization channels. Got: {stream_id}\n"
                f"Example valid stream_ids: 'imec0.ap-SYNC', 'imec1.lf-SYNC'"
            )

        if "obx" in stream_id:
            raise NotImplementedError(
                "OneBox (obx) synchronization channel support is not yet implemented. "
                "Only Neuropixel probe (imec) sync channels are currently supported."
            )

        self.folder_path = Path(folder_path)
        self.stream_id = stream_id
        self.metadata_key = metadata_key

        from spikeinterface.extractors.extractor_classes import (
            SpikeGLXRecordingExtractor,
        )

        self.recording_extractor = SpikeGLXRecordingExtractor(
            folder_path=self.folder_path,
            stream_id=self.stream_id,
            all_annotations=True,
        )

        super().__init__(
            verbose=verbose,
            folder_path=self.folder_path,
            stream_id=self.stream_id,
            metadata_key=self.metadata_key,
        )

        # Extract probe information from stream_id
        # Example: "imec0.ap-SYNC" -> _probe_index="0", _stream_kind="ap"
        base_stream_id = self.stream_id.replace("-SYNC", "")  # "imec0.ap"
        parts = base_stream_id.split(".")

        # Extract device (e.g., "imec0")
        device_part = parts[0]  # "imec0"
        self._probe_index = device_part.replace("imec", "")  # "0"

        # Extract stream kind (e.g., "ap" or "lf")
        if len(parts) > 1:
            self._stream_kind = parts[1].upper()  # "AP" or "LF"
        else:
            self._stream_kind = ""

        # Get metadata from the parent stream (sync channels share metadata with their parent stream)
        # The sync stream is derived from the parent stream, so we access metadata using the base stream_id
        signal_info_key = (0, base_stream_id)
        self._signals_info_dict = self.recording_extractor.neo_reader.signals_info_dict[signal_info_key]
        self._meta = self._signals_info_dict["meta"]

    def _get_session_start_time(self) -> datetime | None:
        """
        Fetches the session start time from the recording metadata.

        Returns
        -------
        datetime or None
            The session start time in datetime format.
        """
        session_start_time = self._meta.get("fileCreateTime", None)
        if session_start_time.startswith("0000-00-00"):
            # date was removed. This sometimes happens with human data to protect the
            # anonymity of medical patients.
            return
        if session_start_time:
            session_start_time = datetime.fromisoformat(session_start_time)

        return session_start_time

    def get_metadata(self) -> DeepDict:
        """
        Generate metadata for the sync channel TimeSeries.

        Returns
        -------
        DeepDict
            Metadata dictionary containing device and TimeSeries information.
        """
        metadata = super().get_metadata()

        session_start_time = self._get_session_start_time()
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Device metadata - link to the parent probe device
        device_name = f"NeuropixelsImec{self._probe_index}"
        device = dict(
            name=device_name,
            description=f"Neuropixels probe {self._probe_index} used with SpikeGLX.",
            manufacturer="Imec",
        )

        metadata["Devices"] = [device]

        # TimeSeries metadata for sync channel
        if "TimeSeries" not in metadata:
            metadata["TimeSeries"] = {}

        # Generate TimeSeries name based on probe only (band info in description)
        # Example: "TimeSeriesImec0Sync" for imec0.ap-SYNC or imec0.lf-SYNC
        # Multi-segment recordings will have segment suffix added automatically (e.g., "TimeSeriesImec0Sync0")
        timeseries_name = f"TimeSeriesImec{self._probe_index}Sync"

        metadata["TimeSeries"][self.metadata_key] = {
            "name": timeseries_name,
            "description": (
                f"Synchronization channel (SY0) from Neuropixel probe {self._probe_index} "
                f"{self._stream_kind} stream (stream: {self.stream_id}). Contains a 16-bit status word where bit 6 carries a 1 Hz "
                f"square wave (toggling between 0 and 1 every 0.5 seconds) used for sub-millisecond timing "
                f"alignment across acquisition devices and data streams. The other bits carry hardware status "
                f"and error flags. For NP1.0 probes, the sync channel appears identically in both AP and LF files. "
                f"The sync signal can be generated internally by the Imec module (PXIe or OneBox) or externally "
                f"by an NI-DAQ device acting as the master sync generator for multi-device setups."
            ),
        }

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        iterator_type: str | None = "v2",
        iterator_options: dict | None = None,
        always_write_timestamps: bool = False,
    ):
        """
        Add sync channel data to an NWB file as a TimeSeries.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the sync channel data will be added.
        metadata : dict | None, default: None
            Metadata dictionary with device and TimeSeries information.
            If None, uses default metadata from get_metadata().
        stub_test : bool, default: False
            If True, only writes a small amount of data for testing.
        iterator_type : str | None, default: "v2"
            Type of iterator to use for data streaming.
        iterator_options : dict | None, default: None
            Additional options for the iterator.
        always_write_timestamps : bool, default: False
            If True, always writes timestamps instead of using sampling rate.
        """
        from ....tools.spikeinterface import (
            _stub_recording,
            add_recording_as_time_series_to_nwbfile,
        )

        recording = self.recording_extractor
        if stub_test:
            recording = _stub_recording(recording=self.recording_extractor)

        metadata = metadata or self.get_metadata()

        # Add device (probe) if not already present
        device_metadata = metadata.get("Devices", [])
        for device in device_metadata:
            if device["name"] not in nwbfile.devices:
                nwbfile.create_device(**device)

        add_recording_as_time_series_to_nwbfile(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
            always_write_timestamps=always_write_timestamps,
            metadata_key=self.metadata_key,
        )
