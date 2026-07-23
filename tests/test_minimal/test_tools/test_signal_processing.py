import numpy as np
import pytest
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal

from neuroconv.tools.signal_processing import (
    discretize_trace,
    get_falling_frames_from_ttl,
    get_rising_frames_from_ttl,
)
from neuroconv.tools.testing import generate_mock_ttl_signal


class TestGetRisingAndFallingTimesFromTTL(TestCase):
    def test_input_dimensions_assertion(self):
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg="This function expects a one-dimensional array! Received shape of (2, 2).",
        ):
            get_rising_frames_from_ttl(trace=np.empty(shape=(2, 2)))

        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg="This function expects a one-dimensional array! Received shape of (2, 2).",
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
            signal_duration=10.0,
            ttl_times=[1.1, 6.2],
            ttl_duration=2.0,
            dtype="float32",
        )

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([27_500, 155_000])
        assert_array_equal(rising_frames, expected_rising_frames)

        expected_falling_frames = np.array([77_500, 205_000])
        assert_array_equal(falling_frames, expected_falling_frames)

    def test_custom_threshold_floats(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=10.0,
            ttl_times=[1.1, 6.2],
            ttl_duration=2.0,
            dtype="float32",
        )

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal, threshold=1.5)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal, threshold=1.5)

        expected_rising_frames = np.array([27_500, 155_000])
        assert_array_equal(rising_frames, expected_rising_frames)

        expected_falling_frames = np.array([77_500, 205_000])
        assert_array_equal(falling_frames, expected_falling_frames)


class TestDiscretizeTrace:
    # A 0/1 line with two high pulses: rising at frames [2, 7], falling at frames [5, 8].
    TRACE = np.array([0, 0, 1, 1, 1, 0, 0, 1, 0], dtype="int16")

    def test_rising_and_falling_are_point_events(self):
        onsets, durations = discretize_trace(self.TRACE, detect="rising", threshold=0.5)
        assert_array_equal(onsets, np.array([2, 7]))
        assert durations is None

        onsets, durations = discretize_trace(self.TRACE, detect="falling", threshold=0.5)
        assert_array_equal(onsets, np.array([5, 8]))
        assert durations is None

    def test_high_period_pairs_rising_to_next_falling(self):
        onsets, durations = discretize_trace(self.TRACE, detect="high_period", threshold=0.5)
        assert_array_equal(onsets, np.array([2, 7]))
        assert_array_equal(durations, np.array([3.0, 1.0]))  # frames: 5-2 and 8-7

    def test_low_period_pairs_falling_to_next_rising_with_nan_when_unclosed(self):
        onsets, durations = discretize_trace(self.TRACE, detect="low_period", threshold=0.5)
        assert_array_equal(onsets, np.array([5, 8]))
        # First low span 5->7 closes (2 frames); the last falling at 8 has no later rising -> NaN.
        assert durations[0] == 2.0
        assert np.isnan(durations[1])

    def test_invalid_detect_raises(self):
        with pytest.raises(ValueError, match="Invalid detect"):
            discretize_trace(self.TRACE, detect="nope")
