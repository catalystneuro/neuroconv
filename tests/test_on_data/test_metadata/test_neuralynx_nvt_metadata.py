import datetime

from neuroconv.datainterfaces.behavior.neuralynx.nvt_utils import read_header

from ..setup_paths import BEHAVIOR_DATA_PATH


def test_read_header():
    filepath = str(BEHAVIOR_DATA_PATH / "neuralynx" / "test.nvt")
    header = read_header(filepath)

    assert header == {
        "OriginalFileName": "C:\\Users\\jstout\\Desktop\\Data 2 Move\\21-48\\2023-05-15_10-35-15\\VT1.nvt",
        "TimeCreated": datetime.datetime(2023, 5, 15, 10, 35, 29),
        "TimeClosed": datetime.datetime(2023, 5, 15, 10, 52, 24),
        "FileType": "Video",
        "FileVersion": "3.3.0",
        "RecordSize": 1828,
        "CheetahRev": "6.4.1 Development",
        "AcqEntName": "VT1",
        "VideoFormat": "NTSC",
        "IntensityThreshold": [1, 135],
        "RedThreshold": [1, 100],
        "GreenThreshold": [1, 100],
        "BlueThreshold": [0, 200],
        "Saturation": -1,
        "Hue": -1,
        "Brightness": -1,
        "Contrast": -1,
        "Sharpness": -1,
        "DirectionOffset": 0,
        "Resolution": [720, 480],
        "CameraDelay": 0,
        "EnableFieldEstimation": False,
        "SamplingFrequency": 29.97,
    }
