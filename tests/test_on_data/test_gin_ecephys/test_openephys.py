from hdmf.testing import TestCase

from neuroconv.datainterfaces import OpenEphysRecordingInterface
from neuroconv.datainterfaces.ecephys.openephys.openephysbinarydatainterface import OpenEphysBinaryRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH


class TestOpenOpenEphysRecordingInterfaceRedirects(TestCase):
    def test_legacy_format_raises_NotImplementedError(self):
        folder_path = ECEPHY_DATA_PATH / "openephys" / "OpenEphys_SampleData_1"

        exc_msg = "OpenEphysLegacyRecordingInterface had not been implemented yet."
        with self.assertRaisesWith(NotImplementedError, exc_msg=exc_msg):
            OpenEphysRecordingInterface(folder_path=folder_path)

    def test_binary_format(self):
        folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking"
        interface = OpenEphysRecordingInterface(folder_path=folder_path)
        self.assertIsInstance(interface, OpenEphysBinaryRecordingInterface)

    def test_unrecognized_format(self):
        folder_path = ECEPHY_DATA_PATH / "plexon"
        exc_msg = "The Open Ephys data must be in 'legacy' (.continuous) or in 'binary' (.dat) format."
        with self.assertRaisesWith(AssertionError, exc_msg=exc_msg):
            OpenEphysRecordingInterface(folder_path=folder_path)
