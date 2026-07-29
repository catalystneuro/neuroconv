"""Tests for the saved_files_are_split flag shared by the Intan interfaces."""

from datetime import datetime

import pytest
from pynwb import read_nwb

from neuroconv.datainterfaces import (
    IntanAnalogInterface,
    IntanRecordingInterface,
    IntanStimInterface,
)

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


SPLIT_FOLDER = ECEPHY_DATA_PATH / "intan" / "test_tetrode_240502_162925"


class TestIntanRecordingInterfaceSplit:
    """The test_tetrode fixture contains four rotated .rhd files (amplifier-only)."""

    def test_single_file_ignores_siblings(self):
        """saved_files_are_split=False reads only the file it was pointed at."""
        first_file = sorted(SPLIT_FOLDER.glob("*.rhd"))[0]
        with pytest.warns(UserWarning, match="saved_files_are_split=True"):
            interface = IntanRecordingInterface(file_path=first_file)
        assert interface.recording_extractor.get_num_samples() == 1_800_064

    def test_no_warning_when_flag_set(self):
        """Passing saved_files_are_split=True suppresses the sibling warning."""
        first_file = sorted(SPLIT_FOLDER.glob("*.rhd"))[0]
        import warnings

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            IntanRecordingInterface(file_path=first_file, saved_files_are_split=True)
            split_warnings = [w for w in captured if "saved_files_are_split" in str(w.message)]
            assert split_warnings == []

    def test_conversion_writes_concatenated_data(self, tmp_path):
        """Full NWB conversion preserves the total sample count."""
        first_file = sorted(SPLIT_FOLDER.glob("*.rhd"))[0]
        interface = IntanRecordingInterface(file_path=first_file, saved_files_are_split=True)

        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        nwbfile_path = tmp_path / "split.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)
        series = nwbfile.acquisition["ElectricalSeries"]
        # Data set has three full chunks of 1_800_064 samples plus a shorter tail of 45_184 samples.
        assert series.data.shape[0] == 1_800_064 * 3 + 45_184


def test_analog_interface_accepts_flag():
    """Smoke test that IntanAnalogInterface exposes the parameter."""
    import inspect

    params = inspect.signature(IntanAnalogInterface.__init__).parameters
    assert "saved_files_are_split" in params
    assert params["saved_files_are_split"].default is False


def test_stim_interface_accepts_flag():
    """Smoke test that IntanStimInterface exposes the parameter."""
    import inspect

    params = inspect.signature(IntanStimInterface.__init__).parameters
    assert "saved_files_are_split" in params
    assert params["saved_files_are_split"].default is False
