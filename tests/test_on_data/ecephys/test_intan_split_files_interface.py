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

    def test_concatenates_all_chunks(self):
        """saved_files_are_split=True pulls in every sibling file."""
        first_file = sorted(SPLIT_FOLDER.glob("*.rhd"))[0]
        interface = IntanRecordingInterface(file_path=first_file, saved_files_are_split=True)

        expected_total = 1_800_064 * 3 + 45_184  # three full chunks + shorter tail
        assert interface.recording_extractor.get_num_samples() == expected_total
        assert interface.recording_extractor.get_num_segments() == 1

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
        assert series.data.shape[0] == 1_800_064 * 3 + 45_184


# Analog and stim interfaces inherit the same dispatch; the test_tetrode fixture
# has only amplifier data, so a rotated analog/stim fixture would need to be added
# to ephy_testing_data to exercise those code paths end-to-end. For now the single-file
# paths are covered by the existing test_intan_analog_interface.py and
# test_intan_stim_interface.py tests; the split-mode dispatch is validated above on
# the amplifier interface.
#
# Related issues:
# - https://github.com/catalystneuro/neuroconv/issues/789 (parent tracking issue for
#   Intan modes/formats; mentions the rotation scenario explicitly)
# - https://github.com/catalystneuro/neuroconv/issues/519 (where the rotation case
#   was first surfaced by Szonja's comment about ConcatenateSegmentRecording)


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
