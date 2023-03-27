from hdmf.testing import TestCase

from neuroconv.datainterfaces import (
    OpenEphysBinaryRecordingInterface,
    OpenEphysLegacyRecordingInterface,
    OpenEphysRecordingInterface,
)

from ..setup_paths import ECEPHY_DATA_PATH


class TestOpenEphysRecordingInterfaceRedirects(TestCase):
    def test_legacy_format(self):
        folder_path = ECEPHY_DATA_PATH / "openephys" / "OpenEphys_SampleData_1"

        interface = OpenEphysRecordingInterface(folder_path=folder_path)
        self.assertIsInstance(interface, OpenEphysLegacyRecordingInterface)

    def test_propagate_stream_name(self):
        folder_path = ECEPHY_DATA_PATH / "openephys" / "OpenEphys_SampleData_1"
        exc_msg = "The selected stream 'AUX' is not in the available streams '['Signals CH']'!"
        with self.assertRaisesWith(AssertionError, exc_msg=exc_msg):
            OpenEphysRecordingInterface(folder_path=folder_path, stream_name="AUX")

    def test_binary_format(self):
        folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking"
        interface = OpenEphysRecordingInterface(folder_path=folder_path)
        self.assertIsInstance(interface, OpenEphysBinaryRecordingInterface)

    def test_unrecognized_format(self):
        folder_path = ECEPHY_DATA_PATH / "plexon"
        exc_msg = "The Open Ephys data must be in 'legacy' (.continuous) or in 'binary' (.dat) format."
        with self.assertRaisesWith(AssertionError, exc_msg=exc_msg):
            OpenEphysRecordingInterface(folder_path=folder_path)
