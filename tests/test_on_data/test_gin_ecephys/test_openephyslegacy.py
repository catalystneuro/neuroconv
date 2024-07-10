from datetime import datetime

from hdmf.testing import TestCase

from neuroconv.datainterfaces.ecephys.openephys.openephyslegacydatainterface import (
    OpenEphysLegacyRecordingInterface,
)

from ..setup_paths import ECEPHY_DATA_PATH

OPENEPHYS_PATH = ECEPHY_DATA_PATH / "openephys"


class TestOpenEphysLegacyConversions(TestCase):
    def setUp(self) -> None:
        self.folder_path = OPENEPHYS_PATH / "OpenEphys_SampleData_1"
        self.interface = OpenEphysLegacyRecordingInterface(folder_path=self.folder_path)

    def test_openephyslegacy_streams(self):
        stream_names = self.interface.get_stream_names(folder_path=self.folder_path)
        self.assertCountEqual(first=stream_names, second=["Signals CH"])
        assert self.interface.source_data["stream_name"] is None

    def test_openephyslegacy_raises(self):
        with self.assertRaisesWith(
            ValueError,
            "The selected stream 'AUX' is not in the available streams '['Signals CH']'!",
        ):
            OpenEphysLegacyRecordingInterface(folder_path=self.folder_path, stream_name="AUX")

    def test_openephyslegacy_source_schema(self):
        schema = self.interface.get_source_schema()
        expected_description = "Path to directory containing OpenEphys legacy files."
        self.assertEqual(schema["properties"]["folder_path"]["description"], expected_description)

    def test_openephyslegacy_date_parse(self):
        extractor = self.interface.recording_extractor
        neo_reader = extractor.neo_reader

        blocks = neo_reader.raw_annotations.get("blocks", [])
        segments = blocks[0].get("segments", [])
        # Override date_created to test date is parsed
        segments[0].update(date_created="29-Apr-2020 16554")
        with self.assertWarnsWith(
            UserWarning,
            exc_msg="The timestamp for starting time from openephys metadata is ambiguous ('16554')! Only the date will be auto-populated in metadata. Please update the timestamp manually to record this value with the highest known temporal resolution.",
        ):
            metadata = self.interface.get_metadata()

        assert "session_start_time" in metadata["NWBFile"]
        self.assertEqual(metadata["NWBFile"]["session_start_time"], datetime(2020, 4, 29, 0, 0))
