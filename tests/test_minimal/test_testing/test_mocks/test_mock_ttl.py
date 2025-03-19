from pathlib import Path

from hdmf.testing import TestCase
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv.tools.testing import generate_mock_ttl_signal


class TestMockTTLSignals(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nwbfile_path = Path(__file__).parent / "mock_ttl_examples.nwb"

        assert cls.nwbfile_path.exists(), (
            "The file 'mock_ttl_examples.nwb' is missing from the testing suite! "
            "You can download the previously frozen version from the GitHub repository!"
        )

        cls.io = NWBHDF5IO(path=cls.nwbfile_path, mode="r")
        cls.nwbfile = cls.io.read()

        # Standard choice of sampling frequency for testing
        cls.sampling_frequency_hz = 1000.0

    @classmethod
    def tearDownClass(cls):
        cls.io.close()

    def test_overlapping_ttl_assertion(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=("There are overlapping TTL 'on' intervals! Please specify disjoint on/off periods."),
        ):
            generate_mock_ttl_signal(ttl_times=[1.2, 1.5, 1.6], ttl_duration=0.2)

    def test_single_frame_overlapping_ttl_assertion(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=("There are overlapping TTL 'on' intervals! Please specify disjoint on/off periods."),
        ):
            generate_mock_ttl_signal(ttl_times=[1.2, 1.4], ttl_duration=0.2)

    def test_baseline_mean_int_dtype_float_assertion(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "If specifying the 'baseline_mean' manually, please ensure it matches the 'dtype'! "
                "Received 'int', should be a float."
            ),
        ):
            generate_mock_ttl_signal(baseline_mean=1, dtype="float32")

    def test_signal_mean_int_dtype_float_assertion(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "If specifying the 'signal_mean' manually, please ensure it matches the 'dtype'! "
                "Received 'int', should be a float."
            ),
        ):
            generate_mock_ttl_signal(signal_mean=1, dtype="float32")

    def test_channel_noise_int_dtype_float_assertion(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "If specifying the 'channel_noise' manually, please ensure it matches the 'dtype'! "
                "Received 'int', should be a float."
            ),
        ):
            generate_mock_ttl_signal(channel_noise=1, dtype="float32")

    def test_baseline_mean_int_dtype_int_assertion(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "If specifying the 'baseline_mean' manually, please ensure it matches the 'dtype'! "
                "Received 'float', should be an integer."
            ),
        ):
            generate_mock_ttl_signal(baseline_mean=1.2)

    def test_signal_mean_int_dtype_int_assertion(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "If specifying the 'signal_mean' manually, please ensure it matches the 'dtype'! "
                "Received 'float', should be an integer."
            ),
        ):
            generate_mock_ttl_signal(signal_mean=1.2)

    def test_channel_noise_int_dtype_int_assertion(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "If specifying the 'channel_noise' manually, please ensure it matches the 'dtype'! "
                "Received 'float', should be an integer."
            ),
        ):
            generate_mock_ttl_signal(channel_noise=1.2)

    def test_default(self):
        ttl_signal = generate_mock_ttl_signal()

        assert_array_equal(ttl_signal, self.nwbfile.acquisition["DefaultTTLSignal"].data)

    def test_irregular_short_pulses(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=2.5,
            ttl_times=[0.22, 1.37],
            ttl_duration=0.25,
            sampling_frequency_hz=self.sampling_frequency_hz,
        )

        assert_array_equal(ttl_signal, self.nwbfile.acquisition["IrregularShortPulses"].data)

    def test_non_default_regular(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=2.7,
            ttl_times=[0.2, 1.2, 2.2],
            ttl_duration=0.3,
            sampling_frequency_hz=self.sampling_frequency_hz,
        )

        assert_array_equal(ttl_signal, self.nwbfile.acquisition["NonDefaultRegular"].data)

    def test_non_default_regular_adjusted_means(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=2.7,
            ttl_times=[0.2, 1.2, 2.2],
            ttl_duration=0.3,
            sampling_frequency_hz=self.sampling_frequency_hz,
            baseline_mean=300,
            signal_mean=20000,
        )

        assert_array_equal(ttl_signal, self.nwbfile.acquisition["NonDefaultRegularAdjustedMeans"].data)

    def test_irregular_short_pulses_adjusted_noise(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=2.5,
            ttl_times=[0.22, 1.37],
            ttl_duration=0.25,
            sampling_frequency_hz=self.sampling_frequency_hz,
            channel_noise=2,
        )

        assert_array_equal(ttl_signal, self.nwbfile.acquisition["IrregularShortPulsesAdjustedNoise"].data)

    def test_non_default_regular_floats(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=2.7,
            ttl_times=[0.2, 1.2, 2.2],
            ttl_duration=0.3,
            sampling_frequency_hz=self.sampling_frequency_hz,
            dtype="float32",
        )

        assert_array_equal(ttl_signal, self.nwbfile.acquisition["NonDefaultRegularFloats"].data)

    def test_non_default_regular_as_uint16(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=2.7,
            ttl_times=[0.2, 1.2, 2.2],
            ttl_duration=0.3,
            sampling_frequency_hz=self.sampling_frequency_hz,
            dtype="uint16",
        )

        assert_array_equal(ttl_signal, self.nwbfile.acquisition["NonDefaultRegularUInt16"].data)

    def test_non_default_regular_floats_adjusted_means_and_noise(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=2.7,
            ttl_times=[0.2, 1.2, 2.2],
            ttl_duration=0.3,
            sampling_frequency_hz=self.sampling_frequency_hz,
            dtype="float32",
            baseline_mean=1.1,
            signal_mean=7.2,
            channel_noise=0.4,
        )

        assert_array_equal(ttl_signal, self.nwbfile.acquisition["FloatsAdjustedMeansAndNoise"].data)

    def test_irregular_short_pulses_different_seed(self):
        ttl_signal = generate_mock_ttl_signal(
            signal_duration=2.5,
            ttl_times=[0.22, 1.37],
            ttl_duration=0.25,
            sampling_frequency_hz=self.sampling_frequency_hz,
            random_seed=1,
        )

        assert_array_equal(ttl_signal, self.nwbfile.acquisition["IrregularShortPulsesDifferentSeed"].data)
