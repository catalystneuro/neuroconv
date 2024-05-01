import numpy as np
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal

from neuroconv.tools.signal_processing import (
    create_ogen_stimulation_timeseries,
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
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([50_000, 100_000, 150_000])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

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
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([50_000, 100_000, 150_000])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_start_during_on_pulse_int16(self):
        """
        Generate a single TTL pulse that is already in an 'on' condition when the signal starts.

        This means there is no detectable rising time but one detectable falling time.
        """
        ttl_signal = generate_mock_ttl_signal(ttl_times=[0.0])

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.empty(shape=0)
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([25_000])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_end_during_on_pulse_int16(self):
        """
        Generate a single TTL pulse that does not end before the signal ends.

        This means there is only one detectable rising time and no detetectable falling times.
        """
        ttl_signal = generate_mock_ttl_signal(signal_duration=5.0, ttl_times=[2.5], ttl_duration=5.0)

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([62_500])
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.empty(shape=0)
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_end_during_off_pulse_int16(self):
        """A couple of normal TTL pulses at the specified time."""
        ttl_signal = generate_mock_ttl_signal(signal_duration=10.0, ttl_times=[1.1, 6.2], ttl_duration=2.0)

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([27_500, 155_000])
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([77_500, 205_000])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_start_during_on_pulse_floats(self):
        """
        Generate a single TTL pulse that is already in an 'on' condition when the signal starts.

        This means there is no detectable rising time but one detectable falling time.
        """
        ttl_signal = generate_mock_ttl_signal(ttl_times=[0.0], dtype="float32")

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.empty(shape=0)
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([25_000])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_end_during_on_pulse_floats(self):
        """
        Generate a single TTL pulse that does not end before the signal ends.

        This means there is only one detectable rising time and no detetectable falling times.
        """
        ttl_signal = generate_mock_ttl_signal(signal_duration=5.0, ttl_times=[2.5], ttl_duration=5.0, dtype="float32")

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([62_500])
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.empty(shape=0)
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_end_during_off_pulse_floats(self):
        """A couple of normal TTL pulses at the specified time."""
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=10.0, ttl_times=[1.1, 6.2], ttl_duration=2.0, dtype="float32"
        )

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([27_500, 155_000])
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([77_500, 205_000])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_custom_threshold_floats(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=10.0, ttl_times=[1.1, 6.2], ttl_duration=2.0, dtype="float32"
        )

        rising_frames = get_rising_frames_from_ttl(trace=ttl_signal, threshold=1.5)
        falling_frames = get_falling_frames_from_ttl(trace=ttl_signal, threshold=1.5)

        expected_rising_frames = np.array([27_500, 155_000])
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([77_500, 205_000])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)


def test_create_ogen_stimulation_timeseries():
    stimulation_onset_times = [10, 20, 30]
    duration = 1
    frequency = 4
    pulse_width = 0.01
    power = 1
    expected_timestamps = [
        0,
        10,
        10.01,
        10.25,
        10.26,
        10.5,
        10.51,
        10.75,
        10.76,
        20,
        20.01,
        20.25,
        20.26,
        20.5,
        20.51,
        20.75,
        20.76,
        30,
        30.01,
        30.25,
        30.26,
        30.5,
        30.51,
        30.75,
        30.76,
    ]
    expected_data = [i % 2 for i in range(len(expected_timestamps))]  # 0, 1, 0, 1, ...
    expected_timestamps = np.array(expected_timestamps, dtype=np.float64)
    expected_data = np.array(expected_data, dtype=np.float64)

    timestamps, data = create_ogen_stimulation_timeseries(
        stimulation_onset_times=stimulation_onset_times,
        duration=duration,
        frequency=frequency,
        pulse_width=pulse_width,
        power=power,
    )

    assert_array_equal(timestamps, expected_timestamps)
    assert_array_equal(data, expected_data)


def test_create_ogen_stimulation_timeseries_cts():
    stimulation_onset_times = [10, 20, 30]
    duration = 1
    frequency = 1
    pulse_width = 1
    power = 1
    expected_timestamps = [0, 10, 11, 20, 21, 30, 31]
    expected_data = [i % 2 for i in range(len(expected_timestamps))]  # 0, 1, 0, 1, ...
    expected_timestamps = np.array(expected_timestamps, dtype=np.float64)
    expected_data = np.array(expected_data, dtype=np.float64)

    timestamps, data = create_ogen_stimulation_timeseries(
        stimulation_onset_times=stimulation_onset_times,
        duration=duration,
        frequency=frequency,
        pulse_width=pulse_width,
        power=power,
    )

    assert_array_equal(timestamps, expected_timestamps)
    assert_array_equal(data, expected_data)
