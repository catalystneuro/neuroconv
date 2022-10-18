import datetime

from neuroconv.datainterfaces.ecephys.neuralynx.neuralynxdatainterface import (
    NeuralynxRecordingInterface,
)

from ..setup_paths import ECEPHY_DATA_PATH

NLX_PATH = ECEPHY_DATA_PATH / "neuralynx"

def test_neuralynx_cheetah_v574_metadata():
    import neo
    import distutils.version as version

    folder_path = NLX_PATH / "Cheetah_v5.7.4" / "original_data"
    metadata = NeuralynxRecordingInterface(folder_path).get_metadata()
    file_metadata = metadata["NWBFile"]

    assert file_metadata["session_start_time"] == datetime.datetime(2017, 2, 16, 17, 56, 4)
    # the session id can only be extracted from the file headers exposed for neo > 0.11.0
    if version.LooseVersion(neo.__version__) > version.LooseVersion("0.11.0"):
        assert file_metadata["session_id"] == "d8ba8eef-8d11-4cdc-86dc-05f50d4ba13d"

    # Metadata extracted directly from file header (neo >= 0.11)
    assert '"FileType": "NCS"' in file_metadata["notes"]
    assert '"recording_closed": "2017-02-16 18:01:18"' in file_metadata["notes"]
    assert '"ADMaxValue": "32767"' in file_metadata["notes"]
    # the sampling rate and device is part of the file headers exposed for neo > 0.11.0
    if version.LooseVersion(neo.__version__) > version.LooseVersion("0.11.0"):
        assert '"sampling_rate": "32000.0"' in file_metadata["notes"]

        device_metadata = metadata["Ecephys"]["Device"]
        assert device_metadata[-1] == {"name": "AcqSystem1 DigitalLynxSX", "description": "Cheetah 5.7.4"}

def test_neuralynx_cheetah_v574_metadata():
    import neo
    import distutils.version as version

    folder_path = NLX_PATH / "Cheetah_v5.7.4" / "original_data"
    metadata = NeuralynxRecordingInterface(folder_path).get_metadata()
    file_metadata = metadata["NWBFile"]

    assert file_metadata["session_start_time"] == datetime.datetime(2017, 2, 16, 17, 56, 4)
    # the session id is only exposed on neo dev as of now. TODO: Remove if after neo >=0.12
    if version.LooseVersion(neo.__version__) > version.LooseVersion("0.11.0"):
        assert file_metadata["session_id"] == "d8ba8eef-8d11-4cdc-86dc-05f50d4ba13d"

    # Metadata extracted directly from file header (neo >= 0.11)
    assert '"FileType": "NCS"' in file_metadata["notes"]
    assert '"recording_closed": "2017-02-16 18:01:18"' in file_metadata["notes"]
    assert '"ADMaxValue": "32767"' in file_metadata["notes"]
    # the sampling rate and device is only exposed on neo dev as of now. TODO: Remove if after neo >=0.12
    if version.LooseVersion(neo.__version__) > version.LooseVersion("0.11.0"):
        assert '"sampling_rate": "32000.0"' in file_metadata["notes"]

        device_metadata = metadata["Ecephys"]["Device"]
        assert device_metadata[-1] == {"name": "AcqSystem1 DigitalLynxSX", "description": "Cheetah 5.7.4"}


def test_neuralynx_cheetah_v563_metadata():
    import neo
    import distutils.version as version

    folder_path = NLX_PATH / "Cheetah_v5.6.3" / "original_data"
    metadata = NeuralynxRecordingInterface(folder_path).get_metadata()
    file_metadata = metadata["NWBFile"]

    assert file_metadata["session_start_time"] == datetime.datetime(2016, 11, 28, 21, 50, 33, 322000)

    # Metadata extracted directly from file header (neo >= 0.11)
    assert '"FileType": "CSC"' in file_metadata["notes"]
    assert '"recording_closed": "2016-11-28 22:44:41.145000"' in file_metadata["notes"]
    assert '"ADMaxValue": "32767"' in file_metadata["notes"]

    # the sampling rate and device is only exposed on neo dev as of now. TODO: Remove if after neo >=0.12
    if version.LooseVersion(neo.__version__) > version.LooseVersion("0.11.0"):
        assert '"sampling_rate": "2000.0"' in file_metadata["notes"]

        device_metadata = metadata["Ecephys"]["Device"]
        assert device_metadata[-1] == {"name": "DigitalLynxSX", "description": "Cheetah 5.6.3"}


def test_neuralynx_cheetah_v540_metadata():
    import neo
    import distutils.version as version

    folder_path = NLX_PATH / "Cheetah_v5.4.0" / "original_data"
    metadata = NeuralynxRecordingInterface(folder_path).get_metadata()
    file_metadata = metadata["NWBFile"]

    assert file_metadata["session_start_time"] == datetime.datetime(2001, 1, 1, 0, 0)

    assert '"recording_closed": "2001-01-01 00:00:00"' in file_metadata["notes"]
    assert '"ADMaxValue": "32767"' in file_metadata["notes"]

    # the sampling rate and device is only exposed on neo dev as of now. TODO: Remove if after neo >=0.12
    if version.LooseVersion(neo.__version__) > version.LooseVersion("0.11.0"):
        assert '"sampling_rate": "1017.375"' in file_metadata["notes"]

        device_metadata = metadata["Ecephys"]["Device"]
        assert device_metadata[-1] == {"name": "DigitalLynx", "description": "Cheetah 5.4.0"}


def test_neuralynx_filtering():
    file_path = NLX_PATH / "Cheetah_v5.7.4" / "original_data"
    interface = NeuralynxRecordingInterface(file_path)
    filtering_keys = interface.recording_extractor.get_annotation("filtering_properties")

    expected_single_channel_props = {"DSPLowCutFilterEnabled": "True",
                      "DspLowCutFrequency": "10",
                      "DspLowCutNumTaps": "0",
                      "DspLowCutFilterType": "DCO",
                      "DSPHighCutFilterEnabled": "True",
                      "DspHighCutFrequency": "9000",
                      "DspHighCutNumTaps": "64",
                      "DspHighCutFilterType": "FIR",
                      "DspDelayCompensation": "Enabled",
                      # don't check for filter delay as the unit might be differently parsed
                      # "DspFilterDelay_µs": "984"
                      }

    extracted_props = {k: interface.recording_extractor.get_property(k) for k in filtering_keys}

    n_channels = interface.recording_extractor.get_num_channels()
    # check consistency of number of entries
    assert all([len(v) == n_channels for v in extracted_props.values()])
    # check values for first channel
    for key, exp_value in expected_single_channel_props.items():
        assert exp_value == extracted_props[key][0]

