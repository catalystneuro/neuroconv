from neuroconv.datainterfaces import SpikeGLXRecordingInterface


def test_keywords():
    assert SpikeGLXRecordingInterface.keywords == [
        "extracellular electrophysiology",
        "voltage",
        "recording",
        "Neuropixels",
    ]
