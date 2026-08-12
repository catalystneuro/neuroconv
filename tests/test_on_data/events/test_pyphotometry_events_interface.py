"""On-data tests for the pyPhotometry events interface.

A ``.ppd`` file has no digital stream of its own: each of the board's digital lines rides in the low bit
of the words of the analog input it shares a slot with, so a line is a sampled ``0``/``1`` signal on that
input's clock. What varies between recordings, for events, is the shape of the pulses and the state of
the lines where the file begins and ends, so the fixtures under ``events_datasets/pyphotometry`` are one
window per shape and this module is organized to match, one round-trip class per window:

- ``narrow_pulses_and_idle_line`` -- the ordinary case, a train of one-to-two-sample pulses on one line,
  and beside it a line that was recorded and never fired.
- ``starts_and_ends_high`` -- a window entered and left mid-pulse, so its first pulse has no onset in the
  file and its last has no end.
- ``wide_pulses_on_both_lines`` -- pulses several samples wide, on two lines that both fire.

Each class states the frames its edges fall on, counted in the low bits of the words by hand, and turns
them into seconds with the rate the header states. Nothing is read back through the interface, which
would make the assertions circular.

A last class holds what no window shows: the readings other than the default, and the stagger between two
lines, which needs both of them to fire on the same frame and so is asserted against a file written here.
"""

import json
from datetime import datetime

import numpy as np
import pytest
from numpy.testing import assert_allclose
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import PyPhotometryEventsInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH

PYPHOTOMETRY_EVENTS_PATH = OPHYS_DATA_PATH / "events_datasets" / "pyphotometry"

#: The rate every one of these windows was recorded at, and so the rate of every line in them.
RATE_IN_HZ = 130.0

#: Line n shares its slot with analog input n, and the timer reaches that slot one tick of
#: (rate * number of inputs) into each cycle. Both windows' recordings have two inputs.
STARTING_TIME_IN_SECONDS = {"digital_1": 0.0, "digital_2": 1 / (2 * RATE_IN_HZ)}


def onsets_of(signal_source_id: str, rising_frames) -> np.ndarray:
    """The times of the given rising frames on the given line, from the rate the header states."""
    return STARTING_TIME_IN_SECONDS[signal_source_id] + np.asarray(rising_frames) / RATE_IN_HZ


def widths_of(sample_counts) -> np.ndarray:
    """The durations, in seconds, of high periods that many samples wide."""
    return np.asarray(sample_counts) / RATE_IN_HZ


class PyPhotometryEventsRoundTrip(DataInterfaceTestMixin):
    """What every window shares: how it is built, and what its metadata says.

    Which events each window carries is its own claim and lives in its ``check_read_nwb``, since the whole
    point of having three of them is that their lines are shaped differently.
    """

    data_interface_cls = PyPhotometryEventsInterface
    conversion_options = dict()  # the events interfaces take none: what is written is set at construction
    save_directory = OUTPUT_PATH

    #: The header's ``date_time``, which is the recording's start and not the window's.
    expected_session_start_time: datetime

    def check_extracted_metadata(self, metadata: dict):
        """Both lines are seeded as event types, named as pyPhotometry's own reader names them.

        A line that never fires is seeded too: which event types exist is a property of the configuration,
        not of whether a line happened to fire, so this costs no data read.
        """
        expected_events_metadata = {
            "pyphotometry_events": {
                "event_types": {
                    "digital_1": {"event_name": "digital_1"},
                    "digital_2": {"event_name": "digital_2"},
                },
            },
        }
        assert metadata["Events"] == expected_events_metadata

        # Unlike most events formats, a .ppd records when the session started.
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time


class TestPyPhotometryNarrowPulsesAndIdleLine(PyPhotometryEventsRoundTrip):
    """The ordinary case: a train of narrow pulses on one line, beside a line that never fires.

    The window is the first five seconds of the recording, so the train is seen starting from a line that
    was low, and it ends on a low sample, which leaves every high period closed.
    """

    file_path = PYPHOTOMETRY_EVENTS_PATH / "narrow_pulses_and_idle_line.ppd"
    interface_kwargs = dict(file_path=file_path)

    expected_session_start_time = datetime(2021, 6, 8, 16, 52, 48)
    #: Every rising edge of digital_1 in the window; the first five are the ones checked in full below.
    expected_pulse_count = 37
    expected_first_rising_frames = [488, 493, 497, 501, 506]
    #: Each of those pulses stays high for one or two samples, aliasing a source at about 30 Hz.
    expected_first_pulse_widths = [2, 1, 1, 2, 1]

    def check_read_nwb(self, nwbfile_path: str):
        """The default reading is high_period: an onset at each rising edge, closed by the falling one."""
        nwbfile = read_nwb(nwbfile_path)

        # Each event_name CamelCases into its table's NWB object name.
        pulses = nwbfile.get_events_table("Digital1")
        assert pulses.colnames == ("timestamp", "duration")
        assert len(pulses) == self.expected_pulse_count
        assert_allclose(pulses["timestamp"][:5], onsets_of("digital_1", self.expected_first_rising_frames))
        assert_allclose(pulses["duration"][:5], widths_of(self.expected_first_pulse_widths))

        # The window ends on a low sample, so no high period in it is left open.
        assert not np.isnan(np.asarray(pulses["duration"][:])).any()

        # A line that never toggled is still an event type: it was recorded, nothing fired. hdmf only
        # materializes the optional duration column once a row supplies one, so a zero-row table has none.
        idle = nwbfile.get_events_table("Digital2")
        assert len(idle) == 0
        assert idle.colnames == ("timestamp",)

        nwbfile.read_io.close()


class TestPyPhotometryStartsAndEndsHigh(PyPhotometryEventsRoundTrip):
    """A window entered and left mid-pulse, which is where the two boundary cases live.

    The first sample is already high, so the falling edge that opens the file belongs to a pulse whose
    onset is not in it: that pulse contributes no event rather than one invented at time zero. The last
    sample is high too, so the final high period never closes and its duration is NaN rather than a length
    running to the end of the file, which is the shape of a closed bug in Doric's reader.
    """

    file_path = PYPHOTOMETRY_EVENTS_PATH / "starts_and_ends_high.ppd"
    interface_kwargs = dict(file_path=file_path)

    expected_session_start_time = datetime(2021, 6, 8, 16, 52, 48)
    #: 33 rising edges: the pulse the window opens inside contributes none, since its onset is outside.
    expected_pulse_count = 33
    #: The window's first falling edge is at frame 1 and its first rising edge at frame 4, so the first
    #: event is the pulse at frame 4 and not the one the file opens in the middle of.
    expected_first_rising_frames = [4, 8, 12, 17]
    expected_first_pulse_widths = [1, 1, 2, 1]
    #: The last sample is frame 142 and it is high, so that rising edge is an onset with no falling edge.
    expected_last_rising_frames = [138, 142]

    def check_read_nwb(self, nwbfile_path: str):
        """Assert the two boundary pulses, which is what this window exists for."""
        nwbfile = read_nwb(nwbfile_path)
        pulses = nwbfile.get_events_table("Digital1")

        assert len(pulses) == self.expected_pulse_count
        timestamps = np.asarray(pulses["timestamp"][:])
        durations = np.asarray(pulses["duration"][:])

        assert_allclose(timestamps[:4], onsets_of("digital_1", self.expected_first_rising_frames))
        assert_allclose(durations[:4], widths_of(self.expected_first_pulse_widths))

        # The pulse the window closes inside keeps its onset and reports an unknown duration.
        assert_allclose(timestamps[-2:], onsets_of("digital_1", self.expected_last_rising_frames))
        assert np.isnan(durations[-1])
        assert not np.isnan(durations[:-1]).any()

        assert len(nwbfile.get_events_table("Digital2")) == 0
        nwbfile.read_io.close()


class TestPyPhotometryWidePulsesOnBothLines(PyPhotometryEventsRoundTrip):
    """Two lines both firing, with pulses wide enough to span several samples.

    This is also the window that shows the stagger on real data: ``digital_2``'s onsets carry the tick of
    the 260 Hz sampling timer that separates it from ``digital_1``, which every other reader reports as
    zero. Every edge of the window falls on a low sample of both lines, so nothing here is truncated.
    """

    file_path = PYPHOTOMETRY_EVENTS_PATH / "wide_pulses_on_both_lines.ppd"
    interface_kwargs = dict(file_path=file_path)

    expected_session_start_time = datetime(2019, 5, 6, 12, 17)
    expected_rising_frames = {"digital_1": [20, 885], "digital_2": [403, 568]}
    expected_pulse_widths = {"digital_1": [8, 8], "digital_2": [6, 6]}

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)

        for signal_source_id, table_name in (("digital_1", "Digital1"), ("digital_2", "Digital2")):
            pulses = nwbfile.get_events_table(table_name)
            assert pulses.colnames == ("timestamp", "duration")
            assert_allclose(
                pulses["timestamp"][:],
                onsets_of(signal_source_id, self.expected_rising_frames[signal_source_id]),
            )
            assert_allclose(pulses["duration"][:], widths_of(self.expected_pulse_widths[signal_source_id]))

        nwbfile.read_io.close()


def write_ppd_file(tmp_path, digital_line_1, digital_line_2):
    """Write a ``.ppd``: a two-byte header length, a JSON header, then the packed words.

    The analog samples are a constant per input, since what this file exists to carry is the digital bit
    in the low position of each word and the slot that word sits in.
    """
    header = {
        "subject_ID": "test",
        "date_time": "2025-01-01T10:00:00",
        "mode": "2EX_2EM_pulsed",
        "sampling_rate": int(RATE_IN_HZ),
        "volts_per_division": [0.00010122, 0.00010122],
        "n_analog_signals": 2,
        "n_digital_signals": 2,
        "version": "1.0",
    }
    header_bytes = json.dumps(header).encode("utf-8")

    words = np.empty(len(digital_line_1) * 2, dtype="<u2")
    words[0::2] = (1000 << 1) | np.asarray(digital_line_1, dtype="<u2")
    words[1::2] = (2000 << 1) | np.asarray(digital_line_2, dtype="<u2")

    file_path = tmp_path / "recording.ppd"
    file_path.write_bytes(len(header_bytes).to_bytes(2, "little") + header_bytes + words.tobytes())
    return file_path


class TestPyPhotometryEventsReadings:
    """Readings and selections no round trip exercises, and the timing no window can isolate."""

    file_path = PYPHOTOMETRY_EVENTS_PATH / "narrow_pulses_and_idle_line.ppd"

    def test_rising_detection_is_onset_only(self):
        """detection='rising' reads point events: onset timestamps and no duration column."""
        interface = PyPhotometryEventsInterface(
            file_path=self.file_path,
            detection_configuration={
                "digital_1": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}]
            },
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        pulses = nwbfile.get_events_table("Digital1")
        assert pulses.colnames == ("timestamp",)
        assert_allclose(pulses["timestamp"][:5], onsets_of("digital_1", [488, 493, 497, 501, 506]))

    def test_naming_one_line_reads_only_it(self):
        """Naming a line derives only that line; the idle one is not written at all."""
        interface = PyPhotometryEventsInterface(
            file_path=self.file_path,
            detection_configuration={
                "digital_1": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "high_period"}]
            },
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert set(nwbfile.events.keys()) == {"Digital1"}

    def test_naming_a_line_the_file_does_not_have_is_refused(self):
        """How many lines a file carries depends on its mode, so this is a mistake worth naming."""
        with pytest.raises(ValueError, match=r"names 'digital_3'.*\['digital_1', 'digital_2'\]"):
            PyPhotometryEventsInterface(
                file_path=self.file_path,
                detection_configuration={
                    "digital_3": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}]
                },
            )

    def test_each_line_starts_when_its_analog_input_does(self, tmp_path):
        """The second line of a strobed recording starts one tick of the sampling timer after the first.

        The words cycle through the analog inputs and the interrupt advances one input per tick, so a line
        is sampled when the input it shares a slot with is. Both lines are given a pulse on the same frame
        here, so the difference between their onsets is that tick and nothing else. No published window
        isolates it: the one that fires both lines never fires them on the same frame.
        """
        pulse_frame = 3
        line = np.zeros(8, dtype=np.uint8)
        line[pulse_frame] = 1
        file_path = write_ppd_file(tmp_path, digital_line_1=line, digital_line_2=line)

        interface = PyPhotometryEventsInterface(file_path=file_path)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        first_line_onset = nwbfile.get_events_table("Digital1")["timestamp"][0]
        second_line_onset = nwbfile.get_events_table("Digital2")["timestamp"][0]
        assert first_line_onset == pytest.approx(onsets_of("digital_1", pulse_frame))
        # Two analog inputs at 130 Hz, so the timer runs at 260 Hz and the second slot is one tick in.
        assert second_line_onset == pytest.approx(onsets_of("digital_2", pulse_frame))
