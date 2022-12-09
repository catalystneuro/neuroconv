import numpy as np
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal

from neuroconv.tools.signal_processing import parse_rising_and_falling_frames_from_ttl
from neuroconv.tools.testing import generate_mock_ttl_signal


class TestParsingRisingAndFallingTimesFromTTL(TestCase):
    def test_default(self):
        ttl_signal = generate_mock_ttl_signal()

        rising_frames, falling_frames = parse_rising_and_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([12499, 74999])
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([37499, 99999])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_start_during_on_pulse(self):
        """
        Default generation tests start in 'off' condition.

        What should 'correct' behavior here be?

        We searh for rising frames to count as a 'start' signal, but if the signal starts in an 'on' condition,
        how to interpret?
        """
        ttl_signal = generate_mock_ttl_signal(ttl_times=[0.0, 3.4])

        rising_frames, falling_frames = parse_rising_and_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([84999])
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([24999, 109999])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_end_during_on_pulse(self):
        """
        Default generation tests start in 'off' condition.

        What should 'correct' behavior here be?

        We searh for rising frames to count as a 'start' signal, but if the signal starts in an 'on' condition,
        how to interpret?
        """
        ttl_signal = generate_mock_ttl_signal(signal_duration=5.0, ttl_on_duration=5.0, ttl_off_duration=2.0)

        rising_frames, falling_frames = parse_rising_and_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([24999])
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_end_during_off_pulse(self):
        ttl_signal = generate_mock_ttl_signal(signal_duration=10.0, ttl_on_duration=2.0, ttl_off_duration=5.0)

        rising_frames, falling_frames = parse_rising_and_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([62499])
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([112499])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_start_during_on_pulse_floats(self):
        ttl_signal = generate_mock_ttl_signal(ttl_times=[0.0, 3.4], dtype="float32")

        rising_frames, falling_frames = parse_rising_and_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([84999, 92131])
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([24999, 92132, 109999])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_end_during_on_pulse_floats(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=5.0, ttl_on_duration=5.0, ttl_off_duration=2.0, dtype="float32"
        )

        rising_frames, falling_frames = parse_rising_and_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([24999, 118851])
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([118852])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)

    def test_end_during_off_pulse_floats(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=10.0, ttl_on_duration=2.0, ttl_off_duration=5.0, dtype="float32"
        )

        rising_frames, falling_frames = parse_rising_and_falling_frames_from_ttl(trace=ttl_signal)

        expected_rising_frames = np.array([62499, 92131])
        assert_array_equal(x=rising_frames, y=expected_rising_frames)

        expected_falling_frames = np.array([92132, 112499])
        assert_array_equal(x=falling_frames, y=expected_falling_frames)
