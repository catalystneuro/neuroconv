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

    def test_value_change_pools_both_edges_into_one_event_type(self):
        """The fifth reading: every transition is the same event type, in both directions.

        It carries no payload, so on a line it is rising and falling in one table rather than two.
        Telling transitions apart is a conditioning job, covered by the fan-out test below.
        """
        interface = MockSignalEncodedEventsInterface(
            digital_line_waveforms={0: "pulses"},
            num_events=3,
            detection_configuration={"word": [{"signal_conditioning": {"bits": [0]}, "detection": "value_change"}]},
        )

        events = interface._get_events_data_dict()["word"]
        assert events.timestamps.size == 6  # three pulses, both edges of each
        assert events.payload == {}
        assert events.durations is None  # a point reading: a transition has no extent


class TestCutsInsteadOfPayloads:
    """Distinguishing values is conditioning's job, not a value column's.

    One spec per distinction on the same signal, each named, each durative. This is what replaced the
    payload-carrying ``value_change``, and it is lossless: the band at any instant is how many cut
    points the signal has currently reached, so the per-cut tables carry the whole trajectory.
    """

    CUTS = [1.0, 2.0, 3.0]

    def _interface(self):
        return MockSignalEncodedEventsInterface(
            analog_waveforms={"stim_level": "levels"},
            detection_configuration={
                "stim_level": [
                    {
                        "signal_conditioning": {"binarize": cut},
                        "detection": "high_period",
                        "event_name": f"Above{index}",
                    }
                    for index, cut in enumerate(self.CUTS)
                ]
            },
        )

    def test_each_cut_is_its_own_named_durative_event_type(self):
        """What the value column could not give: real start and stop times per distinction."""
        events = self._interface()._get_events_data_dict()

        assert set(events) == {"Above0", "Above1", "Above2"}
        for event in events.values():
            assert event.durations is not None
            assert event.payload == {}

    def test_the_cuts_reconstruct_the_band_trajectory_exactly(self):
        """The lossless claim the design rests on, checked against the banding it replaced."""
        interface = self._interface()
        timestamps = interface._get_timestamps()
        trace = interface._get_signal("stim_level")
        bands = np.searchsorted(self.CUTS, trace, side="right")

        reconstructed = np.zeros(trace.size, dtype="int64")
        for event in interface._get_events_data_dict().values():
            for onset, duration in zip(event.timestamps, event.durations):
                stop = timestamps[-1] + 1 if np.isnan(duration) else onset + duration
                reconstructed[(timestamps >= onset) & (timestamps < stop)] += 1

        np.testing.assert_array_equal(reconstructed, bands)


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

    def test_a_single_cut_turns_an_analog_trace_into_a_readable_line(self):
        """A given cut exists to make a line out of a continuous trace, which edge readings then read."""
        interface = MockSignalEncodedEventsInterface(
            analog_waveforms={"photodiode": "levels"},
            detection_configuration={
                "photodiode": [{"signal_conditioning": {"binarize": 2.0}, "detection": "high_period"}]
            },
        )

        events = interface._get_events_data_dict()["photodiode"]
        assert events.timestamps.size == 1  # the trace rises through 2.0 once and stays up to the end
        assert events.durations is not None

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
        """A continuous trace has no defensible default cut, and inventing one fabricates events."""
        interface = MockSignalEncodedEventsInterface(
            digital_line_waveforms={0: "pulses"}, analog_waveforms={"photodiode": "levels"}
        )

        assert event_type_ids(interface) == ["word"]

    def test_a_spec_with_no_conditioning_raises(self):
        """Every spec states how its signal becomes a line; there is no pass-through spelling."""
        with pytest.raises(ValueError, match="does not set 'signal_conditioning'"):
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


class TestConfigurationErrors:
    """The grammar's rules, reached through a real interface rather than against the validator directly."""

    def test_a_spec_must_state_how_its_signal_becomes_a_line(self):
        """No conditioning at all, and an empty one, are the same mistake and get the same treatment."""
        with pytest.raises(ValueError, match="does not set 'signal_conditioning'"):
            MockSignalEncodedEventsInterface(detection_configuration={"word": [{"detection": "rising"}]})

        with pytest.raises(ValueError, match="exactly one"):
            MockSignalEncodedEventsInterface(
                digital_line_waveforms={0: "pulses", 1: "pulses"},
                detection_configuration={"word": [{"signal_conditioning": {}, "detection": "rising"}]},
            )

    def test_a_deferred_conditioning_key_raises_rather_than_being_ignored(self):
        """``hysteresis`` and ``debounce`` are designed but unbuilt; a knob that validates and does
        nothing is the silent-discard failure this validation exists to remove."""
        with pytest.raises(ValueError, match="unrecognized key"):
            MockSignalEncodedEventsInterface(
                detection_configuration={
                    "word": [{"signal_conditioning": {"bits": [0], "debounce": 0.01}, "detection": "rising"}]
                }
            )

    def test_cutting_a_word_at_a_magnitude_raises(self):
        """A word admits exactly one route, ``bits``, and both other cuts read its pattern as a number.

        The two live checks pair up: omitting conditioning on a word is rejected because a word is
        several signals, and cutting one is rejected for the same reason. Values 0, 1, 2, 3 on a
        two-line word are four combinations of two lines, so a threshold at 1.5 asks which of them are
        "large", which is not a question about the experiment.
        """
        for conditioning in ({"binarize": 1.5}, {"binarize": "midpoint"}):
            with pytest.raises(ValueError, match="cuts a packed word"):
                MockSignalEncodedEventsInterface(
                    digital_line_waveforms={0: "pulses", 1: "pulses"},
                    detection_configuration={"word": [{"signal_conditioning": conditioning, "detection": "rising"}]},
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


class TestBitsWithinTheDeclaredInventory:
    """A spec may only name a bit position the word actually carries.

    The check the word dialect needs and no other cut does. It is structural, taken from the format's
    declaration, because the data cannot answer it: a bit that was never acquired is zero at every
    sample, which is bit-for-bit what an acquired line that never fired looks like, and that second
    case must convert to a zero-row table rather than fail. So the two are separable only before the
    samples are read, and only by what the header declared.
    """

    def test_a_bit_the_word_does_not_carry_raises(self):
        with pytest.raises(ValueError, match="does not carry"):
            MockSignalEncodedEventsInterface(
                digital_line_waveforms={0: "pulses", 3: "pulses"},
                detection_configuration={"word": [{"signal_conditioning": {"bits": [7]}, "detection": "rising"}]},
            )

    def test_a_bit_inside_a_gap_in_the_inventory_raises(self):
        """The case a real fixture cannot state: every ``.nidq.meta`` anyone has declares ``0:7``.

        A contiguous inventory only ever exercises "past the end", so a check written against one
        would pass just as well if it compared against ``max(bits)`` instead of membership.
        """
        with pytest.raises(ValueError, match=r"bit position\(s\) \[1\]"):
            MockSignalEncodedEventsInterface(
                digital_line_waveforms={0: "pulses", 3: "pulses"},
                detection_configuration={"word": [{"signal_conditioning": {"bits": [1]}, "detection": "rising"}]},
            )

    def test_the_message_lists_the_positions_the_word_does_carry(self):
        """What the caller needs to fix it, which for a real word is its ``niXDChans1`` entries."""
        with pytest.raises(ValueError, match=r"bit positions are \[0, 3\]"):
            MockSignalEncodedEventsInterface(
                digital_line_waveforms={0: "pulses", 3: "pulses"},
                detection_configuration={"word": [{"signal_conditioning": {"bits": [1]}, "detection": "rising"}]},
            )

    def test_a_declared_bit_across_the_gap_is_read_normally(self):
        """The other side of the same test: membership, not a range, so bit 3 is perfectly addressable."""
        interface = MockSignalEncodedEventsInterface(
            digital_line_waveforms={0: "pulses", 3: "pulses"},
            detection_configuration={"word": [{"signal_conditioning": {"bits": [3]}, "detection": "high_period"}]},
        )

        assert interface._get_events_data_dict()["word"].timestamps.size == 4

    def test_a_declared_line_that_never_fired_still_converts(self):
        """The case this check must not swallow: recorded, never toggled, so a faithful zero-row table.

        Its output is identical to the rejected one above, which is the whole reason the rejection has
        to happen at construction and from the declaration rather than from the samples.
        """
        interface = MockSignalEncodedEventsInterface(
            digital_line_waveforms={0: "pulses", 3: "idle"},
            detection_configuration={"word": [{"signal_conditioning": {"bits": [3]}, "detection": "high_period"}]},
        )

        assert interface._get_events_data_dict()["word"].timestamps.size == 0


class TestGetEventTimesOnAReading:
    """The one part of ``get_event_times`` that is about readings rather than about the base class.

    The rest of the query is covered in ``test_base_events_interface.py``, since it is
    ``BaseEventsInterface`` behaviour and works the same on a pre-extracted source.
    """

    def test_a_durative_reading_answers_with_the_edge_times(self):
        """``high_period`` pairs each rising edge with the next falling one, so its onsets are the edges.

        Which is why a line written with its pulse widths needs no second reading to be usable for
        alignment, and why the query needs no way to ask for one.
        """
        durative_interface = MockSignalEncodedEventsInterface(
            digital_line_waveforms={0: ("camera", "pulses")},
            detection_configuration={
                "word": [{"signal_conditioning": {"bits": [0]}, "detection": "high_period", "event_name": "camera"}]
            },
        )
        point_interface = MockSignalEncodedEventsInterface(
            digital_line_waveforms={0: ("camera", "pulses")},
            detection_configuration={
                "word": [{"signal_conditioning": {"bits": [0]}, "detection": "rising", "event_name": "camera"}]
            },
        )

        timestamps_from_point_reading = point_interface.get_event_times(event_type_source_id="camera")
        timestamps_from_durative_reading = durative_interface.get_event_times(event_type_source_id="camera")

        np.testing.assert_allclose(timestamps_from_durative_reading, timestamps_from_point_reading)
