import datetime

from neuroconv.datainterfaces.ecephys.neuroscope.neuroscope_utils import get_session_start_time
from neuroconv.datainterfaces.ecephys.neuroscope.neuroscopedatainterface import NeuroscopeSortingInterface

from ..setup_paths import ECEPHY_DATA_PATH

NEUROSCOPE_PATH = ECEPHY_DATA_PATH / "neuroscope"


def test_neuroscope_session_start_time():
    xml_file_path = str(NEUROSCOPE_PATH / "dataset_1" / "YutaMouse42-151117.xml")

    assert get_session_start_time(xml_file_path) == datetime.datetime(2015, 8, 31, 0, 0)


def test_get_metadata():

    sx = NeuroscopeSortingInterface(
        str(NEUROSCOPE_PATH / "dataset_1"),
        xml_file_path=str(NEUROSCOPE_PATH / "dataset_1" / "YutaMouse42-151117.xml"),
    )

    assert sx.get_metadata()["NWBFile"]["session_start_time"] == datetime.datetime(2015, 8, 31, 0, 0)
