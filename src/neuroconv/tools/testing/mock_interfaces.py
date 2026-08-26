import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np
from pynwb import NWBFile
from pynwb.base import DynamicTable

from .mock_ttl_signals import generate_mock_ttl_signal
from ...basedatainterface import BaseDataInterface
from ...basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ...datainterfaces import SpikeGLXNIDQInterface
from ...datainterfaces.behavior.baseposeestimationinterface import (
    BasePoseEstimationInterface,
)
from ...datainterfaces.behavior.video.externalvideointerface import (
    ExternalVideoInterface,
)
from ...datainterfaces.ecephys.baserecordingextractorinterface import (
    BaseRecordingExtractorInterface,
)
from ...datainterfaces.ecephys.basesortingextractorinterface import (
    BaseSortingExtractorInterface,
)
from ...datainterfaces.events.baseeventsinterface import (
    BaseEventsInterface,
    _EventsData,
)
from ...datainterfaces.fiber_photometry.basefiberphotometryinterface import (
    BaseFiberPhotometryInterface,
)
from ...datainterfaces.ophys.baseimagingextractorinterface import (
    BaseImagingExtractorInterface,
)
from ...datainterfaces.ophys.basesegmentationextractorinterface import (
    BaseSegmentationExtractorInterface,
)
from ...tools.events import (
    _get_event_type_source_ids,
    _resolve_detection_plan,
    _validate_detection_configuration,
)
from ...tools.icephys import _RESPONSE_CLASS, _add_intracellular_electrode_to_nwbfile
from ...tools.signal_processing import (
    _condition_signal,
    _detect_events,
    _frames_to_seconds,
)
from ...utils import (
    ArrayType,
    calculate_regular_series_rate,
    get_json_schema_from_method_signature,
    to_camel_case,
)
from ...utils.dict import DeepDict


class MockInterface(BaseDataInterface):
    """
    A mock interface for testing basic command passing without side effects.
    """

    def __init__(self, verbose: bool = False, **source_data):

        super().__init__(verbose=verbose, **source_data)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        session_start_time = datetime.now().astimezone()
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None, add_subject: bool = False):
        """Add a mock subject to the NWBFile when asked to, and nothing otherwise.

        The one conversion option this interface takes, so that a test can assert an option reached it by
        reading the file it wrote rather than by reading state off the interface.
        """
        if add_subject:
            from pynwb.testing.mock.file import mock_Subject

            nwbfile.subject = mock_Subject()


class MockTimeSeriesInterface(BaseDataInterface):
    """
    A mock TimeSeries interface for testing purposes.

    This interface uses pynwb's mock_TimeSeries to create synthetic time series data
    without only pynwb as a dependency.
    """

    def __init__(
        self,
        *,
        num_channels: int = 4,
        sampling_frequency: float = 30_000.0,
        duration: float = 1.0,
        seed: int = 0,
        verbose: bool = False,
        metadata_key: str = "TimeSeries",
    ):
        """
        Initialize a mock TimeSeries interface.

        Parameters
        ----------
        num_channels : int, optional
            Number of channels to generate, by default 4.
        sampling_frequency : float, optional
            Sampling frequency in Hz, by default 30,000.0 Hz.
        duration : float, optional
            Duration of the data in seconds, by default 1.0.
        seed : int, optional
            Seed for the random number generator, by default 0.
        verbose : bool, optional
            Control verbosity, by default False.
        metadata_key : str, optional
            Key for the TimeSeries metadata in the metadata dictionary, by default "TimeSeries".
        """
        self.num_channels = num_channels
        self.sampling_frequency = sampling_frequency
        self.duration = duration
        self.seed = seed
        self.metadata_key = metadata_key

        super().__init__(verbose=verbose)

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the TimeSeries interface.

        Returns
        -------
        dict
            The metadata dictionary containing NWBFile and TimeSeries metadata.
        """
        metadata = super().get_metadata()
        session_start_time = datetime.now().astimezone()
        metadata["NWBFile"]["session_start_time"] = session_start_time

        # Add TimeSeries metadata using the metadata_key
        metadata["TimeSeries"] = {
            self.metadata_key: {
                "name": self.metadata_key,
                "description": f"Mock TimeSeries data with {self.num_channels} channels",
                "unit": "n.a.",
            }
        }

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
    ):
        """
        Add mock TimeSeries data to an NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the TimeSeries data will be added.
        metadata : dict, optional
            Metadata dictionary. If None, uses default metadata.
        """
        from pynwb.testing.mock.base import mock_TimeSeries

        if metadata is None:
            metadata = self.get_metadata()

        # Generate mock data
        rng = np.random.default_rng(self.seed)
        num_samples = int(self.duration * self.sampling_frequency)
        data = rng.standard_normal(size=(num_samples, self.num_channels)).astype("float32")

        # Get TimeSeries kwargs from metadata
        time_series_metadata = metadata.get("TimeSeries", {}).get(self.metadata_key, {})

        tseries_kwargs = {
            "name": time_series_metadata.get("name", "MockTimeSeries"),
            "description": time_series_metadata.get("description", "Mock TimeSeries data"),
            "unit": time_series_metadata.get("unit", "n.a."),
            "data": data,
            "starting_time": 0.0,
            "rate": self.sampling_frequency,
        }

        # Apply any additional metadata
        for key in ["comments", "conversion", "offset"]:
            if key in time_series_metadata:
                tseries_kwargs[key] = time_series_metadata[key]

        time_series = mock_TimeSeries(**tseries_kwargs)
        nwbfile.add_acquisition(time_series)


class MockBehaviorEventInterface(BaseTemporalAlignmentInterface):
    """
    A mock behavior event interface for testing purposes.
    """

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["event_times"])
        source_schema["additionalProperties"] = True
        return source_schema

    def __init__(self, event_times: ArrayType | None = None):
        """
        Initialize the interface with event times for behavior.

        Parameters
        ----------
        event_times : list of floats, optional
            The event times to set as timestamps for this interface.
            The default is the array [1.2, 2.3, 3.4] to simulate a time series similar to the
            MockSpikeGLXNIDQInterface.
        """
        event_times = event_times or [1.2, 2.3, 3.4]
        self.event_times = np.array(event_times)
        self.original_event_times = np.array(event_times)  # Make a copy of the initial loaded timestamps

    def get_original_timestamps(self) -> np.ndarray:
        """
        Get the original event times before any alignment or transformation.

        Returns
        -------
        np.ndarray
            The original event times as a NumPy array.
        """
        return self.original_event_times

    def get_timestamps(self) -> np.ndarray:
        """
        Get the current (possibly aligned) event times.

        Returns
        -------
        np.ndarray
            The current event times as a NumPy array, possibly modified after alignment.
        """
        return self.event_times

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        """
        Set the event times after alignment.

        Parameters
        ----------
        aligned_timestamps : np.ndarray
            The aligned event timestamps to update the internal event times.
        """
        self.event_times = aligned_timestamps

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        """
        Add the event times to an NWBFile as a DynamicTable.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the event times will be added.
        metadata : dict
            Metadata to describe the event times in the NWB file.

        Notes
        -----
        This method creates a DynamicTable to store event times and adds it to the NWBFile's acquisition.
        """
        table = DynamicTable(name="BehaviorEvents", description="Times of various classified behaviors.")
        table.add_column(name="event_time", description="Time of each event.")
        for timestamp in self.get_timestamps():
            table.add_row(event_time=timestamp)
        nwbfile.add_acquisition(table)


class MockEventsInterface(BaseEventsInterface):
    """A configurable mock events interface for exercising the ``EventsTable`` writer without a real
    acquisition format.

    Generates ``num_event_types`` synthetic event types, each keyed by its own id (``"events"`` for a
    single type, else ``"events_0" .. "events_{N-1}"``) and, by default, its own table. Their shape is
    set by two taxonomy axes describing the generated *data*: ``event_extent`` (point vs event with
    duration) and ``event_payload`` (timestamps only / a single categorical value / a multi-value
    struct); both apply to every type. Timestamps are staggered across types so pooling several into
    one table interleaves in time. Data is deterministic (no ``seed`` needed). Everything else a test
    exercises, renaming a column, merging types into one table (repoint their ``table_metadata_key``),
    dropping the meanings map, lives in the returned metadata and is driven by editing it, not by a
    constructor flag.
    """

    def __init__(
        self,
        *,
        metadata_key: str | None = None,
        num_event_types: int = 1,
        num_events: int = 4,
        event_extent: Literal["point event", "event with duration"] = "point event",
        event_payload: Literal["timestamps only", "single value", "multi value"] = "timestamps only",
        verbose: bool = False,
    ):
        """Initialize a mock events interface.

        Parameters
        ----------
        metadata_key : str, optional
            The key under ``metadata["Events"]`` namespacing this interface's ``event_types``.
            If None (default), ``"mock_events"`` is used.
        num_event_types : int, optional
            How many event types (streams) to generate, by default 1. Each gets its own id and, by
            default, its own table; a test merges them by repointing their ``table_metadata_key`` at a
            shared table.
        num_events : int, optional
            Number of events (timestamps) generated per event type, by default 4.
        event_extent : {"point event", "event with duration"}, optional
            The temporal extent of the generated events (the taxonomy's Extent axis). ``"point event"``
            (default) generates timestamp-only events; ``"event with duration"`` gives each event a
            duration, so the writer adds a ``duration`` column. Applies to every event type.
        event_payload : {"timestamps only", "single value", "multi value"}, optional
            The payload carried per event (the taxonomy's Payload axis). ``"timestamps only"``
            (default) is a timestamp-only event with no value column; ``"single value"`` carries one
            categorical field (a labeled column with a ``MeaningsTable``); ``"multi value"`` carries a
            three-field struct that fans into three columns on the same rows, one per way the writer
            treats a value column: ``outcome`` (labels and meanings, so a ``MeaningsTable``), ``cue``
            (labels but nothing to explain, so no ``MeaningsTable``), and ``amplitude`` (raw numeric
            values). Applies to every event type.
        verbose : bool, optional
            Whether to print status messages, by default False.
        """
        self._num_event_types = num_event_types
        self._num_events = num_events
        self._event_extent = event_extent
        self._event_payload = event_payload
        super().__init__(verbose=verbose)
        self.metadata_key = metadata_key or "mock_events"

    def _event_type_source_ids(self) -> list[str]:
        # A single type keeps the plain "events" id; several are indexed so their ids (and, by default,
        # their tables and column names) stay unique.
        if self._num_event_types == 1:
            return ["events"]
        return [f"events_{index}" for index in range(self._num_event_types)]

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        for index, event_type_source_id in enumerate(self._event_type_source_ids()):
            suffix = "" if self._num_event_types == 1 else f"_{index}"
            # One branch per payload mode, spelled out in full rather than composed from shared pieces:
            # between them the modes cover the three ways the writer treats a value column, and stating
            # each mode's columns outright is what makes which-mode-covers-which readable.
            if self._event_payload == "timestamps only":
                # No value column at all.
                columns = {}
            elif self._event_payload == "single value":
                # One categorical column declaring labels and meanings: display labels plus a MeaningsTable.
                columns = {
                    "outcome": {
                        "column_name": f"outcome{suffix}",
                        "description": "The outcome of each event.",
                        "column_categories": {
                            "labels": {0: "go", 1: "no_go"},
                            "meanings": {0: "A go outcome.", 1: "A no-go outcome."},
                        },
                    },
                }
            elif self._event_payload == "multi value":
                # A struct payload fanned into three columns on the same rows, one per way the writer
                # treats a value column: 'outcome' as above, 'cue' declaring labels whose meaning is
                # self-evident (so no meanings and no MeaningsTable), and 'amplitude' as raw numbers.
                columns = {
                    "outcome": {
                        "column_name": f"outcome{suffix}",
                        "description": "The outcome of each event.",
                        "column_categories": {
                            "labels": {0: "go", 1: "no_go"},
                            "meanings": {0: "A go outcome.", 1: "A no-go outcome."},
                        },
                    },
                    "cue": {
                        "column_name": f"cue{suffix}",
                        "description": "The cue presented with each event.",
                        "column_categories": {"labels": {0: "tone", 1: "light"}},
                    },
                    "amplitude": {
                        "column_name": f"amplitude{suffix}",
                        "description": "The amplitude of each event.",
                    },
                }
            # No EventTables entry: a solo type names its own table from event_name (CamelCased). A merge
            # test repoints these types' table_metadata_key at a shared key and declares the table there.
            # Only what the source actually carries: no event_description (the mock has none to report),
            # and no columns key at all for a timestamps-only type.
            entry = {"event_name": event_type_source_id}
            if columns:
                entry["columns"] = columns
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = entry
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        if self._events_data_dict is not None:
            return self._events_data_dict

        duration = 0.05 if self._event_extent == "event with duration" else None
        events_data_dict = {}
        for index, event_type_source_id in enumerate(self._event_type_source_ids()):
            # Stagger timestamps across types so pooling several into one table interleaves in time.
            timestamps = 0.1 * (np.arange(self._num_events) * self._num_event_types + index + 1)
            durations = np.full(self._num_events, duration) if duration is not None else None
            # One branch per payload mode, matching the columns get_metadata declares for that mode.
            if self._event_payload == "timestamps only":
                payload = {}
            elif self._event_payload == "single value":
                payload = {"outcome": np.arange(self._num_events) % 2}  # alternating go / no_go
            elif self._event_payload == "multi value":
                payload = {
                    "outcome": np.arange(self._num_events) % 2,  # alternating go / no_go
                    "cue": (np.arange(self._num_events) // 2) % 2,  # tone, tone, light, light, ...
                    "amplitude": np.arange(self._num_events, dtype="float64"),
                }
            events_data_dict[event_type_source_id] = _EventsData(
                event_type_source_id=event_type_source_id,
                timestamps=timestamps,
                durations=durations,
                payload=payload,
            )

        self._events_data_dict = events_data_dict
        return self._events_data_dict


class MockSignalEncodedEventsInterface(BaseEventsInterface):
    """A mock **signal-encoded** events interface: a synthetic digital word, real derivation machinery.

    Where :class:`MockEventsInterface` hands the writer finished event records, this one starts a step
    earlier, from a sampled signal that still has to be discretized, so it exercises the part of the
    stack every signal-encoded interface shares: the ``detection_configuration`` grammar, the
    conditioning and detection split in :mod:`neuroconv.tools.signal_processing`, and the frame-to-seconds
    adapter. Only discovery is faked; everything after it is the shipped code path.

    It speaks the **packed-word dialect** deliberately. One line per signal is the degenerate shape and
    cannot exercise one-signal-to-many, so it would bless the wrong abstraction; a word whose bits are
    carved out by ``bits`` is the general case that Intan and the National Instruments data acquisition
    (NIDQ) board both need.

    ``digital_line_waveforms`` is the core knob and *is* the synthetic word: it says which bit positions
    the format recorded and what each line does. ``detection_configuration`` then says what the user
    carves out of it. That existence-versus-selection split is what makes selection, defaults and
    absent-bit errors testable. Configuration describes what to generate; the mock never takes data
    arrays.

    ``analog_waveforms`` adds continuous signals alongside the word. They were originally planned as a
    separate mock, on the grounds that cutting a continuous trace is distinct enough from the ``bits``
    carve to test apart from it. They live here because the conditioning machinery turned out to be
    shared rather than parallel: a given cut and a derived one are the same ``binarize`` in the same
    :func:`~neuroconv.tools.signal_processing._condition_signal`, so a mock that exercises one and not the
    other leaves shipped code with no end-to-end coverage. Hysteresis, the genuinely analog-only knob, is
    still unbuilt and is what a separate mock would be for.
    """

    def __init__(
        self,
        *,
        digital_line_waveforms: (
            dict[
                int,
                Literal["pulses", "idle", "unclosed_pulses"] | tuple[str, Literal["pulses", "idle", "unclosed_pulses"]],
            ]
            | None
        ) = None,
        analog_waveforms: dict[str, Literal["levels", "noisy_two_level"]] | None = None,
        detection_configuration: dict | None = None,
        duration: float = 1.0,
        num_events: int = 4,
        sampling_frequency: float = 1000.0,
        sampling: Literal["regular", "irregular"] = "regular",
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize a mock signal-encoded events interface.

        Parameters
        ----------
        digital_line_waveforms : dict, optional
            The synthetic word: ``{bit position: waveform kind}``, or ``{bit position: (line name,
            waveform kind)}`` to name the line. The keys are the recorded bit inventory, reaching the
            validator as the word descriptor's ``bits``, and they need not be contiguous, so a
            configuration naming a bit the word does not carry can be exercised in the gap as well as
            past the end. No real fixture can state the gap case, since every ``.nidq.meta`` anyone has
            declares ``niXDChans1=0:7``. A named line becomes
            that event type's identifier under the default configuration (the ``event_name`` route,
            rule 3); an unnamed one falls to the derived form, ``word_bit0_high_period``. Naming is what
            keeps the default legible, at the price of the default no longer exercising derivation, so a
            test that cares about derived identifiers passes bare waveform kinds. Each waveform kind is
            one of:

            - ``"pulses"`` (the ordinary line): ``num_events`` complete pulses, which ``detection`` then
              reads four ways.
            - ``"idle"``: no edges at all, a line that was recorded and never fired, which is the
              zero-row table path and is unreachable from a ``"pulses"`` line under any reading.
            - ``"unclosed_pulses"``: ``num_events`` pulses whose last one stays high to the end, which is
              the NaN-duration path, kept separate so not every durative test carries a NaN.

            Defaults to ``{0: ("lick", "pulses"), 1: ("reward", "idle")}``: one line that fires and one
            recorded line that never did, the second being the zero-row table path.
        analog_waveforms : dict, optional
            Continuous signals to expose alongside the word, ``{signal_source_id: waveform kind}``. Each
            key is a ``signal_source_id``, naming a signal of kind ``"analog"`` that
            ``detection_configuration`` then addresses the way it addresses ``"word"``; the caller picks
            it, since a mock discovers nothing from a file. It names a signal, not an event type, though
            a signal given a single spec keeps its ``signal_source_id`` as that event type's identifier.
            A digital line is not one of these, being a bit inside the single packed word rather than a
            signal of its own, and ``"word"`` itself is reserved. Each value is one of:

            - ``"levels"``: a trace stepping through four amplitudes, which no edge reading can read
              without being told where to cut, so it is what a given ``binarize`` cut point needs.
            - ``"noisy_two_level"``: a trace that is conceptually a line and numerically is not, sitting
              near two amplitudes with jitter on every sample, which is what ``binarize`` exists for.

            Defaults to none, keeping the mock digital-only unless a test asks otherwise.
        detection_configuration : dict, optional
            What to carve out of the word, exactly as on a real interface. If None (default), every
            recorded bit becomes its own event type at ``high_period``, which is lossless and assumes the
            lines are independent.
        duration : float, optional
            Signal length in seconds, by default 1.0.
        num_events : int, optional
            Pulses generated per active line, by default 4.
        sampling_frequency : float, optional
            Samples per second, by default 1000.0. With ``duration`` this fixes the frame count, and it
            is what makes timestamps land in seconds rather than frames.
        sampling : {"regular", "irregular"}, optional
            The clock. ``"regular"`` (default) steps by ``1 / sampling_frequency``. ``"irregular"`` keeps
            the frame count and stretches one gap, which is the only way to tell a duration read from the
            clock apart from one estimated off a median sampling period. No real fixture in the suite
            samples irregularly.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` namespacing this interface's ``event_types``. If None
            (default), ``"mock_signal_encoded_events"`` is used.
        verbose : bool, optional
            Whether to print status messages, by default False.
        """
        # A value is either a bare waveform kind or a (line name, waveform kind) pair, so the two are
        # split apart here and the rest of the class sees two plain dicts.
        entries = dict(digital_line_waveforms or {0: ("lick", "pulses"), 1: ("reward", "idle")})
        self._digital_line_waveforms = {
            bit: entry[1] if isinstance(entry, tuple) else entry for bit, entry in entries.items()
        }
        self._digital_line_names = {bit: entry[0] for bit, entry in entries.items() if isinstance(entry, tuple)}
        unknown_kinds = set(self._digital_line_waveforms.values()) - {
            "pulses",
            "idle",
            "unclosed_pulses",
        }
        if unknown_kinds:
            raise ValueError(
                f"Unknown waveform kind(s) {sorted(unknown_kinds)}; valid kinds are pulses, idle, " "unclosed_pulses."
            )
        self._analog_waveforms = dict(analog_waveforms or {})
        unknown_kinds = set(self._analog_waveforms.values()) - {
            "levels",
            "noisy_two_level",
        }
        if unknown_kinds:
            raise ValueError(
                f"Unknown analog waveform kind(s) {sorted(unknown_kinds)}; valid kinds are levels, " "noisy_two_level."
            )
        if self.SIGNAL_SOURCE_ID in self._analog_waveforms:
            raise ValueError(f"'{self.SIGNAL_SOURCE_ID}' is the packed word's handle; name analog signals differently.")
        self._duration = duration
        self._num_events = num_events
        self._sampling_frequency = sampling_frequency
        self._sampling = sampling
        super().__init__(verbose=verbose)
        self.metadata_key = metadata_key or "mock_signal_encoded_events"

        # Discovery, faked: one packed word, whose kind is what makes bit selection legal on it and a
        # magnitude cut illegal, and whose `bits` are the positions it carries. A real interface
        # settles both from its file's structure: SpikeGLX declares the inventory as niXDChans1, and the
        # keys of digital_line_waveforms stand in for that declaration here.
        self._available_signals = {
            self.SIGNAL_SOURCE_ID: {
                "kind": "word",
                "bits": sorted(self._digital_line_waveforms),
            }
        }
        self._available_signals.update({name: {"kind": "analog"} for name in self._analog_waveforms})
        if detection_configuration is None:
            detection_configuration = self._default_detection_configuration()
        # One construction-time check, on the default as well as on a caller-supplied configuration: the
        # default is machine-built but its inputs are not, so it too can resolve two event types to the
        # same identifier. Validation covers structure and identifier resolution (rules 4 and 5) alike.
        _validate_detection_configuration(detection_configuration, self._available_signals)
        self._detection_configuration = detection_configuration

    SIGNAL_SOURCE_ID = "word"

    def _default_detection_configuration(self) -> dict:
        """Every recorded bit as its own event type at ``high_period``.

        Lossless and reconstructable, and it assumes the lines are independent, which is the common case
        but wrong for a trial-code word. A coded word therefore cannot be reached by this path and has to
        be configured explicitly.
        """
        # Analog signals are absent from this: a continuous trace has no defensible default cut, and
        # inventing one fabricates events. "midpoint" is defensible only for a signal already two-valued.
        specs = []
        # Fanned out over the word descriptor's declared inventory rather than over the waveforms
        # directly, which is the same loop a real interface runs over the positions its header declares.
        for bit in self._available_signals[self.SIGNAL_SOURCE_ID]["bits"]:
            spec = {"signal_conditioning": {"bits": [bit]}, "detection": "high_period"}
            line_name = self._digital_line_names.get(bit)
            if line_name is not None:
                # A named line pins its own identifier instead of taking the derived one, which is what
                # makes the default read as an experiment rather than as bit arithmetic.
                spec["event_name"] = line_name
            specs.append(spec)
        return {self.SIGNAL_SOURCE_ID: specs}

    @property
    def _num_samples(self) -> int:
        return int(self._duration * self._sampling_frequency)

    def _get_timestamps(self) -> np.ndarray:
        """The clock the word is sampled on."""
        timestamps = np.arange(self._num_samples, dtype="float64") / self._sampling_frequency
        if self._sampling == "irregular":
            # One long gap partway through. The frame count across it is unchanged, so a duration
            # spanning it is only right if it was read from the clock rather than estimated from it.
            timestamps[self._num_samples // 2 :] += self._duration
        return timestamps

    def _get_line(self, kind: str) -> np.ndarray:
        """Build one 0/1 line deterministically from its waveform kind."""
        num_samples = self._num_samples
        line = np.zeros(num_samples, dtype="int64")
        if kind == "idle":
            return line  # recorded and never fired: no edges at all

        # Evenly spaced pulses, each high for a third of its period, so every pulse is complete and the
        # onsets are predictable from num_events alone.
        period = num_samples // (self._num_events + 1)
        width = max(1, period // 3)
        for index in range(self._num_events):
            start = period * (index + 1)
            line[start : start + width] = 1
        if kind == "unclosed_pulses":
            line[period * self._num_events :] = 1  # the last pulse never closes
        return line

    def _get_word(self) -> np.ndarray:
        """Pack every recorded line into one integer signal, which is what the interface exposes."""
        word = np.zeros(self._num_samples, dtype="int64")
        for bit, kind in self._digital_line_waveforms.items():
            word |= self._get_line(kind) << int(bit)
        return word

    def _get_analog_trace(self, kind: str) -> np.ndarray:
        """Build one continuous signal deterministically from its waveform kind."""
        num_samples = self._num_samples
        step = num_samples // 5
        if kind == "levels":
            trace = np.full(num_samples, 0.5, dtype="float64")
            for index, level in enumerate((1.5, 2.5, 3.5), start=1):
                trace[step * index : step * (index + 1)] = level
            return trace
        # noisy_two_level: conceptually a line, numerically not one. Deterministic jitter, no seed needed.
        jitter = 0.05 * np.sin(np.arange(num_samples, dtype="float64"))
        trace = np.full(num_samples, 48.0) + jitter
        trace[step : step * 2] = 64.0 + jitter[step : step * 2]
        trace[step * 3 : step * 4] = 64.0 + jitter[step * 3 : step * 4]
        return trace

    def _get_signal(self, signal_source_id: str) -> np.ndarray:
        """The trace the interface exposes for one signal, word or analog."""
        if signal_source_id == self.SIGNAL_SOURCE_ID:
            return self._get_word()
        return self._get_analog_trace(self._analog_waveforms[signal_source_id])

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        # Derived from the configuration, so metadata costs no signal generation, does not depend on a
        # plan existing, and lists exactly what will be written, including a line that never fired.
        for event_type_source_id in _get_event_type_source_ids(self._detection_configuration):
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = {
                "event_name": event_type_source_id
            }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Derive events from the synthetic word through the shared machinery, cached."""
        if self._events_data_dict is not None:
            return self._events_data_dict

        # Built here rather than held on the interface: the configuration is the source of truth, and the
        # plan is pure and cheap to rebuild. Grouped by signal, so the word is packed once however many
        # bits are carved out of it. This is the loop a sixteen-bit Intan or NIDQ interface will copy.
        detection_plan = _resolve_detection_plan(self._detection_configuration)

        timestamps = self._get_timestamps()
        events_data_dict = {}
        for signal_source_id, detection_specs in detection_plan.items():
            signal = self._get_signal(signal_source_id)
            for event_type_source_id, spec in detection_specs:
                conditioned = _condition_signal(signal, spec["signal_conditioning"])
                onset_frames, offset_frames = _detect_events(conditioned, spec["detection"])
                onsets, durations = _frames_to_seconds(onset_frames, offset_frames, timestamps)
                events_data_dict[event_type_source_id] = _EventsData(
                    event_type_source_id=event_type_source_id,
                    timestamps=onsets,
                    durations=durations,
                )

        self._events_data_dict = events_data_dict
        return self._events_data_dict


class MockFiberPhotometryInterface(BaseFiberPhotometryInterface):
    """A mock acquisition fiber photometry interface backed by synthetic data.

    Writes one ``FiberPhotometryResponseSeries`` from a synthetic trace, so the
    ``ndx-fiber-photometry`` write/read path is exercised with no data on disk.

    """

    def __init__(
        self,
        *,
        excitation_wavelengths_in_nm: float | list[float] = 470.0,
        num_fibers: int = 1,
        num_samples: int = 100,
        sampling_frequency: float = 100.0,
        seed: int = 0,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize a mock fiber photometry interface.

        Parameters
        ----------
        excitation_wavelengths_in_nm : float or list of float, default: 470.0
            The excitation wavelength(s) this interface's series carries, one source stream each.
            ndx-fiber-photometry recommends one series per excitation/emission wavelength, so the
            default is a single wavelength and a second one is a second interface writing its own
            series into the same table. Passing a list aggregates over the wavelength axis instead,
            which asserts that they share a clock: true of a frequency-multiplexed (lock-in) rig where
            every LED is on at once, false of a time-multiplexed one where they alternate.
        num_fibers : int, default: 1
            How many fibers the series carries, one column per fiber. Columns are wavelength-major,
            so two wavelengths and two fibers give ``[w0f0, w0f1, w1f0, w1f1]``, and
            ``fiber_photometry_table_region`` has to list its row keys in that order. A single fiber
            reads as a 1-D array, several as ``(num_samples, num_fibers)``, which is the shape a real
            multi-fiber acquisition store returns.
        num_samples : int, default: 100
            Number of samples in the synthetic response series.
        sampling_frequency : float, default: 100.0
            Sampling frequency (Hz) of the synthetic response series.
        seed : int, default: 0
            Seed for the synthetic data.
        metadata_key : str, optional
            Override the response-series metadata key (default derived from the wavelengths).
        verbose : bool, default: False
            Whether to print status messages.
        """
        if isinstance(excitation_wavelengths_in_nm, (int, float)):
            excitation_wavelengths_in_nm = [excitation_wavelengths_in_nm]
        self._excitation_wavelengths_in_nm = [float(wavelength) for wavelength in excitation_wavelengths_in_nm]
        if not self._excitation_wavelengths_in_nm:
            raise ValueError("excitation_wavelengths_in_nm must name at least one excitation wavelength.")
        if int(num_fibers) < 1:
            raise ValueError(f"num_fibers must be at least 1, got {num_fibers}.")
        self._num_fibers = int(num_fibers)
        self._num_samples = int(num_samples)
        self._sampling_frequency = float(sampling_frequency)
        self._seed = int(seed)
        # One source stream per wavelength, named after it so the derived metadata_key is readable.
        stream_names = [f"{wavelength:g}nm" for wavelength in self._excitation_wavelengths_in_nm]
        super().__init__(stream_names=stream_names, metadata_key=metadata_key, verbose=verbose)

    def _get_stream_data(self, *, stream_name: str) -> np.ndarray:
        # Deterministic per-wavelength synthetic trace (a distinct seed each, so the traces differ).
        index = self.stream_names.index(stream_name)
        rng = np.random.default_rng(self._seed + index)
        # Drawing a 1-D array for a single fiber (rather than slicing an (N, 1) one) keeps the
        # default draw identical to the single-fiber case.
        size = self._num_samples if self._num_fibers == 1 else (self._num_samples, self._num_fibers)
        return rng.standard_normal(size).astype("float64")

    def _get_stream_timestamps(self, *, stream_name: str) -> np.ndarray:
        return np.arange(self._num_samples, dtype="float64") / self._sampling_frequency

    def get_metadata(self) -> DeepDict:
        """Return the base metadata with a fixed session start time; no fiber photometry provenance."""
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
        return metadata


class MockSpikeGLXNIDQInterface(SpikeGLXNIDQInterface):
    """
    A mock SpikeGLX interface for testing purposes.
    """

    ExtractorName = "NumpyRecording"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["ttl_times"])
        source_schema["additionalProperties"] = True
        return source_schema

    def __init__(
        self,
        signal_duration: float = 7.0,
        ttl_times: list[list[float]] | None = None,
        ttl_duration: float = 1.0,
    ):
        """
        Define a mock SpikeGLXNIDQInterface by overriding the recording extractor to be a mock TTL signal.

        Parameters
        ----------
        signal_duration : float, default: 7.0
            The number of seconds to simulate.
        ttl_times : list of lists of floats, optional
            The times within the `signal_duration` to trigger the TTL pulse for each channel.
            The outer list is over channels, while each inner list is the set of TTL times for each specific channel.
            The default generates 8 channels with periodic on/off cycle (which start in the 'off' state)
            each of which is of length `ttl_duration` with a 0.1 second offset per channel.
        ttl_duration : float, default: 1.0
            How long the TTL pulses stays in the 'on' state when triggered, in seconds.
        """
        from spikeinterface.extractors import NumpyRecording

        self.has_analog_channels = True
        self.has_digital_channels = False

        if ttl_times is None:
            # Begin in 'off' state
            number_of_periods = int(np.ceil((signal_duration - ttl_duration) / (ttl_duration * 2)))
            default_periodic_ttl_times = [ttl_duration * (1 + 2 * period) for period in range(number_of_periods)]
            ttl_times = [[ttl_time + 0.1 * channel for ttl_time in default_periodic_ttl_times] for channel in range(8)]
        number_of_channels = len(ttl_times)
        channel_ids = [f"nidq#XA{channel_index}" for channel_index in range(number_of_channels)]  # NIDQ channel IDs
        channel_groups = ["NIDQChannelGroup"] * number_of_channels
        self.analog_channel_ids = channel_ids

        sampling_frequency = 25_000.0  # NIDQ sampling rate
        number_of_frames = int(signal_duration * sampling_frequency)
        traces = np.empty(shape=(number_of_frames, number_of_channels), dtype="int16")
        for channel_index in range(number_of_channels):
            traces[:, channel_index] = generate_mock_ttl_signal(
                signal_duration=signal_duration,
                ttl_times=ttl_times[channel_index],
                ttl_duration=ttl_duration,
                sampling_frequency_hz=sampling_frequency,
            )

        self.recording_extractor = NumpyRecording(
            traces_list=traces,
            sampling_frequency=sampling_frequency,
            channel_ids=channel_ids,
        )
        # NIDQ channel gains
        self.recording_extractor.set_channel_gains(gains=[61.03515625] * self.recording_extractor.get_num_channels())
        self.recording_extractor.set_property(key="group_name", values=channel_groups)

        # Minimal meta so `get_metadata` works similarly to real NIDQ header
        self.meta = {
            "acqMnMaXaDw": "0,0,8,1",
            "fileCreateTime": "2020-11-03T10:35:10",
            "niDev1ProductName": "PCI-6259",
        }
        self.verbose = None
        self.metadata_key = "spikeglx_nidq"
        self._analog_channel_groups = {
            "nidq_analog": {
                "channels": list(channel_ids),
            }
        }
        self._digital_channel_groups = {}


class MockRecordingInterface(BaseRecordingExtractorInterface):
    """An interface with a spikeinterface recording object for testing purposes."""

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.core.generate import generate_recording

        return generate_recording

    def _initialize_extractor(self, interface_kwargs: dict):
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("es_key", None)
        self.extractor_kwargs.pop("metadata_key", None)
        self.extractor_kwargs.pop("calibration", None)

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    def __init__(
        self,
        *args,
        num_channels: int = 4,
        sampling_frequency: float = 30_000.0,
        durations: tuple[float, ...] = (1.0,),
        seed: int = 0,
        verbose: bool = False,
        es_key: str | None = None,
        metadata_key: str | None = None,
        set_probe: bool = False,
        calibration: Literal["unknown", "uniform", "heterogeneous_gains", "heterogeneous_offsets"] = "uniform",
    ):
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "num_channels",
                "sampling_frequency",
                "durations",
                "seed",
                "verbose",
                "es_key",
                "set_probe",
            ]
            # Number of positional parameters before *args in the signature (self is counted by Python in error messages)
            num_positional_args_before_args = 1  # self
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"MockRecordingInterface.__init__() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments "
                    f"but {len(args) + num_positional_args_before_args} were given. "
                    "Note: Positional arguments are deprecated and will be removed in June 2026 or after. Please use keyword arguments."
                )
            # Map positional args to keyword args, positional args take precedence
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to MockRecordingInterface.__init__() is deprecated "
                f"and will be removed in June 2026 or after. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            num_channels = positional_values.get("num_channels", num_channels)
            sampling_frequency = positional_values.get("sampling_frequency", sampling_frequency)
            durations = positional_values.get("durations", durations)
            seed = positional_values.get("seed", seed)
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)
            set_probe = positional_values.get("set_probe", set_probe)

        super().__init__(
            num_channels=num_channels,
            sampling_frequency=sampling_frequency,
            durations=durations,
            set_probe=set_probe,
            seed=seed,
            verbose=verbose,
            es_key=es_key,
            metadata_key=metadata_key,
        )

        number_of_channels = self.recording_extractor.get_num_channels()
        if calibration == "uniform":
            gains = np.ones(number_of_channels)
            offsets = np.zeros(number_of_channels)
        elif calibration == "heterogeneous_gains":
            gains = np.arange(1, number_of_channels + 1)
            offsets = np.zeros(number_of_channels)
        elif calibration == "heterogeneous_offsets":
            gains = np.ones(number_of_channels)
            offsets = np.arange(number_of_channels)
        elif calibration == "unknown":
            gains = offsets = None
        else:
            raise ValueError(
                "calibration must be one of 'unknown', 'uniform', 'heterogeneous_gains', or " "'heterogeneous_offsets'."
            )

        if gains is not None:
            self.recording_extractor.set_channel_gains(gains=gains)
            self.recording_extractor.set_channel_offsets(offsets=offsets)
            self.recording_extractor.set_property("physical_unit", values=["uV"] * number_of_channels)
            self.recording_extractor.set_property("gain_to_physical_unit", values=gains)
            self.recording_extractor.set_property("offset_to_physical_unit", values=offsets)

        # If probe was set, customize contact IDs to use "e0", "e1", etc. format for testing
        if set_probe and self.recording_extractor.has_probe():
            probe = self.recording_extractor.get_probe()
            contact_ids = [f"e{i}" for i in range(num_channels)]
            probe.set_contact_ids(contact_ids)
            # TODO: drop `in_place=True` once spikeinterface>=0.105.0 is the minimum pin, where the call
            # is always in place, returns None and the argument is deprecated. It is required on 0.104,
            # which otherwise returns a new recording and leaves this one unchanged.
            self.recording_extractor.set_probe(probe, group_mode="by_probe", in_place=True)

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        """
        Get metadata for the recording interface.

        Returns
        -------
        dict
            The metadata dictionary containing NWBFile metadata with session start time.
        """
        metadata = super().get_metadata(use_new_metadata_format=use_new_metadata_format)
        session_start_time = datetime.now().astimezone()
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata


class MockSortingInterface(BaseSortingExtractorInterface):
    """A mock sorting extractor interface for generating synthetic sorting data."""

    # TODO: Implement this class with the lazy generator once is merged
    # https://github.com/SpikeInterface/spikeinterface/pull/2227

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.core.generate import generate_sorting

        return generate_sorting

    def _initialize_extractor(self, interface_kwargs: dict):
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    def __init__(
        self,
        num_units: int = 4,
        sampling_frequency: float = 30_000.0,
        durations: tuple[float, ...] = (1.0,),
        seed: int = 0,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        num_units : int, optional
            Number of units to generate, by default 4.
        sampling_frequency : float, optional
            Sampling frequency of the generated data in Hz, by default 30,000.0 Hz.
        durations : tuple of float, optional
            Durations of the segments in seconds, by default (1.0,).
        seed : int, optional
            Seed for the random number generator, by default 0.
        verbose : bool, optional
            Control whether to display verbose messages during writing, by default True.

        """

        super().__init__(
            num_units=num_units,
            sampling_frequency=sampling_frequency,
            durations=durations,
            seed=seed,
            verbose=verbose,
        )

        # Sorting extractor to have string unit ids until is changed in SpikeInterface
        # https://github.com/SpikeInterface/spikeinterface/pull/3588
        string_unit_ids = [str(id) for id in self.sorting_extractor.unit_ids]
        self.sorting_extractor = self.sorting_extractor.rename_units(new_unit_ids=string_unit_ids)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        session_start_time = datetime.now().astimezone()
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata


class MockImagingInterface(BaseImagingExtractorInterface):
    """
    A mock imaging interface for testing purposes.
    """

    @classmethod
    def get_extractor_class(cls):
        from roiextractors.testing import generate_dummy_imaging_extractor

        return generate_dummy_imaging_extractor

    def _initialize_extractor(self, interface_kwargs: dict):
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("photon_series_type", None)
        self.extractor_kwargs.pop("metadata_key", None)

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    def __init__(
        self,
        num_samples: int = 30,
        num_rows: int = 10,
        num_columns: int = 10,
        sampling_frequency: float = 30,
        dtype: str = "uint16",
        verbose: bool = False,
        seed: int = 0,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
        metadata_key: str | None = None,
    ):
        """
        Parameters
        ----------
        num_samples : int, optional
            The number of samples (frames) in the mock imaging data, by default 30.
        num_rows : int, optional
            The number of rows (height) in each frame of the mock imaging data, by default 10.
        num_columns : int, optional
            The number of columns (width) in each frame of the mock imaging data, by default 10.
        sampling_frequency : float, optional
            The sampling frequency of the mock imaging data in Hz, by default 30.
        dtype : str, optional
            The data type of the generated imaging data (e.g., 'uint16'), by default 'uint16'.
        seed : int, optional
            Random seed for reproducibility, by default 0.
        photon_series_type : Literal["OnePhotonSeries", "TwoPhotonSeries"], optional
            The type of photon series for the mock imaging data, either "OnePhotonSeries" or
            "TwoPhotonSeries", by default "TwoPhotonSeries".
        verbose : bool, default False
            controls verbosity
        """

        self.seed = seed
        if metadata_key is None:
            metadata_key = "mock_imaging"

        super().__init__(
            num_samples=num_samples,
            num_rows=num_rows,
            num_columns=num_columns,
            sampling_frequency=sampling_frequency,
            dtype=dtype,
            verbose=verbose,
            seed=seed,
            metadata_key=metadata_key,
        )

        self.verbose = verbose
        self.photon_series_type = photon_series_type

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        session_start_time = datetime.now().astimezone()
        metadata = super().get_metadata(use_new_metadata_format=use_new_metadata_format)
        metadata["NWBFile"]["session_start_time"] = session_start_time
        if use_new_metadata_format:
            # Add to the entry the base already named rather than replacing the block.
            metadata["Ophys"]["MicroscopySeries"][self.metadata_key].update(
                description="Imaging data from mock generator."
            )
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *args,
        photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "TwoPhotonSeries",
        photon_series_index: int = 0,
        parent_container: Literal["acquisition", "processing/ophys"] = "acquisition",
        stub_test: bool = False,
        always_write_timestamps: bool = False,
        iterator_type: str | None = "v2",
        iterator_options: dict | None = None,
    ):
        """
        Add imaging data to the NWB file.

        This method demonstrates the *args pattern for deprecating positional arguments
        while maintaining schema validation for keyword-only arguments.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file where the imaging data will be added.
        metadata : dict, optional
            Metadata for the NWBFile, by default None.
        photon_series_type : {"TwoPhotonSeries", "OnePhotonSeries"}, optional
            The type of photon series to be added, by default "TwoPhotonSeries".
        photon_series_index : int, optional
            The index of the photon series in the provided imaging data, by default 0.
        parent_container : {"acquisition", "processing/ophys"}, optional
            Specifies the parent container to which the photon series should be added.
        stub_test : bool, optional
            If True, only writes a small subset of frames for testing purposes, by default False.
        always_write_timestamps : bool, optional
            Whether to always write timestamps, by default False.
        iterator_type : {"v2", None}, default: "v2"
            The type of iterator for chunked data writing.
        iterator_options : dict, optional
            Options for controlling the iterative write process.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "photon_series_type",
                "photon_series_index",
                "parent_container",
                "stub_test",
                "always_write_timestamps",
                "iterator_type",
                "iterator_options",
            ]
            num_positional_args_before_args = 2  # nwbfile, metadata
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"add_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                    f"{len(args) + num_positional_args_before_args} were given. "
                    "Note: Positional arguments are deprecated and will be removed in June 2026 or after. Please use keyword arguments."
                )
            # Map positional args to keyword args, positional args take precedence
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to add_to_nwbfile is deprecated "
                f"and will be removed in June 2026 or after. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            photon_series_type = positional_values.get("photon_series_type", photon_series_type)
            photon_series_index = positional_values.get("photon_series_index", photon_series_index)
            parent_container = positional_values.get("parent_container", parent_container)
            stub_test = positional_values.get("stub_test", stub_test)
            always_write_timestamps = positional_values.get("always_write_timestamps", always_write_timestamps)
            iterator_type = positional_values.get("iterator_type", iterator_type)
            iterator_options = positional_values.get("iterator_options", iterator_options)

        # Call parent implementation with keyword arguments
        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            photon_series_index=photon_series_index,
            parent_container=parent_container,
            stub_test=stub_test,
            always_write_timestamps=always_write_timestamps,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
        )


class MockSegmentationInterface(BaseSegmentationExtractorInterface):
    """A mock segmentation interface for testing purposes."""

    @classmethod
    def get_extractor_class(cls):
        from roiextractors.testing import generate_dummy_segmentation_extractor

        return generate_dummy_segmentation_extractor

    def _initialize_extractor(self, interface_kwargs: dict):
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    def __init__(
        self,
        num_rois: int = 10,
        num_samples: int = 30,
        num_rows: int = 25,
        num_columns: int = 25,
        sampling_frequency: float = 30.0,
        has_summary_images: bool = True,
        has_raw_signal: bool = True,
        has_dff_signal: bool = True,
        has_deconvolved_signal: bool = True,
        has_neuropil_signal: bool = True,
        seed: int = 0,
        verbose: bool = False,
        metadata_key: str | None = None,
    ):
        """
        Parameters
        ----------
        num_rois : int, optional
            number of regions of interest, by default 10.
        num_samples : int, optional
            number of samples (frames), by default 30.
        num_rows : int, optional
            number of rows in the hypothetical video from which the data was extracted, by default 25.
        num_columns : int, optional
            number of columns in the hypothetical video from which the data was extracted, by default 25.
        sampling_frequency : float, optional
            sampling frequency of the hypothetical video from which the data was extracted, by default 30.0.
        has_summary_images : bool, optional
            whether the dummy segmentation extractor has summary images or not (mean and correlation).
        has_raw_signal : bool, optional
            whether a raw fluorescence signal is desired in the object, by default True.
        has_dff_signal : bool, optional
            whether a relative (df/f) fluorescence signal is desired in the object, by default True.
        has_deconvolved_signal : bool, optional
            whether a deconvolved signal is desired in the object, by default True.
        has_neuropil_signal : bool, optional
            whether a neuropil signal is desired in the object, by default True.
        seed: int, default 0
            seed for the random number generator, by default 0
        verbose : bool, optional
            controls verbosity, by default False.
        metadata_key : str, optional
            Metadata key for this interface. When None, defaults to "mock_segmentation".
        """
        if metadata_key is None:
            metadata_key = "mock_segmentation"

        super().__init__(
            num_rois=num_rois,
            num_samples=num_samples,
            num_rows=num_rows,
            num_columns=num_columns,
            sampling_frequency=sampling_frequency,
            has_summary_images=has_summary_images,
            has_raw_signal=has_raw_signal,
            has_dff_signal=has_dff_signal,
            has_deconvolved_signal=has_deconvolved_signal,
            has_neuropil_signal=has_neuropil_signal,
            verbose=verbose,
            seed=seed,
            metadata_key=metadata_key,
        )

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        session_start_time = datetime.now().astimezone()

        if use_new_metadata_format:
            metadata = super().get_metadata(use_new_metadata_format=True)
            metadata["NWBFile"]["session_start_time"] = session_start_time
            metadata["Ophys"] = {
                "PlaneSegmentations": {
                    self.metadata_key: {
                        "name": "PlaneSegmentation",
                        "description": "Segmentation data from mock generator.",
                    },
                },
            }
            return metadata

        metadata = super().get_metadata(use_new_metadata_format=False)
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata


class MockPoseEstimationInterface(BasePoseEstimationInterface):
    """
    A mock pose estimation interface for testing purposes.
    """

    display_name = "Mock Pose Estimation"
    keywords = (
        "behavior",
        "pose estimation",
        "mock",
    )
    associated_suffixes = []
    info = "Mock interface for pose estimation data testing."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["timestamps", "confidence"])
        source_schema["additionalProperties"] = True
        return source_schema

    def __init__(
        self,
        num_samples: int = 1000,
        num_nodes: int = 3,
        seed: int = 0,
        verbose: bool = False,
        metadata_key: str = "MockPoseEstimation",
        pose_estimation_metadata_key: str | None = None,
    ):
        """
        Initialize a mock pose estimation interface.

        Parameters
        ----------
        num_samples : int, optional
            Number of samples to generate, by default 1000.
        num_nodes : int, optional
            Number of nodes/body parts to track, by default 3.
        seed : int, optional
            Random seed for reproducible data generation, by default 0.
        verbose : bool, optional
            Control verbosity, by default False.
        metadata_key : str, default: "MockPoseEstimation"
            Metadata key for this interface.
        pose_estimation_metadata_key : str, optional
            Deprecated. Renamed to ``metadata_key``; passing it forwards the value to
            ``metadata_key`` and will be removed on or after February 2027.
        """
        if pose_estimation_metadata_key is not None:
            warnings.warn(
                "The 'pose_estimation_metadata_key' argument has been renamed to 'metadata_key' and "
                "will be removed on or after February 2027. Please use 'metadata_key' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            metadata_key = pose_estimation_metadata_key

        self.num_samples = num_samples
        self.num_nodes = num_nodes
        self.metadata_key = metadata_key
        self.seed = seed
        self.verbose = verbose

        # Set metadata defaults
        self.scorer = "MockScorer"
        self.source_software = "MockSourceSoftware"

        # Generate random nodes and edges
        orbital_body_parts = [
            "head",
            "neck",
            "left_shoulder",
            "right_shoulder",
            "chest",
            "left_elbow",
            "right_elbow",
            "left_wrist",
            "right_wrist",
            "pelvis",
        ]

        # Use orbital body parts if we have enough, otherwise generate generic nodes
        if num_nodes <= len(orbital_body_parts):
            self.nodes = orbital_body_parts[:num_nodes]
        else:
            self.nodes = orbital_body_parts + [f"node_{i}" for i in range(len(orbital_body_parts), num_nodes)]

        # Generate random edges (connect some nodes randomly)
        np.random.seed(seed)  # For reproducible edge generation
        num_edges = min(num_nodes - 1, max(1, num_nodes // 2))  # Reasonable number of edges
        possible_edges = [(i, j) for i in range(num_nodes) for j in range(i + 1, num_nodes)]
        selected_edges = np.random.choice(len(possible_edges), size=num_edges, replace=False)
        self.edges = np.array([possible_edges[i] for i in selected_edges], dtype="uint8")

        # Generate timestamps (private attributes)
        self._original_timestamps = np.linspace(0.0, float(num_samples) / 30.0, num_samples)
        self._timestamps = np.copy(self._original_timestamps)

        # Generate pose estimation data
        self.pose_data = self._generate_pose_data()

        super().__init__(verbose=verbose)

        # Import ndx_pose to ensure it's available
        import ndx_pose  # noqa: F401

    def _generate_pose_data(self) -> np.ndarray:
        """Generate pose estimation data with center following Lissajous trajectory and nodes fixed on circle."""
        # Fixed to 2D for now
        shape = (self.num_samples, self.num_nodes, 2)

        # Generate Lissajous trajectory for the center
        time_points = np.linspace(0, 4 * np.pi, self.num_samples)
        center_x = 320 + 80 * np.sin(1.2 * time_points)  # Center follows Lissajous
        center_y = 240 + 60 * np.sin(1.7 * time_points + np.pi / 3)

        # Generate data for all nodes
        data = np.zeros(shape)
        circle_radius = 50  # Radius of circle around center

        for node_index in range(self.num_nodes):
            # Position each node equally spaced around a circle relative to center
            angle = 2 * np.pi * node_index / self.num_nodes

            # Fixed position on circle relative to center (no oscillations)
            offset_x = circle_radius * np.cos(angle)
            offset_y = circle_radius * np.sin(angle)

            # Final position: center + fixed circle position
            data[:, node_index, 0] = center_x + offset_x
            data[:, node_index, 1] = center_y + offset_y

        return data

    def get_original_timestamps(self) -> np.ndarray:
        """Get the original timestamps before any alignment."""
        return self._original_timestamps

    def get_timestamps(self) -> np.ndarray:
        """Get the current (possibly aligned) timestamps."""
        return self._timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        """Set aligned timestamps."""
        self._timestamps = aligned_timestamps

    def get_metadata(self) -> DeepDict:
        """Name the objects after this interface's key and add what the mock pretends its source records."""
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        container_name = self.metadata_key
        metadata["Pose"]["Skeletons"][self.metadata_key].update(
            name=f"Skeleton{container_name}",
            edges=self.edges.tolist(),
        )
        metadata["Pose"]["PoseEstimations"][self.metadata_key].update(
            name=container_name,
            description=f"Mock pose estimation data from {self.source_software}.",
            source_software=self.source_software,
            scorer=self.scorer,
            PoseEstimationSeries={
                node: {"name": f"PoseEstimationSeries{self._pascal_case(node)}"} for node in self.nodes
            },
        )
        return metadata

    @staticmethod
    def _pascal_case(node_name: str) -> str:
        return "".join(word.capitalize() for word in node_name.replace("_", " ").split())

    def _get_keypoint_names(self) -> list[str]:
        return self.nodes

    def _get_keypoint_data(self) -> dict[str, tuple[np.ndarray, np.ndarray | None]]:
        return {
            node_name: (self.pose_data[:, index, :], np.ones(self.num_samples))
            for index, node_name in enumerate(self.nodes)
        }


class MockExternalVideoInterface(ExternalVideoInterface):
    """
    A mock external video interface for testing purposes.

    Overrides exactly one thing: what the container header says. The frame count and the frame rate are
    constructor arguments rather than reads, so a test can compose a video of any length into a conversion
    at no cost, and everything else runs the real interface's course. In particular the timing is left
    unset, as it is on a freshly constructed real interface, so a single file writes a starting time and a
    rate while several files raise until the test says where they sit.

    Nothing that reads the video itself is stubbed, only the header, so a method that decodes frames
    (``get_original_timestamps``, and ``set_aligned_segment_starting_times`` which goes through it) will
    fail here as it would on any missing file. Give the times directly with ``set_aligned_timestamps``.

    The paths land in ``external_file`` as they were passed and deliberately do not resolve, which is what
    keeps the file a mock produces from being mistaken for a publishable one; ``nwbinspector`` flags the
    dangling path, and that is the intent.
    """

    display_name = "Mock Video"
    keywords = ("video", "behavior", "mock")
    associated_suffixes = ()
    info = "Mock interface for external video data testing."

    def __init__(
        self,
        file_paths: list[str] | None = None,
        num_frames: int = 100,
        frame_rate: float = 30.0,
        verbose: bool = False,
        *,
        metadata_key: str | None = None,
    ):
        """
        Initialize a mock external video interface.

        Parameters
        ----------
        file_paths : list of str, optional
            The paths written to ``external_file``; they do not have to exist. Defaults to a single
            ``"mock_video.mp4"``.
        num_frames : int, default: 100
            The frame count each file's header reports, which backs ``num_samples`` and ``starting_frame``.
        frame_rate : float, default: 30.0
            The frame rate each file's header reports.
        verbose : bool, default: False
            If True, display verbose output.
        metadata_key : str, optional
            Snake_case key identifying this video's entry under ``metadata["Behavior"]["ExternalVideos"]``.
            Defaults to the stem-based key of the parent interface.
        """
        file_paths = [Path(file_path) for file_path in file_paths or ["mock_video.mp4"]]
        # ExternalVideoInterface.__init__ is wrapped by pydantic's validate_call, whose FilePath refuses a
        # path that does not exist; the undecorated function kept at __wrapped__ is what lets this interface
        # stand up with nothing behind its paths.
        ExternalVideoInterface.__init__.__wrapped__(
            self,
            file_paths=file_paths,
            verbose=verbose,
            metadata_key=metadata_key,
        )
        self.num_frames = num_frames
        self.frame_rate = frame_rate

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        return metadata

    def _get_header_frame_counts(self) -> list[int]:
        """Return the frame count the mock was built with, so the write path opens no files."""
        return [self.num_frames] * self._number_of_files

    def _get_header_frame_rates(self) -> list[float]:
        """Return the frame rate the mock was built with, so the write path opens no files."""
        return [self.frame_rate] * self._number_of_files


class MockIcephysInterface(BaseDataInterface):
    """
    A mock intracellular electrophysiology interface for testing purposes.

    Writes one electrode's synthetic response as a single continuous response series (the class chosen by the
    clamp ``mode``, as a real interface does) plus one
    intracellular-recordings row per sweep, each addressing the sweep's ``(start_index, count)`` sample range.
    That is the contract every icephys interface emits, so this exercises the format-independent machinery in
    :mod:`neuroconv.tools.icephys` (which reads those rows back to build the hierarchy tables and the sweep
    intervals) without any acquisition file. Combine several instances in a ``ConverterPipe`` for the
    multi-channel and multi-run cases: instances sharing a ``starting_time`` describe the same sweeps recorded
    on two electrodes (a dual patch), distinct ones place two runs on a single timeline.
    """

    def __init__(
        self,
        *,
        mode: Literal["voltage_clamp", "current_clamp", "izero"] = "current_clamp",
        num_sweeps: int = 3,
        sweep_duration: float = 1.0,
        sampling_frequency: float = 10_000.0,
        inter_sweep_interval: float = 0.0,
        starting_time: float = 0.0,
        sequence: str = "run",
        stimulus_type: str | None = "mock protocol",
        repetition: str | None = None,
        condition: str | None = None,
        metadata_key: str = "mock",
        seed: int = 0,
        verbose: bool = False,
    ):
        """
        Initialize a mock intracellular electrophysiology interface.

        Parameters
        ----------
        mode : {"current_clamp", "voltage_clamp", "izero"}, default: "current_clamp"
            The clamp mode, which selects the response series class the same way a real interface does.
        num_sweeps : int, default: 3
            Number of sweeps, one intracellular-recordings row each.
        sweep_duration : float, default: 1.0
            Duration of every sweep, in seconds.
        sampling_frequency : float, default: 10000.0
            Sampling rate of the response series, in Hz.
        inter_sweep_interval : float, default: 0.0
            Dead time between the end of a sweep and the start of the next one, in seconds. The default of 0.0
            leaves the samples regular, so the series is written with a uniform rate; a non-zero value makes
            them irregular, so it is written with explicit timestamps instead (the rule a real interface uses).
        starting_time : float, default: 0.0
            Time of the first sample, in seconds.
        sequence : str, default: "run"
            Run identity written to the ``sequence`` column of every row, the label that groups the rows into
            one sequential recording.
        stimulus_type : str, optional, default: "mock protocol"
            Value of the ``stimulus_type`` column, carried up to the sequential recording when aggregated. Pass
            ``None`` to omit the column, as an interface whose format describes no stimulus does.
        repetition : str, optional
            Label grouping this run's sequential recording with others into a ``Repetitions`` entry. Written as a
            column only when given, as a real interface does.
        condition : str, optional
            Label grouping this run's repetition with others into an ``ExperimentalConditions`` entry. Written as
            a column only when given.
        metadata_key : str, default: "mock"
            Identity of this interface's electrode and response series in the metadata dict. Give combined
            instances distinct keys so each writes its own electrode and series.
        seed : int, default: 0
            Seed for the random number generator.
        verbose : bool, default: False
            Control verbosity.
        """
        super().__init__(verbose=verbose)
        self.mode = mode
        self.num_sweeps = num_sweeps
        self.sweep_duration = sweep_duration
        self.sampling_frequency = sampling_frequency
        self.inter_sweep_interval = inter_sweep_interval
        self.starting_time = starting_time
        self.sequence = sequence
        self.stimulus_type = stimulus_type
        self.repetition = repetition
        self.condition = condition
        self.metadata_key = metadata_key
        self.seed = seed

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the intracellular electrophysiology interface.

        Returns
        -------
        DeepDict
            The metadata dictionary, with the device, electrode and response series entries keyed by
            ``metadata_key`` and cross-linked the way a real icephys interface links them.
        """
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        name_suffix = to_camel_case(self.metadata_key)
        # The device identifies the amplifier, which runs share, so every instance meets at one registry entry
        # (a single key with a single name), the way several real interfaces recorded on one amplifier do.
        device_metadata_key = "mock_amplifier"
        metadata["Devices"] = {
            device_metadata_key: {
                "name": "MockAmplifier",
                "description": "Mock patch-clamp amplifier.",
            }
        }
        metadata["Icephys"]["IntracellularElectrodes"] = {
            self.metadata_key: {
                "name": f"IntracellularElectrode{name_suffix}",
                "description": "Mock patch-clamp electrode.",
                "device_metadata_key": device_metadata_key,
            }
        }
        # The default name is the NWB neurodata type for the clamp mode plus the electrode suffix, the same
        # rule a real interface follows (add_to_nwbfile instantiates the matching class via _RESPONSE_CLASS).
        response_type_name = {
            "voltage_clamp": "VoltageClampSeries",
            "current_clamp": "CurrentClampSeries",
            "izero": "IZeroClampSeries",
        }[self.mode]
        metadata["Icephys"]["PatchClampSeries"] = {
            self.metadata_key: {
                "name": f"{response_type_name}{name_suffix}",
                "description": f"Mock intracellular response ({self.mode}).",
                "electrode_metadata_key": self.metadata_key,
            }
        }
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
    ):
        """
        Add the mock response series and its per-sweep intracellular-recordings rows to an NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file the series and rows are added to.
        metadata : dict, optional
            Metadata dictionary. If None, uses default metadata.
        """
        if metadata is None:
            metadata = self.get_metadata()

        response_metadata = metadata["Icephys"]["PatchClampSeries"][self.metadata_key]
        electrode = _add_intracellular_electrode_to_nwbfile(
            nwbfile, metadata, response_metadata["electrode_metadata_key"]
        )

        samples_per_sweep = round(self.sweep_duration * self.sampling_frequency)
        rng = np.random.default_rng(self.seed)
        total_samples = self.num_sweeps * samples_per_sweep
        data = rng.standard_normal(total_samples).astype("float32")

        # The sweeps are laid end to end in one continuous series, each starting an inter-sweep interval after
        # the previous one ended; the ranges are the (start_index, count) pairs the recordings rows address.
        sweep_sample_ranges = [
            (sweep_index * samples_per_sweep, samples_per_sweep) for sweep_index in range(self.num_sweeps)
        ]
        timestamps = np.empty(total_samples, dtype="float64")
        for sweep_index, (start_index, count) in enumerate(sweep_sample_ranges):
            sweep_start_time = self.starting_time + sweep_index * (self.sweep_duration + self.inter_sweep_interval)
            timestamps[start_index : start_index + count] = (
                sweep_start_time + np.arange(count) / self.sampling_frequency
            )

        series_kwargs = dict(
            name=response_metadata["name"],
            description=response_metadata["description"],
            data=data,
            electrode=electrode,
            gain=np.nan,
        )
        # Same timing rule as a real interface: a uniform rate while the samples stay regular, explicit
        # timestamps once the inter-sweep gaps make them irregular.
        rate = calculate_regular_series_rate(series=timestamps)
        if rate is not None:
            series_kwargs.update(starting_time=float(timestamps[0]), rate=rate)
        else:
            series_kwargs.update(timestamps=timestamps)
        response_series = _RESPONSE_CLASS[self.mode](**series_kwargs)
        nwbfile.add_acquisition(response_series)

        # The run-level columns, denormalized onto every row exactly as a real interface writes them: the
        # always-present run identity, plus the optional ones only when the caller asked for them.
        columns = {"sequence": self.sequence}
        if self.stimulus_type is not None:
            columns["stimulus_type"] = self.stimulus_type
        if self.repetition is not None:
            columns["repetition"] = self.repetition
        if self.condition is not None:
            columns["condition"] = self.condition
        column_descriptions = {
            "sequence": "Run identity grouping rows into a sequential recording.",
            "stimulus_type": "Stimulus type of the run, carried up to its sequential recording when aggregated.",
            "repetition": "Repetition label grouping sequential recordings into a repetition.",
            "condition": "Experimental condition label grouping repetitions.",
        }
        table = nwbfile.get_intracellular_recordings()
        for column_name in columns:
            if column_name not in table.colnames:
                table.add_column(name=column_name, description=column_descriptions[column_name])

        for start_index, count in sweep_sample_ranges:
            nwbfile.add_intracellular_recording(
                electrode=electrode,
                response=response_series,
                response_start_index=start_index,
                response_index_count=count,
                **columns,
            )
