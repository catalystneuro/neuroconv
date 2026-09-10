"""Derive discrete events from Intan USB-board ADC channels."""

from functools import partial
from pathlib import Path

from pydantic import FilePath, validate_call

from ._utils import _warn_if_split_siblings_detected
from ...events.baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools.events import _get_event_type_source_ids, _resolve_detection_plan, _validate_detection_configuration
from ....tools.signal_processing import _condition_signal, _detect_events, _frames_to_seconds

_ADC_STREAM_NAMES = ("USB board ADC input channel", "USB board ADC output channel")


class IntanAnalogEventsInterface(BaseEventsInterface):
    """Derive discrete events from Intan USB-board ADC input and output streams.

    This is the events counterpart to :class:`.IntanAnalogInterface`. It does not write the continuous
    traces, so callers may use either interface or both. ``detection_configuration`` is required: unlike
    an already-discrete digital line, an ADC trace has no lossless default event reading without a
    caller-selected cut point. :class:`.IntanDigitalInterface` can derive every line as ``"high_period"``
    events by default because its input is already binary; an ADC threshold instead establishes the event
    semantics.
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
        detection_configuration: dict[str, list[dict]],
        metadata_key: str | None = None,
        verbose: bool = False,
        saved_files_are_split: bool = False,
    ):
        """Initialize an Intan ADC events interface.

        Parameters
        ----------
        file_path : FilePath
            Path to an ``.rhd`` or ``.rhs`` file, or any chunk in a rotated session.
        detection_configuration : dict
            Required ``{channel_name: [spec, ...]}`` mapping across the available ADC input and output
            channels. Every spec states a caller-selected ``signal_conditioning={"binarize": cut}`` and
            a ``detection`` reading such as ``"rising"`` or ``"high_period"``. ``cut`` is in the source's
            stored ADC values, matching the raw ``IntanAnalogInterface`` trace and the shared
            signal-encoded-events convention. This differs from ``IntanDigitalInterface``, which needs no
            configuration because its input already has a lossless ``"high_period"`` reading.
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

        self._saved_files_are_split = saved_files_are_split
        self._recording_extractors = self._read_adc_streams(file_path, saved_files_are_split)
        self._available_signals = {
            str(channel_id): {"kind": "analog", "stream_name": stream_name, "channel_id": channel_id}
            for stream_name, recording in self._recording_extractors.items()
            for channel_id in recording.get_channel_ids()
        }
        if not self._available_signals:
            raise ValueError(f"'{file_path}' carries no channels in its ADC input or output streams.")
        _validate_detection_configuration(detection_configuration, self._available_signals)
        self._detection_configuration = detection_configuration

        super().__init__(
            file_path=file_path,
            detection_configuration=detection_configuration,
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

    def get_event_type_source_ids(self) -> list[str]:
        """The event types the configuration resolves to."""
        return _get_event_type_source_ids(self._detection_configuration)

    def get_metadata(self) -> dict:
        """Seed one event type per configured derived event without reading the ADC trace."""
        metadata = super().get_metadata()
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        for event_type_source_id in self.get_event_type_source_ids():
            event_types[event_type_source_id] = {"event_name": event_type_source_id}
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Condition configured ADC channels and read their transitions, cached after the first call."""
        if self._events_data_dict is not None:
            return self._events_data_dict

        detection_plan = _resolve_detection_plan(self._detection_configuration)
        events_data_dict = {}
        for signal_source_id, detection_specs in detection_plan.items():
            signal = self._available_signals[signal_source_id]
            recording = self._recording_extractors[signal["stream_name"]]
            trace = recording.get_traces(channel_ids=[signal["channel_id"]])[:, 0]
            read_clock = partial(recording.sample_index_to_time, segment_index=0)
            for event_type_source_id, spec in detection_specs:
                conditioned = _condition_signal(trace, spec["signal_conditioning"])
                onset_frames, offset_frames = _detect_events(conditioned, spec["detection"])
                onsets, durations = _frames_to_seconds(onset_frames, offset_frames, read_clock)
                events_data_dict[event_type_source_id] = _EventsData(
                    event_type_source_id=event_type_source_id, timestamps=onsets, durations=durations
                )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
