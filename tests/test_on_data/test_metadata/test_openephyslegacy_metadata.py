from datetime import datetime

from neuroconv.datainterfaces.ecephys.openephys.openephyslegacydatainterface import OpenEphysLegacyRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH

OPENEPHYS_PATH = ECEPHY_DATA_PATH / "openephys"


def test_openephyslegacy_metadata():
    openephys_folder_path = OPENEPHYS_PATH / "OpenEphys_SampleData_1"

    openephys_interface = OpenEphysLegacyRecordingInterface(folder_path=openephys_folder_path)
    metadata = openephys_interface.get_metadata()

    # Test session start time
    session_start_time = metadata["NWBFile"]["session_start_time"]

    expected_datetime = datetime(2018, 10, 3, 13, 16, 50)
    assert session_start_time == expected_datetime
