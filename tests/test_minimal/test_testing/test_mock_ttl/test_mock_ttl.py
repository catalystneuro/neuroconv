from pathlib import Path

from pynwb import NWBHDF5IO
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal

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

    @classmethod
    def tearDownClass(cls):
        cls.io.close()

    def test_default_mock_ttl(self):
        ttl_signal = generate_mock_ttl_signal()

        assert_array_equal(x=ttl_signal, y=self.nwbfile.acquisition["DefaultTTLSignal"].data)
