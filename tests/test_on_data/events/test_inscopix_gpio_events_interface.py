from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import InscopixGpioEventsInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH


class TestInscopixGpioOdorConcentrationStimulus:
    """InscopixGpioEventsInterface derives events from the channels of an Inscopix ``.gpio`` file.

    ``odor_concentration_stimulus.gpio`` is a four-level odor-concentration code on ``GPIO-2``
    (amplitudes 128/144/160/224, 164 change points) recorded beside ``BNC Sync Output``, a 0/1 frame
    clock with 9 rising edges. The conditioning grammar these specs are written in is exercised against
    a mock in ``tests/test_minimal/test_signal_encoded_events.py``; what is checked here is that this
    recording is read and written correctly.
    """

    FILE_PATH = str(OPHYS_DATA_PATH / "analog_datasets" / "inscopix" / "gpio" / "odor_concentration_stimulus.gpio")

    # ``BNC Sync Output`` is a 0/1 line, so its cut is the derived midpoint. ``GPIO-2`` is cut at the
    # lowest odor boundary, which reads the span above it.
    DETECTION_CONFIGURATION = {
        "BNC Sync Output": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}],
        "GPIO-2": [{"signal_conditioning": {"binarize": 136}, "detection": "high_period"}],
    }

    @pytest.fixture
    def interface(self):
        return InscopixGpioEventsInterface(
            file_path=self.FILE_PATH, detection_configuration=self.DETECTION_CONFIGURATION
        )

    def test_requires_detection_configuration(self):
        # Selection is explicit: the file records no analog-versus-digital flag, so there is no lossless
        # default to derive and the configuration is a required keyword.
        with pytest.raises(ValidationError, match="detection_configuration"):
            InscopixGpioEventsInterface(file_path=self.FILE_PATH)

    def test_get_available_channels(self):
        inventory = InscopixGpioEventsInterface.get_available_channels(self.FILE_PATH)
        by_name = {entry["name"]: entry for entry in inventory}
        assert by_name["BNC Sync Output"]["unique_values"] == [0.0, 1.0]  # a 0/1 line
        assert by_name["GPIO-2"]["unique_values"] == [128.0, 144.0, 160.0, 224.0]  # four levels, one cut each

    def test_session_start_time(self, interface):
        session_start_time = interface.get_metadata()["NWBFile"]["session_start_time"]
        assert session_start_time == datetime(2025, 2, 27, 11, 25, 28, 935000, tzinfo=timezone.utc)

    def test_metadata_seeds_event_types(self, interface):
        event_types = interface.get_metadata()["Events"]["inscopix_gpio_events"]["event_types"]
        assert set(event_types) == {"BNC Sync Output", "GPIO-2"}
        # The channel name carries a space and a hyphen, neither of which survives as an NWB object name.
        assert event_types["BNC Sync Output"]["event_name"] == "bnc_sync_output"
        assert event_types["GPIO-2"]["event_name"] == "gpio_2"
        # No event type seeds a value column: nothing on the signal-encoded path carries a payload.
        assert all("columns" not in entry for entry in event_types.values())

    def test_metadata_key_default_and_override(self):
        interface = InscopixGpioEventsInterface(
            file_path=self.FILE_PATH, detection_configuration=self.DETECTION_CONFIGURATION
        )
        assert set(interface.get_metadata()["Events"]) == {"inscopix_gpio_events"}
        interface = InscopixGpioEventsInterface(
            file_path=self.FILE_PATH,
            detection_configuration=self.DETECTION_CONFIGURATION,
            metadata_key="odor_session",
        )
        assert set(interface.get_metadata()["Events"]) == {"odor_session"}

    def test_selection_by_inclusion(self, interface):
        # Only the two configured channels are written; the other 24 channels never appear.
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        assert set(nwbfile.events) == {"BncSyncOutput", "Gpio2"}

    def test_unknown_channel_raises_at_construction(self):
        # The channel inventory is known at construction, so naming a channel the file does not have fails
        # there rather than at read time.
        with pytest.raises(ValueError, match="not one of the file's signals"):
            InscopixGpioEventsInterface(
                file_path=self.FILE_PATH, detection_configuration={"NotAChannel": [{"detection": "rising"}]}
            )

    def test_round_trip(self, interface, tmp_path):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        nwbfile_path = tmp_path / "test_inscopix_gpio_events.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()
            assert len(read_nwbfile.get_events_table("Gpio2")) == 164
            assert len(read_nwbfile.get_events_table("BncSyncOutput")) == 9
