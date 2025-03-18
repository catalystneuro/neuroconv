import numpy as np
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal

from neuroconv.tools.signal_processing import (
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
