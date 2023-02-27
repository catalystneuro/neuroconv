from datetime import datetime

from neuroconv.datainterfaces import PlexonSortingInterface
from ..setup_paths import ECEPHY_DATA_PATH

PLEXON_PATH = ECEPHY_DATA_PATH / "plexon"


def test_plexon_metadata():
    plexon_filepath = PLEXON_PATH / "File_plexon_2.plx"

    plexon_interface = PlexonSortingInterface(file_path=plexon_filepath)
    metadata = plexon_interface.get_metadata()

    # Test session start time
    session_start_time = metadata["NWBFile"]["session_start_time"]

    expected_datetime = datetime(2000, 10, 30, 15, 56, 56)
    assert session_start_time == expected_datetime
