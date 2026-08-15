"""Tests for the saved_files_are_split flag shared by the Intan interfaces."""

from datetime import datetime

import numpy as np
import pytest
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import (
    IntanAnalogInterface,
    IntanDigitalInterface,
    IntanRecordingInterface,
    IntanStimInterface,
)

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


SPLIT_FOLDER = ECEPHY_DATA_PATH / "intan" / "test_tetrode_240502_162925"
DIGITAL_SPLIT_FOLDER = ECEPHY_DATA_PATH / "intan" / "time_split_with_digital_stream"


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


class TestIntanDigitalInterfaceSplit:
    """The only fixture carrying both a rotated session and a digital line.

    Four rotated .rhd chunks of 6016 samples at 30 kHz, cut out of one contiguous run, with a camera
    frame sync on DIGITAL-IN-14 that puts four pulses in every chunk. DIGITAL-IN-12 and DIGITAL-IN-13
    were enabled but stay idle. The other split fixture (test_tetrode) is amplifier-only, which is why
    the digital interface's concatenation path could not be tested before this one existed.
    """

    LINE = "DIGITAL-IN-14"
    CHUNK_DURATION = 6016 / 30_000.0  # seconds per rotated chunk, all four are the same length
    SAMPLING_FREQUENCY = 30_000.0

    @staticmethod
    def _read_line(interface, line):
        """Return (timestamps, durations) for one line, through the public write path."""
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        table = nwbfile.events[line]
        return np.asarray(table["timestamp"][:]), np.asarray(table["duration"][:])

    def test_single_file_read_stops_at_the_chunk_boundary(self):
        """Without the flag the interface sees one chunk: the four pulses of the file it was given."""
        first_file = sorted(DIGITAL_SPLIT_FOLDER.glob("*.rhd"))[0]
        interface = IntanDigitalInterface(file_path=first_file)
        timestamps, _ = self._read_line(interface, self.LINE)

        assert len(timestamps) == 4

    def test_split_read_joins_the_chunks_in_filename_order(self):
        """With the flag every chunk's pulses are there, each one shifted by the chunks ahead of it.

        Asserted against the per-chunk reads rather than against hardcoded times, because the claim is
        exactly that: the joined read is the four separate reads laid end to end, in filename order,
        on one clock that keeps running across the joins.
        """
        files = sorted(DIGITAL_SPLIT_FOLDER.glob("*.rhd"))
        expected_timestamps = np.concatenate(
            [
                self._read_line(IntanDigitalInterface(file_path=file), self.LINE)[0] + chunk_index * self.CHUNK_DURATION
                for chunk_index, file in enumerate(files)
            ]
        )

        interface = IntanDigitalInterface(file_path=files[0], saved_files_are_split=True)
        timestamps, durations = self._read_line(interface, self.LINE)

        assert len(timestamps) == 16  # four pulses in each of the four chunks
        np.testing.assert_allclose(timestamps, expected_timestamps)
        # Every pulse ends inside the recording, so none is left with the NaN duration of an
        # unterminated high.
        assert not np.isnan(durations).any()

    def test_pulse_train_is_unbroken_across_the_joins(self):
        """The frame period across a join is the same as inside a chunk, so no sample is lost or
        repeated at a boundary.

        This is what makes a pulse that rises in one chunk and falls in the next read as the single
        pulse it is: the camera runs at a fixed rate the whole time, and a join that dropped or
        duplicated even one sample would show up as a period no chunk contains. 1502 and 1503 samples
        are the two the camera alternates between, since its rate does not land on a whole sample of
        the 30 kHz clock; the joins sit at indices 3, 7 and 11 and carry the same pair.
        """
        first_file = sorted(DIGITAL_SPLIT_FOLDER.glob("*.rhd"))[0]
        interface = IntanDigitalInterface(file_path=first_file, saved_files_are_split=True)
        timestamps, _ = self._read_line(interface, self.LINE)

        periods_in_samples = np.round(np.diff(timestamps) * self.SAMPLING_FREQUENCY).astype(int)
        assert len(periods_in_samples) == 15  # the sixteen pulses of the joined read
        assert sorted(set(periods_in_samples)) == [1502, 1503]

    def test_joined_read_exposes_the_same_lines(self):
        """The joined read declares the three lines the header does, the two idle ones included.

        The inventory is taken off the concatenated extractor rather than off the file the interface
        was pointed at, so this is where a join that changed the channel set would show. An idle line
        stays an empty table, as it is on an unsplit session.
        """
        first_file = sorted(DIGITAL_SPLIT_FOLDER.glob("*.rhd"))[0]
        interface = IntanDigitalInterface(file_path=first_file, saved_files_are_split=True)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        assert {name: len(table) for name, table in nwbfile.events.items()} == {
            "DIGITAL-IN-12": 0,
            "DIGITAL-IN-13": 0,
            "DIGITAL-IN-14": 16,
        }


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
