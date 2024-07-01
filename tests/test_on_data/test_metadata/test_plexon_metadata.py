import datetime

import pytest

from neuroconv.datainterfaces import Plexon2RecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH


def test_session_start_time():
    file_path = f"{ECEPHY_DATA_PATH}/plexon/4chDemoPL2.pl2"
    interface = Plexon2RecordingInterface(file_path=file_path)
    metadata = interface.get_metadata()
    session_start_time = metadata["NWBFile"]["session_start_time"]

    assert session_start_time == datetime.datetime(2013, 11, 20, 15, 59, 39)
