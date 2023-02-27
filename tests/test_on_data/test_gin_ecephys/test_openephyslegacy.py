from hdmf.testing import TestCase

from neuroconv.datainterfaces.ecephys.openephys.openephyslegacydatainterface import OpenEphysLegacyRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH

OPENEPHYS_PATH = ECEPHY_DATA_PATH / "openephys"


class TestOpenEphysLegacyConversions(TestCase):
    def setUp(self) -> None:
        self.folder_path = OPENEPHYS_PATH / "OpenEphys_SampleData_1"
        self.interface = OpenEphysLegacyRecordingInterface(folder_path=self.folder_path)

    def test_openephyslegacy_streams(self):
        stream_names = self.interface.get_stream_names(folder_path=self.folder_path)
        self.assertEqual(stream_names, ["Signals CH"])
        self.assertEqual(self.interface.source_data["stream_name"], "Signals CH")

    def test_openephyslegacy_raises(self):
        with self.assertRaisesWith(
            AssertionError,
            "The selected stream 'AUX' is not in the available streams '['Signals CH']'!",
        ):
            OpenEphysLegacyRecordingInterface(folder_path=self.folder_path, stream_name="AUX")

    def test_openephyslegacy_source_schema(self):
        schema = self.interface.get_source_schema()
        expected_description = "Path to directory containing OpenEphys legacy files."
        self.assertEqual(schema["properties"]["folder_path"]["description"], expected_description)
