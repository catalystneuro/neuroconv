from datetime import datetime
import unittest

from neuroconv import EDFRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH


class TestEDFMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        file_path = ECEPHY_DATA_PATH / "edf" / "edf+C.edf"
        cls.interface = EDFRecordingInterface(file_path=file_path)

    def test_nwb_metadata(self):

        nwb_metadata = self.interface.extract_nwb_file_metadata()

        extracted_session_start_time = nwb_metadata["session_start_time"]
        expected_session_start_time = datetime(2022, 3, 2, 10, 42, 19)
        assert extracted_session_start_time == expected_session_start_time

        extracted_experimenter = nwb_metadata["experimenter"]
        expected_experimenter = ""
        assert extracted_experimenter == expected_experimenter

    def test_subject_metadata(self):

        subject_metadata = self.interface.extract_subject_metadata()

        extracted_subject_id = subject_metadata["subject_id"]
        expected_subject_id = ""
        assert extracted_subject_id == expected_subject_id

        extracted_subject_date_of_birth = subject_metadata["date_of_birth"]
        expected_subject_date_of_birth = ""
        assert extracted_subject_date_of_birth == expected_subject_date_of_birth


if __name__ == "__main__":
    unittest.main()
