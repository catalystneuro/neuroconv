import unittest

from neuroconv.datainterfaces.ecephys.openephys.openephyslegacydatainterface import OpenEphysLegacyRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH

OPENEPHYS_PATH = ECEPHY_DATA_PATH / "openephys"


class TestOpenEphysLegacyConversions(unittest.TestCase):
    def setUp(self) -> None:
        self.folder_path = OPENEPHYS_PATH / "OpenEphys_SampleData_1"
        self.interface = OpenEphysLegacyRecordingInterface(folder_path=self.folder_path)

    def test_openephyslegacy_streams(self):
        streams = self.interface._get_stream_channels()
        self.assertEqual(list(streams["id"]), ["CH"])
        self.assertEqual(list(streams["name"]), ["Signals CH"])
        self.assertEqual(self.interface.source_data["stream_id"], "CH")

    def test_openephyslegacy_stub_test_True(self):
        interface = OpenEphysLegacyRecordingInterface(folder_path=self.folder_path, stub_test=True)
        self.assertEqual(interface.subset_channels, [0, 1])

    def test_openephyslegacy_stub_test_False(self):
        interface = OpenEphysLegacyRecordingInterface(folder_path=self.folder_path, stub_test=False)
        self.assertNotEqual(interface.subset_channels, [0, 1])

    def test_openephyslegacy_source_schema(self):
        schema = self.interface.get_source_schema()
        expected_description = "Path to directory containing OpenEphys legacy files."
        self.assertEqual(schema["properties"]["folder_path"]["description"], expected_description)
