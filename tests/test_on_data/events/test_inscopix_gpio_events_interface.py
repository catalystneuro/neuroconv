import platform
import sys
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import InscopixGpioEventsInterface
from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH


# `isx`, which reads the file, resolves on neither of these, so the tests below have nothing to read.
# Mirrors the guards on the other Inscopix classes in `test_imaging_interfaces.py` and
# `test_segmentation_interfaces.py`, and the equivalent skip the gallery conftest applies to the page.
skip_on_darwin_arm64 = pytest.mark.skipif(
    platform.system() == "Darwin" and platform.machine() == "arm64",
    reason="The isx package is currently not natively supported on macOS with Apple Silicon. "
    "Installation instructions can be found at: "
    "https://github.com/inscopix/pyisx?tab=readme-ov-file#install",
)
skip_on_python_313 = pytest.mark.skipif(
    sys.version_info >= (3, 13),
    reason="Tests are skipped on Python 3.13 because of incompatibility with the 'isx' module "
    "Requires: Python <3.13, >=3.9)"
    "See:https://github.com/inscopix/pyisx/issues",
)


@skip_on_darwin_arm64
@skip_on_python_313
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

    def test_get_metadata(self):
        interface = InscopixGpioEventsInterface(
            file_path=self.FILE_PATH, detection_configuration=self.DETECTION_CONFIGURATION
        )

        metadata = interface.get_metadata()

        assert metadata["NWBFile"]["session_start_time"] == datetime(
            2025, 2, 27, 11, 25, 28, 935000, tzinfo=timezone.utc
        )

        event_types = metadata["Events"]["inscopix_gpio_events"]["event_types"]
        assert set(event_types) == {"BNC Sync Output", "GPIO-2"}
        # The channel name carries a space and a hyphen, neither of which survives as an NWB object name.
        assert event_types["BNC Sync Output"]["event_name"] == "bnc_sync_output"
        assert event_types["GPIO-2"]["event_name"] == "gpio_2"
        # No event type seeds a value column: nothing on the signal-encoded path carries a payload.
        assert all("columns" not in entry for entry in event_types.values())

    def test_metadata_key_overrides_the_block_name(self):
        interface = InscopixGpioEventsInterface(
            file_path=self.FILE_PATH,
            detection_configuration=self.DETECTION_CONFIGURATION,
            metadata_key="odor_session",
        )

        assert set(interface.get_metadata()["Events"]) == {"odor_session"}

    def test_add_to_nwbfile(self, tmp_path):
        """Only the two configured channels are written; the other 24 never appear."""
        interface = InscopixGpioEventsInterface(
            file_path=self.FILE_PATH, detection_configuration=self.DETECTION_CONFIGURATION
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        nwbfile_path = tmp_path / "test_inscopix_gpio_events.nwb"
        configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")
        read_nwbfile = read_nwb(path=nwbfile_path)

        assert set(read_nwbfile.events) == {"BncSyncOutput", "Gpio2"}
        # The frame clock is read at its rising edges, the odor code across its change points.
        assert len(read_nwbfile.get_events_table("BncSyncOutput")) == 9
        assert len(read_nwbfile.get_events_table("Gpio2")) == 164

    def test_unknown_channel_raises_at_construction(self):
        # The channel inventory is known at construction, so naming a channel the file does not have fails
        # there rather than at read time.
        with pytest.raises(ValueError, match="not one of the file's signals"):
            InscopixGpioEventsInterface(
                file_path=self.FILE_PATH, detection_configuration={"NotAChannel": [{"detection": "rising"}]}
            )
