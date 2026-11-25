"""Derive discrete events from Intan USB-board ADC channels."""

from functools import partial
from pathlib import Path

from pydantic import FilePath, validate_call

from ._utils import _warn_if_split_siblings_detected
from ...events.baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools.signal_processing import _detect_occurrences

_ADC_STREAM_NAMES = ("USB board ADC input channel", "USB board ADC output channel")


class IntanAnalogEventsInterface(BaseEventsInterface):
    """Derive discrete events from Intan USB-board ADC input and output streams.

    This is the events counterpart to :class:`.IntanAnalogInterface`. It does not write the continuous
    traces, so callers may use either interface or both. ``event_extraction_configuration`` is required:
    an ADC trace has no default event reading, because nothing in the file says where on begins.
    """

    display_name = "Intan Analog Events"
    keywords = ("intan", "analog", "ADC", "events", "rhd", "rhs")
    associated_suffixes = (".rhd", ".rhs")
    info = "Interface for deriving discrete events from Intan USB-board ADC channels."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        event_extraction_configuration: dict[str, dict],
        metadata_key: str | None = None,
        verbose: bool = False,
        saved_files_are_split: bool = False,
    ):
        """Initialize an Intan ADC events interface.

        Parameters
        ----------
        file_path : FilePath
            Path to an ``.rhd`` or ``.rhs`` file, or any chunk in a rotated session.
        event_extraction_configuration : dict
            Entries keyed by the event type identifier. Each entry names an ADC channel in ``source``
            (``"ANALOG-IN-1"``, ``"ANALOG-OUT-1"``), cuts it into a line with
            ``signal_conditioning={"binarize": cut}`` and says which changes are events with
            ``detection={"on_change": {"onset": ...}}``. ``cut`` is in the stored ADC values, matching the
            raw ``IntanAnalogInterface`` trace, or ``"midpoint"``.
        metadata_key : str, optional
            The key under ``metadata["Events"]``. Defaults to ``"intan_analog_events"``.
        verbose : bool, default: False
            Whether to print status messages.
        saved_files_are_split : bool, default: False
            Concatenate rotated sibling files before detection.
        """
        file_path = str(file_path)
        if not saved_files_are_split:
            _warn_if_split_siblings_detected(Path(file_path), interface_name="IntanAnalogEventsInterface")

        self._recording_extractors = self._read_adc_streams(file_path, saved_files_are_split)
        self._channel_streams = {
            str(channel_id): stream_name
            for stream_name, recording in self._recording_extractors.items()
            for channel_id in recording.get_channel_ids()
        }
        if not self._channel_streams:
            raise ValueError(f"'{file_path}' carries no channels in its ADC input or output streams.")
        available_sources = {
            channel: {"supported_operations": ["signal_conditioning", "detection"]} for channel in self._channel_streams
        }
        self._event_extraction_configuration = self._resolve_event_sources(
            event_extraction_configuration, available_sources
        )

        super().__init__(
            file_path=file_path,
            event_extraction_configuration=event_extraction_configuration,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "intan_analog_events"

    @staticmethod
    def _read_adc_streams(file_path: str, saved_files_are_split: bool) -> dict:
        from spikeinterface.extractors import get_neo_streams, read_intan, read_split_intan_files

        stream_names, _ = get_neo_streams("intan", file_path=file_path)

        def read_stream(stream_name: str):
            if saved_files_are_split:
                return read_split_intan_files(
                    folder_path=Path(file_path).parent, stream_name=stream_name, all_annotations=True
                )
            return read_intan(file_path=file_path, stream_name=stream_name, all_annotations=True)

        return {
            stream_name: read_stream(stream_name) for stream_name in _ADC_STREAM_NAMES if stream_name in stream_names
        }

    @classmethod
    def get_available_event_sources(cls, file_path: FilePath) -> list[str]:
        """List all analog input and output channels in the file's header."""
        streams = cls._read_adc_streams(str(file_path), saved_files_are_split=False)
        return [str(channel) for recording in streams.values() for channel in recording.get_channel_ids()]

    def get_event_type_source_ids(self) -> list[str]:
        """The event types the configuration names."""
        return list(self._event_extraction_configuration)

    def get_metadata(self) -> dict:
        """Seed one event type per configured entry without reading the ADC trace."""
        metadata = super().get_metadata()
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        for event_type_source_id in self.get_event_type_source_ids():
            event_types[event_type_source_id] = {"event_name": event_type_source_id}
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Condition configured ADC channels and read their transitions, cached after the first call."""
        if self._events_data_dict is not None:
            return self._events_data_dict

        events_data_dict = {}
        for event_type_source_id, entry in self._event_extraction_configuration.items():
            recording = self._recording_extractors[self._channel_streams[entry["source"]]]
            trace = recording.get_traces(channel_ids=[entry["source"]])[:, 0]
            onsets, durations = _detect_occurrences(
                entry=entry,
                trace=trace,
                timestamps=partial(recording.sample_index_to_time, segment_index=0),
            )
            events_data_dict[event_type_source_id] = _EventsData(
                event_type_source_id=event_type_source_id, timestamps=onsets, durations=durations
            )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
