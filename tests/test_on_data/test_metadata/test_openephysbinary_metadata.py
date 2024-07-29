from datetime import datetime

from neuroconv.datainterfaces import OpenEphysBinaryRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH

OPENEPHYSBINARY_PATH = ECEPHY_DATA_PATH / "openephysbinary"


def test_openephysbinary_session_start_time():
    folder_path = OPENEPHYSBINARY_PATH / "v0.4.4.1_with_video_tracking"
    interface = OpenEphysBinaryRecordingInterface(folder_path=folder_path)
    metadata = interface.get_metadata()

    expected_session_start_time = datetime(2021, 2, 15, 17, 20, 4)

    assert metadata["NWBFile"]["session_start_time"] == expected_session_start_time
