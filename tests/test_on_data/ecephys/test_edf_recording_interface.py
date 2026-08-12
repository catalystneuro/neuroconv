import pytest

from neuroconv.datainterfaces import EDFRecordingInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

MULTI_STREAM_FILE_PATH = ECEPHY_DATA_PATH / "edf" / "heterogeneous_offsets" / "same_unit_offsets_multirate.edf"


class TestEDFStreamSelection:
    """A file whose signals were not all sampled at the same rate carries one stream per rate."""

    def test_get_stream_names(self):
        stream_names = EDFRecordingInterface.get_stream_names(file_path=MULTI_STREAM_FILE_PATH)

        assert stream_names == ["stream ((100.0,) Hz)", "stream ((1.0,) Hz)"]

    def test_stream_name_is_required_for_a_multi_stream_file(self):
        with pytest.raises(ValueError, match="several streams"):
            EDFRecordingInterface(file_path=MULTI_STREAM_FILE_PATH)

    def test_stream_name_selects_the_channels_of_its_stream(self):
        interface = EDFRecordingInterface(file_path=MULTI_STREAM_FILE_PATH, stream_name="stream ((1.0,) Hz)")

        assert list(interface.channel_ids) == ["Resp oro-nasal", "EMG submental", "Temp rectal", "Event marker"]
        assert interface.recording_extractor.get_sampling_frequency() == 1.0

    def test_channels_to_skip_applies_within_the_selected_stream(self):
        interface = EDFRecordingInterface(
            file_path=MULTI_STREAM_FILE_PATH,
            stream_name="stream ((100.0,) Hz)",
            channels_to_skip=["EOG horizontal"],
        )

        assert list(interface.channel_ids) == ["EEG Fpz-Cz", "EEG Pz-Oz"]

    def test_get_available_channel_ids_takes_a_stream_name(self):
        channel_ids = EDFRecordingInterface.get_available_channel_ids(
            file_path=MULTI_STREAM_FILE_PATH, stream_name="stream ((100.0,) Hz)"
        )

        assert channel_ids == ["EEG Fpz-Cz", "EEG Pz-Oz", "EOG horizontal"]
