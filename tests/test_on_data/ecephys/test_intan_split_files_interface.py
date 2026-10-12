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
    SAMPLING_FREQUENCY = 30_000.0

    def test_split_read_joins_the_chunks_in_filename_order(self):
        """Every chunk's pulses are there, on one clock that keeps running across the joins.

        The chunk a pulse came from is not recoverable from the result, which is the point: the four
        pulses of the second chunk sit at 6548 onwards rather than back at 532, so the times are the
        session's rather than an offset into whichever file happens to hold them.
        """
        # The camera's rising edges over the whole session, read off the fixture, as sample indices of
        # the concatenated recording (the joins sit at 6016, 12032 and 18048, since all four chunks are
        # 6016 samples long). Hardcoded rather than assembled from per-chunk reads, which would only
        # compare the reader against itself.
        edges = (539, 2041, 3543, 5046, 6548, 8050, 9553, 11055, 12558, 14060, 15562, 17065, 18567, 20069, 21572, 23075)
        # The joined read declares the lines the header does, the two enabled but idle ones included,
        # since the inventory comes off the concatenated extractor rather than off the file the
        # interface was pointed at.
        expected_events_per_line = {"DIGITAL-IN-12": 0, "DIGITAL-IN-13": 0, "DIGITAL-IN-14": len(edges)}

        first_file = sorted(DIGITAL_SPLIT_FOLDER.glob("*.rhd"))[0]
        interface = IntanDigitalInterface(file_path=first_file, saved_files_are_split=True)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        timestamps = np.asarray(nwbfile.events[self.LINE]["timestamp"][:])

        assert {name: len(table) for name, table in nwbfile.events.items()} == expected_events_per_line
        expected_timestamps = np.array(edges) / self.SAMPLING_FREQUENCY
        np.testing.assert_allclose(timestamps, expected_timestamps)

    def test_a_low_period_spanning_a_join_reads_as_one_event(self):
        """An event that opens in one chunk and closes in the next comes out whole.

        The camera line idles low between frames, so reading it as a low period puts an event across
        every join, which the high pulses themselves do not do: each of them is over well before the
        file it is in ends. Read one chunk on its own and the low period it ends on has no rising edge
        left to close it, so the duration is NaN; the durations asserted here are the ones the whole
        session gives, and they are only available if the chunks were joined before edge detection.
        """
        # Onset -> duration, in samples, for the three low periods that span a join: the line goes low
        # at 5947 and does not come back up until 6548, which is past the boundary at 6016, and
        # likewise at the other two.
        low_periods_spanning_a_join = {5947: 601, 11956: 602, 17966: 601}
        # Every line the header declares, read the same way: the camera's sixteen gaps between frames,
        # and nothing at all from the two that stay low the whole session, since a flat line has no
        # falling edge to open a low period on.
        expected_events_per_line = {"DIGITAL-IN-12": 0, "DIGITAL-IN-13": 0, "DIGITAL-IN-14": 16}

        first_file = sorted(DIGITAL_SPLIT_FOLDER.glob("*.rhd"))[0]
        interface = IntanDigitalInterface(
            file_path=first_file,
            saved_files_are_split=True,
            detection_configuration={
                line: [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "low_period"}]
                for line in expected_events_per_line
            },
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        table = nwbfile.events[self.LINE]
        timestamps = np.asarray(table["timestamp"][:])
        durations = np.asarray(table["duration"][:])

        assert {name: len(events_table) for name, events_table in nwbfile.events.items()} == expected_events_per_line
        onsets_in_samples = np.round(timestamps * self.SAMPLING_FREQUENCY).astype(int)
        durations_in_samples = durations * self.SAMPLING_FREQUENCY
        spanning_a_join = {
            int(onset): round(float(duration))
            for onset, duration in zip(onsets_in_samples, durations_in_samples)
            if int(onset) in low_periods_spanning_a_join
        }
        assert spanning_a_join == low_periods_spanning_a_join


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
