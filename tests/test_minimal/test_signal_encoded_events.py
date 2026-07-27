"""Data-free tests of the shared signal-encoded events pattern, driven by ``MockSignalEncodedEventsInterface``.

Where ``test_base_events_interface.py`` covers the writer (``_EventsData`` into tables, driven by the
pre-extracted ``MockEventsInterface``), these cover the step before it: turning a sampled signal into
``_EventsData``. The mock generates a synthetic packed word from a waveform description, so everything
from the ``detection_configuration`` grammar through conditioning, detection and the frame-to-seconds
adapter is the shipped code path, exercised on shapes no real fixture in the suite has (a packed word,
an idle line, an unclosed pulse, an irregular clock).

The low-level edge and duration maths lives in ``test_tools/test_signal_processing.py``; these tests
confirm each path is reachable through a real interface and survives to the written table.
"""

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.events import _get_event_type_source_ids
from neuroconv.tools.testing import MockSignalEncodedEventsInterface


def event_type_ids(interface):
    """The identifiers a configuration resolves to, which is what the writer keys tables on.

    Derived from the configuration rather than read off ``_detection_plan``, since the plan is
    grouped by signal (one read per signal) and so its keys are signal handles, not event types.
    """
    return _get_event_type_source_ids(interface._detection_configuration)


class TestDefaults:
    """``detection_configuration=None`` carves every recorded bit, losslessly."""

    def test_every_recorded_bit_becomes_its_own_event_type(self):
        interface = MockSignalEncodedEventsInterface(digital_line_waveforms={0: "pulses", 1: "pulses"})

        assert event_type_ids(interface) == ["word_bit0_high_period", "word_bit1_high_period"]

    def test_the_bit_inventory_need_not_be_contiguous(self):
        """The keys are what the format recorded, so a gap in them is normal and must round-trip."""
        interface = MockSignalEncodedEventsInterface(digital_line_waveforms={0: "pulses", 3: "pulses"})

        assert event_type_ids(interface) == ["word_bit0_high_period", "word_bit3_high_period"]

    def test_a_single_carved_bit_keeps_the_bare_signal_handle(self):
        """Rule 1: one spec on a signal means no fan-out, so no components are appended."""
        interface = MockSignalEncodedEventsInterface(digital_line_waveforms={0: "pulses"})

        assert event_type_ids(interface) == ["word"]

    def test_the_default_reading_is_durative(self):
        interface = MockSignalEncodedEventsInterface(digital_line_waveforms={0: "pulses"})

        assert interface._get_events_data_dict()["word"].durations is not None

    def test_a_named_line_pins_its_own_identifier(self):
        """Rule 3 reached through the default configuration, which is what the shipped default takes."""
        interface = MockSignalEncodedEventsInterface()

        assert event_type_ids(interface) == ["lick", "reward"]

    def test_naming_is_per_line_so_the_two_routes_can_be_mixed(self):
        """An unnamed line still derives, so a test wanting derived identifiers just omits the name."""
        interface = MockSignalEncodedEventsInterface(digital_line_waveforms={0: ("lick", "pulses"), 1: "pulses"})

        assert event_type_ids(interface) == ["lick", "word_bit1_high_period"]

    def test_the_default_configuration_is_validated_too(self):
        """A default is machine-built, but its inputs are not, so it can still collide."""
        with pytest.raises(ValueError, match="same identifier"):
            MockSignalEncodedEventsInterface(digital_line_waveforms={0: ("lick", "pulses"), 1: ("lick", "idle")})

    def test_a_fanned_out_signal_is_read_once(self):
        """The plan groups by signal, so a sixteen-bit word is one read and sixteen derivations.

        Invisible in the output, which is why it needs its own guard: reading per event type gives the
        same events, just N times the IO. This is the loop the Intan and NIDQ interfaces will copy.
        """
        interface = MockSignalEncodedEventsInterface(digital_line_waveforms={bit: "pulses" for bit in range(4)})
        reads = []
        unwrapped_get_signal = interface._get_signal

        def counting_get_signal(signal_source_id):
            reads.append(signal_source_id)
            return unwrapped_get_signal(signal_source_id)

        interface._get_signal = counting_get_signal

        assert len(interface._get_events_data_dict()) == 4
        assert reads == ["word"]


class TestWaveformKinds:
    """Each kind exists to make one path reachable that no reading can produce from a plain pulse train."""

    def test_pulses_give_one_event_per_pulse(self):
        interface = MockSignalEncodedEventsInterface(digital_line_waveforms={0: "pulses"}, num_events=6)

        assert interface._get_events_data_dict()["word"].timestamps.size == 6

    def test_an_idle_line_is_still_an_event_type_and_writes_a_zero_row_table(self):
        """Recorded and never fired: the type existed, nothing happened. Not the same as absent."""
        interface = MockSignalEncodedEventsInterface(digital_line_waveforms={0: "pulses", 1: "idle"})
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert interface._get_events_data_dict()["word_bit1_high_period"].timestamps.size == 0
        assert len(nwbfile.get_events_table("WordBit1HighPeriod")) == 0

    def test_an_unclosed_pulse_carries_a_nan_duration_through_to_the_table(self):
        """A truncated interval is a missing offset, and NaN has to survive the write."""
        interface = MockSignalEncodedEventsInterface(digital_line_waveforms={0: "unclosed_pulses"})
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        durations = nwbfile.get_events_table("Word")["duration"][:]
        assert np.isnan(durations[-1])
        assert not np.isnan(durations[:-1]).any()


class TestReadings:
    """One waveform read four ways, which is the variety ``detection`` supplies on its own."""

    def _plan_for(self, detection):
        return {"word": [{"signal_conditioning": {"bits": [0]}, "detection": detection}]}

    def test_rising_and_falling_are_point_events(self):
        for detection in ("rising", "falling"):
            interface = MockSignalEncodedEventsInterface(
                digital_line_waveforms={0: "pulses"}, detection_configuration=self._plan_for(detection)
            )
            assert interface._get_events_data_dict()["word"].durations is None

    def test_high_and_low_period_are_durative(self):
        for detection in ("high_period", "low_period"):
            interface = MockSignalEncodedEventsInterface(
                digital_line_waveforms={0: "pulses"}, detection_configuration=self._plan_for(detection)
            )
            assert interface._get_events_data_dict()["word"].durations is not None

    def test_value_change_is_the_only_reading_with_a_payload(self):
        """A banded trace read as value_change keeps the new band; every reading else resolves state away.

        Banded rather than a coded word: reading several bits together is deferred until its strobe
        guard exists, so `thresholds` is the only shipped route to a more-than-two-valued signal.
        """
        coded = MockSignalEncodedEventsInterface(
            analog_waveforms={"stim_level": "levels"},
            detection_configuration={
                "stim_level": [{"signal_conditioning": {"thresholds": [1.0, 2.0, 3.0]}, "detection": "value_change"}]
            },
        )
        plain = MockSignalEncodedEventsInterface(digital_line_waveforms={0: "pulses"})

        assert "value" in coded._get_events_data_dict()["stim_level"].payload
        assert plain._get_events_data_dict()["word"].payload == {}


class TestPayload:
    """A payload-carrying reading has to survive to a written column once its column is declared.

    A field the metadata never declares is silently dropped by the writer today; refusing that is a
    separate fix to the shared writer, tracked in the events ongoing-work notes.
    """

    def _coded_interface(self):
        """A banded analog trace: the shipped route to a payload, since a coded word is deferred."""
        return MockSignalEncodedEventsInterface(
            analog_waveforms={"stim_level": "levels"},
            detection_configuration={
                "stim_level": [{"signal_conditioning": {"thresholds": [1.0, 2.0, 3.0]}, "detection": "value_change"}]
            },
        )

    def test_a_declared_payload_field_reaches_the_written_table(self):
        """Declaring the column is the user's, not the interface's: get_metadata seeds only names."""
        interface = self._coded_interface()
        metadata = interface.get_metadata()
        entry = metadata["Events"]["mock_signal_encoded_events"]["event_types"]["stim_level"]
        assert "columns" not in entry  # nothing about the reading leaks into metadata
        entry["columns"] = {"value": {"column_name": "band"}}

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        table = nwbfile.get_events_table("StimLevel")
        np.testing.assert_array_equal(
            table["band"][:], interface._get_events_data_dict()["stim_level"].payload["value"]
        )


class TestTimebase:
    """Timestamps land in seconds, and durations come from the clock rather than from a frame count."""

    def test_timestamps_are_seconds_within_the_requested_duration(self):
        interface = MockSignalEncodedEventsInterface(
            digital_line_waveforms={0: "pulses"}, duration=2.0, sampling_frequency=500.0
        )

        onsets = interface._get_events_data_dict()["word"].timestamps
        assert onsets.min() >= 0.0
        assert onsets.max() < 2.0

    def test_an_irregular_clock_does_not_distort_durations(self):
        """The reason durations are not a frame count times an estimated sampling period."""
        regular = MockSignalEncodedEventsInterface(digital_line_waveforms={0: "pulses"}, sampling="regular")
        irregular = MockSignalEncodedEventsInterface(digital_line_waveforms={0: "pulses"}, sampling="irregular")

        regular_durations = regular._get_events_data_dict()["word"].durations
        irregular_durations = irregular._get_events_data_dict()["word"].durations

        # No pulse spans the stretched gap, so every pulse keeps its real width rather than picking up a
        # share of an averaged period. A median-based conversion would smear the gap across all of them.
        np.testing.assert_allclose(regular_durations, irregular_durations)

    def test_onsets_after_the_gap_follow_the_clock(self):
        interface = MockSignalEncodedEventsInterface(digital_line_waveforms={0: "pulses"}, sampling="irregular")

        onsets = interface._get_events_data_dict()["word"].timestamps
        assert onsets[-1] > 1.0  # the last pulse sits beyond the one-second gap


class TestMetadata:
    """Metadata is derived from the configuration, so it lists exactly what will be written."""

    def test_metadata_key_namespaces_the_event_types(self):
        interface = MockSignalEncodedEventsInterface(digital_line_waveforms={0: "pulses"}, metadata_key="my_events")

        assert set(interface.get_metadata()["Events"]["my_events"]["event_types"]) == {"word"}


class TestAnalogSignals:
    """The other half of the conditioning vocabulary: cuts on a continuous trace."""

    def test_thresholds_band_a_multi_level_trace(self):
        """No edge reading can read four levels, so the caller says where to cut and reads the bands."""
        interface = MockSignalEncodedEventsInterface(
            analog_waveforms={"photodiode": "levels"},
            detection_configuration={
                "photodiode": [{"signal_conditioning": {"thresholds": [1.0, 2.0, 3.0]}, "detection": "value_change"}]
            },
        )

        events = interface._get_events_data_dict()["photodiode"]
        np.testing.assert_array_equal(events.payload["value"], [1, 2, 3, 0])

    def test_binarize_reads_a_trace_that_is_a_line_only_conceptually(self):
        """A TTL through an analog input sits near two amplitudes with jitter on every sample."""
        interface = MockSignalEncodedEventsInterface(
            analog_waveforms={"ttl_on_analog": "noisy_two_level"},
            detection_configuration={
                "ttl_on_analog": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "high_period"}]
            },
        )

        events = interface._get_events_data_dict()["ttl_on_analog"]
        assert events.timestamps.size == 2
        np.testing.assert_allclose(events.durations, [0.2, 0.2])

    def test_an_analog_signal_is_absent_from_the_zero_configuration_default(self):
        """`thresholds` has no defensible default, and inventing one fabricates events."""
        interface = MockSignalEncodedEventsInterface(
            digital_line_waveforms={0: "pulses"}, analog_waveforms={"photodiode": "levels"}
        )

        assert event_type_ids(interface) == ["word"]

    def test_an_edge_reading_on_an_unconditioned_analog_trace_raises(self):
        """Rejected structurally at construction, before any sample is read."""
        with pytest.raises(ValueError, match="analog signal"):
            MockSignalEncodedEventsInterface(
                analog_waveforms={"photodiode": "levels"},
                detection_configuration={"photodiode": [{"detection": "rising"}]},
            )

    def test_bits_on_an_analog_signal_raises(self):
        with pytest.raises(ValueError, match="not a packed word"):
            MockSignalEncodedEventsInterface(
                analog_waveforms={"photodiode": "levels"},
                detection_configuration={"photodiode": [{"signal_conditioning": {"bits": [0]}, "detection": "rising"}]},
            )

    def test_an_unknown_analog_waveform_kind_raises(self):
        with pytest.raises(ValueError, match="Unknown analog waveform kind"):
            MockSignalEncodedEventsInterface(analog_waveforms={"photodiode": "sawtooth"})


class TestReadTimeBackstop:
    """The one check that cannot be made structurally, because it depends on the cut's width."""

    def test_a_multi_band_cut_read_as_an_edge_raises_at_read_time(self):
        """The analog twin: three cut points give four bands, which no edge reading can read."""
        interface = MockSignalEncodedEventsInterface(
            analog_waveforms={"photodiode": "levels"},
            detection_configuration={
                "photodiode": [{"signal_conditioning": {"thresholds": [1.0, 2.0, 3.0]}, "detection": "rising"}]
            },
        )

        with pytest.raises(ValueError, match="needs a two-valued signal"):
            interface._get_events_data_dict()


class TestConfigurationErrors:
    """The grammar's rules, reached through a real interface rather than against the validator directly."""

    def test_omitting_conditioning_on_a_word_raises(self):
        """A word is several signals until the caller says which bits form one value."""
        with pytest.raises(ValueError, match="packed word"):
            MockSignalEncodedEventsInterface(detection_configuration={"word": [{"detection": "rising"}]})

    def test_a_deferred_conditioning_key_raises_rather_than_being_ignored(self):
        """``hysteresis`` and ``debounce`` are designed but unbuilt; a knob that validates and does
        nothing is the silent-discard failure this validation exists to remove."""
        with pytest.raises(ValueError, match="unrecognized key"):
            MockSignalEncodedEventsInterface(
                detection_configuration={
                    "word": [{"signal_conditioning": {"bits": [0], "debounce": 0.01}, "detection": "rising"}]
                }
            )

    def test_reading_several_bits_together_is_deferred(self):
        """The coded-word reading needs a strobe guard to know when the word is settled, and has none.

        A word's bits do not all change on the same sample, so every transient combination it passes
        through would be written as a real event. Rejected structurally until the guard lands.
        """
        with pytest.raises(ValueError, match="several bits together"):
            MockSignalEncodedEventsInterface(
                digital_line_waveforms={0: "pulses", 1: "pulses"},
                detection_configuration={
                    "word": [
                        {"signal_conditioning": {"bits": [0, 1]}, "detection": "value_change"},
                        {"signal_conditioning": {"bits": [0]}, "detection": "rising"},
                    ]
                },
            )

    def test_an_unknown_waveform_kind_raises(self):
        with pytest.raises(ValueError, match="Unknown waveform kind"):
            MockSignalEncodedEventsInterface(digital_line_waveforms={0: "flat_high"})
