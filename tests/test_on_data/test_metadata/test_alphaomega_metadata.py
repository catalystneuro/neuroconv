from datetime import datetime
import unittest

from neuroconv.datainterfaces import AlphaOmegaRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH


class TestEDFMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder_path = ECEPHY_DATA_PATH / "alphaomega" / "mpx_map_version4"
        cls.interface = AlphaOmegaRecordingInterface(folder_path=folder_path)

    def test_nwb_metadata(self):
        nwb_metadata = self.interface.get_metadata()["NWBFile"]

        extracted_session_start_time = nwb_metadata["session_start_time"]
        expected_session_start_time = datetime(2021, 11, 19, 15, 23, 15)

        assert extracted_session_start_time == expected_session_start_time


if __name__ == "__main__":
    unittest.main()
