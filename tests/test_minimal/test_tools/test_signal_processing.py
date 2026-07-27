import numpy as np
import pytest
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal

from neuroconv.tools.signal_processing import (
    _condition_signal,
    _detect_events,
    _frames_to_seconds,
    get_falling_frames_from_ttl,
    get_rising_frames_from_ttl,
)
from neuroconv.tools.testing import generate_mock_ttl_signal


class TestGetRisingAndFallingTimesFromTTL(TestCase):
    def test_input_dimensions_assertion(self):
        with self.assertRaisesWith(
            exc_type=ValueError, exc_msg="This function expects a one-dimensional array! Received shape of (2, 2)."
        ):
            get_rising_frames_from_ttl(trace=np.empty(shape=(2, 2)))

        with self.assertRaisesWith(
            exc_type=ValueError, exc_msg="This function expects a one-dimensional array! Received shape of (2, 2)."
        ):
            get_falling_frames_from_ttl(trace=np.empty(shape=(2, 2)))

    def test_current_defaults(self):
        ttl_signal = generate_mock_ttl_signal()

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([25_000, 75_000, 125_000])
        assert_array_equal(rising_frames, expected_rising_frames)

        expected_falling_frames = np.array([50_000, 100_000, 150_000])
        assert_array_equal(falling_frames, expected_falling_frames)

    def test_explicit_original_defaults(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=7.0,
            ttl_times=None,
            ttl_duration=1.0,
            sampling_frequency_hz=25_000.0,
            dtype="int16",
            baseline_mean=None,
            signal_mean=None,
            channel_noise=None,
            random_seed=0,
        )

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([25_000, 75_000, 125_000])
        assert_array_equal(rising_frames, expected_rising_frames)

        expected_falling_frames = np.array([50_000, 100_000, 150_000])
        assert_array_equal(falling_frames, expected_falling_frames)

    def test_start_during_on_pulse_int16(self):
        """
        Generate a single TTL pulse that is already in an 'on' condition when the signal starts.

        This means there is no detectable rising time but one detectable falling time.
        """
        ttl_signal = generate_mock_ttl_signal(ttl_times=[0.0])

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.empty(shape=0)
        assert_array_equal(rising_frames, expected_rising_frames)

        expected_falling_frames = np.array([25_000])
        assert_array_equal(falling_frames, expected_falling_frames)

    def test_end_during_on_pulse_int16(self):
        """
        Generate a single TTL pulse that does not end before the signal ends.

        This means there is only one detectable rising time and no detetectable falling times.
        """
        ttl_signal = generate_mock_ttl_signal(signal_duration=5.0, ttl_times=[2.5], ttl_duration=5.0)

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([62_500])
        assert_array_equal(rising_frames, expected_rising_frames)

        expected_falling_frames = np.empty(shape=0)
        assert_array_equal(falling_frames, expected_falling_frames)

    def test_end_during_off_pulse_int16(self):
        """A couple of normal TTL pulses at the specified time."""
        ttl_signal = generate_mock_ttl_signal(signal_duration=10.0, ttl_times=[1.1, 6.2], ttl_duration=2.0)

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([27_500, 155_000])
        assert_array_equal(rising_frames, expected_rising_frames)

        expected_falling_frames = np.array([77_500, 205_000])
        assert_array_equal(falling_frames, expected_falling_frames)

    def test_start_during_on_pulse_floats(self):
        """
        Generate a single TTL pulse that is already in an 'on' condition when the signal starts.

        This means there is no detectable rising time but one detectable falling time.
        """
        ttl_signal = generate_mock_ttl_signal(ttl_times=[0.0], dtype="float32")

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.empty(shape=0)
        assert_array_equal(rising_frames, expected_rising_frames)

        expected_falling_frames = np.array([25_000])
        assert_array_equal(falling_frames, expected_falling_frames)

    def test_end_during_on_pulse_floats(self):
        """
        Generate a single TTL pulse that does not end before the signal ends.

        This means there is only one detectable rising time and no detetectable falling times.
        """
        ttl_signal = generate_mock_ttl_signal(signal_duration=5.0, ttl_times=[2.5], ttl_duration=5.0, dtype="float32")

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([62_500])
        assert_array_equal(rising_frames, expected_rising_frames)

        expected_falling_frames = np.empty(shape=0)
        assert_array_equal(falling_frames, expected_falling_frames)

    def test_end_during_off_pulse_floats(self):
        """A couple of normal TTL pulses at the specified time."""
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=10.0, ttl_times=[1.1, 6.2], ttl_duration=2.0, dtype="float32"
        )

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([27_500, 155_000])
        assert_array_equal(rising_frames, expected_rising_frames)

        expected_falling_frames = np.array([77_500, 205_000])
        assert_array_equal(falling_frames, expected_falling_frames)

    def test_custom_threshold_floats(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=10.0, ttl_times=[1.1, 6.2], ttl_duration=2.0, dtype="float32"
        )

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal, threshold=1.5)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal, threshold=1.5)

        expected_rising_frames = np.array([27_500, 155_000])
        assert_array_equal(rising_frames, expected_rising_frames)

        expected_falling_frames = np.array([77_500, 205_000])
        assert_array_equal(falling_frames, expected_falling_frames)


class TestConditionSignal:
    """Conditioning is signal-to-signal: it returns a discrete-valued signal of the same length."""

    def test_omission_returns_the_trace_unchanged(self):
        """Omitting conditioning asserts the signal is already discrete-valued, the recorded-line case."""
        line = np.array([0, 0, 1, 1, 0], dtype="int16")
        assert_array_equal(_condition_signal(line), line)
        assert_array_equal(_condition_signal(line, None), line)

    def test_one_bit_gives_a_line_and_several_give_a_coded_value(self):
        word = np.array([0, 1, 3, 3, 2, 0], dtype="int64")
        assert_array_equal(_condition_signal(word, {"bits": [0]}), np.array([0, 1, 1, 1, 0, 0]))
        assert_array_equal(_condition_signal(word, {"bits": [1]}), np.array([0, 0, 1, 1, 1, 0]))
        # Least-significant first, so [0, 1] reconstructs the two-bit word itself.
        assert_array_equal(_condition_signal(word, {"bits": [0, 1]}), word)

    def test_thresholds_give_a_band_index(self):
        trace = np.array([0.1, 0.1, 2.0, 2.0, 4.0, 0.1])
        assert_array_equal(_condition_signal(trace, {"thresholds": [1.0, 3.0]}), np.array([0, 0, 1, 1, 2, 0]))

    def test_binarize_midpoint_is_invariant_under_windowing(self):
        """The midpoint is unmoved by any sample between the two levels, so a stub cuts where the full run does."""
        full = np.array([48.0, 48.2, 64.0, 63.8, 48.1, 55.0, 64.0])
        stub = full[:4]
        assert_array_equal(
            _condition_signal(full, {"binarize": "midpoint"})[:4], _condition_signal(stub, {"binarize": "midpoint"})
        )

    def test_binarize_mean_moves_with_the_window(self):
        """Why the mean is not the default: the same samples cut differently depending on what you sliced."""
        full = np.array([48.0, 48.0, 48.0, 48.0, 64.0, 64.0])
        stub = full[3:]
        assert _condition_signal(full, {"binarize": "mean"})[3] == 0
        assert _condition_signal(stub, {"binarize": "mean"})[0] == 0
        assert full.mean() != stub.mean()

    def test_conditioning_preserves_length(self):
        """The contract detection depends on: frame indices must still address the caller's timestamps."""
        trace = np.array([0.1, 2.0, 4.0, 0.1, 2.0])
        for conditioning in ({"thresholds": [1.0, 3.0]}, {"binarize": "midpoint"}, None):
            assert _condition_signal(trace, conditioning).size == trace.size

    def test_two_cuts_raise(self):
        with pytest.raises(ValueError, match="more than one cut"):
            _condition_signal(np.array([0, 1]), {"bits": [0], "thresholds": [0.5]})

    def test_unsorted_thresholds_raise(self):
        with pytest.raises(ValueError, match="strictly increasing"):
            _condition_signal(np.array([0.0, 1.0]), {"thresholds": [3.0, 1.0]})


class TestDetectEvents:
    """Detection is signal-to-events, in frame indices, and takes no threshold."""

    # A 0/1 line with two high pulses: rising at frames [2, 7], falling at frames [5, 8].
    LINE = np.array([0, 0, 1, 1, 1, 0, 0, 1, 0], dtype="int16")

    def test_takes_no_threshold(self):
        """The acceptance test for the split: if a threshold survived here, conditioning did not move."""
        import inspect

        assert "threshold" not in inspect.signature(_detect_events).parameters

    def test_rising_and_falling_are_point_events(self):
        onsets, offsets = _detect_events(self.LINE, detection="rising")
        assert_array_equal(onsets, np.array([2, 7]))
        assert offsets is None

        onsets, offsets = _detect_events(self.LINE, detection="falling")
        assert_array_equal(onsets, np.array([5, 8]))
        assert offsets is None

    def test_high_period_pairs_rising_to_next_falling(self):
        onsets, offsets = _detect_events(self.LINE, detection="high_period")
        assert_array_equal(onsets, np.array([2, 7]))
        assert_array_equal(offsets, np.array([5.0, 8.0]))

    def test_low_period_offset_is_nan_when_unclosed(self):
        onsets, offsets = _detect_events(self.LINE, detection="low_period")
        assert_array_equal(onsets, np.array([5, 8]))
        assert offsets[0] == 7.0
        assert np.isnan(offsets[1])  # the last low span never closes

    def test_value_change_is_the_reading_a_multi_valued_signal_admits(self):
        """Every transition is one event type, with nothing to tell them apart and so nothing carried.

        The four edge readings would be refused here by the backstop; distinguishing the bands is a
        conditioning job (one cut per distinction), not something this reading encodes.
        """
        banded = np.array([0, 0, 1, 1, 2, 0])
        onsets, offsets = _detect_events(banded, detection="value_change")
        assert_array_equal(onsets, np.array([2, 4, 5]))
        assert offsets is None

    def test_a_signal_that_never_toggles_yields_no_events(self):
        """One distinct value passes the backstop: it must convert to a zero-row table, not fail."""
        onsets, offsets = _detect_events(np.ones(10), detection="high_period")
        assert onsets.size == 0

    def test_edge_reading_on_a_multi_level_signal_raises(self):
        """The read-time backstop: with three levels there is no fact about which count as high."""
        with pytest.raises(ValueError, match="needs a two-valued signal"):
            _detect_events(np.array([0, 1, 2, 1, 0]), detection="rising")

    def test_an_unsigned_line_reads_the_same_as_a_signed_one(self):
        """Differencing an unsigned dtype wraps, which would turn every fall into a rise.

        Intan hands its digital lines over as uint16, so this is a real input rather than a synthetic
        one, and the failure it guards is silent: the line would report both its edges as rising.
        """
        for dtype in ("uint8", "uint16", "uint32", "uint64"):
            unsigned = self.LINE.astype(dtype)
            assert_array_equal(_detect_events(unsigned, "rising")[0], np.array([2, 7]))
            assert_array_equal(_detect_events(unsigned, "falling")[0], np.array([5, 8]))
            onsets, offsets = _detect_events(unsigned, "high_period")
            assert_array_equal(onsets, np.array([2, 7]))
            assert_array_equal(offsets, np.array([5.0, 8.0]))

    def test_invalid_detection_raises(self):
        with pytest.raises(ValueError, match="Invalid detection"):
            _detect_events(self.LINE, detection="nope")


class TestFramesToSeconds:
    """Durations come from reading the clock at both ends, which is exact on any clock."""

    LINE = np.array([0, 0, 1, 1, 1, 0, 0, 1, 0], dtype="int16")

    def test_regular_clock(self):
        timestamps = np.arange(9) * 0.001
        onsets, durations = _frames_to_seconds(*_detect_events(self.LINE, "high_period")[:2], timestamps)
        assert_array_equal(onsets, np.array([0.002, 0.007]))
        assert_array_equal(durations, np.array([0.003, 0.001]))

    def test_irregular_clock_is_exact_where_a_median_period_would_not_be(self):
        """The reason durations are not a frame count times an estimated period."""
        # A one-second gap between frames 4 and 5; every other step is 1 ms.
        timestamps = np.array([0.0, 0.001, 0.002, 0.003, 0.004, 1.004, 1.005, 1.006, 1.007])
        onsets, durations = _frames_to_seconds(*_detect_events(self.LINE, "high_period")[:2], timestamps)

        assert_array_equal(onsets, np.array([0.002, 1.006]))
        # Frames 2 -> 5 really spans the gap: 1.004 - 0.002. A median period of 1 ms would say 0.003.
        assert durations[0] == pytest.approx(1.002)
        assert durations[1] == pytest.approx(0.001)

    def test_point_reading_has_no_durations(self):
        timestamps = np.arange(9) * 0.001
        onsets, durations = _frames_to_seconds(*_detect_events(self.LINE, "rising")[:2], timestamps)
        assert_array_equal(onsets, np.array([0.002, 0.007]))
        assert durations is None

    def test_unclosed_event_keeps_a_nan_duration(self):
        """NaN marks a truncated interval, which is what NWB's DurationVectorData expects."""
        timestamps = np.arange(9) * 0.001
        _, durations = _frames_to_seconds(*_detect_events(self.LINE, "low_period")[:2], timestamps)
        assert durations[0] == pytest.approx(0.002)
        assert np.isnan(durations[1])

    def test_a_callable_clock_is_only_asked_for_the_event_frames(self):
        """A source deriving its clock from a rate passes a callable instead of materialising it.

        The point is not that the answer differs, it is that the whole clock is never built: Intan at
        30 kHz over three hours would be 324 million timestamps to read a handful of edges.
        """
        asked_for = []

        def clock(frames):
            asked_for.append(np.asarray(frames))
            return np.asarray(frames) * 0.001

        onsets, durations = _frames_to_seconds(*_detect_events(self.LINE, "high_period")[:2], clock)

        assert_array_equal(onsets, np.array([0.002, 0.007]))
        assert_array_equal(durations, np.array([0.003, 0.001]))
        # Onsets once and closing frames once, and never more frames than there are events.
        assert [frames.tolist() for frames in asked_for] == [[2, 7], [5, 8]]

    def test_a_callable_clock_agrees_with_the_array_it_replaces(self):
        timestamps = np.array([0.0, 0.5, 0.7, 0.9, 1.3, 2.0, 2.1, 2.5, 9.0])
        expected = _frames_to_seconds(*_detect_events(self.LINE, "high_period")[:2], timestamps)
        actual = _frames_to_seconds(*_detect_events(self.LINE, "high_period")[:2], lambda f: timestamps[f])
        assert_array_equal(actual[0], expected[0])
        assert_array_equal(actual[1], expected[1])
