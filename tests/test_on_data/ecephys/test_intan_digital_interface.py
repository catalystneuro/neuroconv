from datetime import datetime, timezone

import numpy as np
import pytest
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import IntanDigitalInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class TestIntanDigitalInterface:
    """
    This test a simple Intan digital file with a single enabled line
    """

    # A file whose digital-input word has a single toggling line, named "DIGITAL-IN-01" in the header
    # (bit 0 of the word: this Intan software version names its lines from one while the bit positions
    # count from zero, which is why the name is the handle and the bit is not).
    FILE_PATH = ECEPHY_DATA_PATH / "intan" / "intan_fps_test_231117_052500" / "info.rhd"

    def test_get_metadata(self):
        """get_metadata (default configuration) seeds one event_type per derived line, under the given
        metadata_key. Exact equality covers it all: the metadata_key namespace, the source id, the
        default event_name (the header's channel name), and the absence of ``columns`` (a single line has
        no value column) and ``event_description`` (an Intan file has no prose for a digital line)."""
        interface = IntanDigitalInterface(file_path=self.FILE_PATH, metadata_key="my_ttl")
        metadata = interface.get_metadata()

        # The Events block is namespaced under the given metadata_key ("my_ttl"); the fixture's one
        # line is the single event_type, named after its header channel name "DIGITAL-IN-01".
        expected_events = {"my_ttl": {"event_types": {"DIGITAL-IN-01": {"event_name": "DIGITAL-IN-01"}}}}
        assert metadata["Events"] == expected_events

    def test_available_signals_descriptor(self):
        """The inventory the validator checks a configuration against: its keys are the names the
        configuration may use, and each says which digital word the line came off. Every Intan digital
        signal is a ``"line"``, because the word arrives already demultiplexed into 0/1 traces."""
        available_signals = IntanDigitalInterface(file_path=self.FILE_PATH)._available_signals

        expected_available_signals = {
            "DIGITAL-IN-01": {
                "kind": "line",
                "stream_name": "USB board digital input channel",
                "channel_id": "DIGITAL-IN-01",
            }
        }
        assert available_signals == expected_available_signals

    def test_run_conversion(self, tmp_path):
        """Generic end-to-end default: a conversion writes the line to nwbfile.events as an EventsTable
        named from the header channel, surviving a disk roundtrip. With no configuration the default
        detection is ``high_period`` (onset at the 0->1 rise, duration to the 1->0 fall, assuming an
        active-high line), so the table is durative; the fixture's single high pulse gives the exact onset
        and span asserted below."""
        interface = IntanDigitalInterface(file_path=self.FILE_PATH)
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now(timezone.utc)  # Intan carries none

        path = tmp_path / "digital.nwb"
        interface.run_conversion(nwbfile_path=path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(path)
        tables = list(nwbfile.events.values())
        assert len(tables) == 1  # the word exposes one line -> one table
        table = tables[0]
        assert table.name == "DIGITAL-IN-01"  # named from the header channel
        assert set(table.colnames) == {
            "timestamp",
            "duration",
        }  # the default high_period is durative
        assert len(table) == 1  # one high pulse -> one event
        expected_timestamps = [0.1652]
        expected_durations = [0.5000333333333333]
        np.testing.assert_allclose(table["timestamp"][:], expected_timestamps)
        np.testing.assert_allclose(table["duration"][:], expected_durations)


class TestIntanDigitalBothWords:
    """This is a test for an Intan file carrying both digital words.

    One interface covers both, because the header names every line individually and the name alone does
    the addressing. A recorded-but-idle line is written as an empty (zero-row) table, faithful to the
    source (the line existed, nothing fired), rather than being dropped. Whether an empty table is
    undesirable for archival is a best-practice question the NWB Inspector owns, not a conversion-time
    error.
    """

    # RHS carrying a digital-input word with 9 lines and a digital-output word with 16, of which only
    # DIGITAL-IN-13/14/15 and DIGITAL-OUT-13/14/15 toggle. This is the shape the single-line fixture
    # cannot exercise.
    FILE_PATH = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
    DIGITAL_IN = "USB board digital input channel"
    DIGITAL_OUT = "USB board digital output channel"

    def test_both_words_are_covered_without_naming_a_stream(self):
        """The interface is not told which digital word to read: it reads whichever the file carries.

        The two words share the amplifier's sampling rate and timeline, and their header names cannot
        collide (DIGITAL-IN-* against DIGITAL-OUT-*), so one keyspace addresses both.

        Asserted as the whole inventory rather than by count, because the exact set is what carries the
        information. The input word's enabled lines are 01-06 and 13-15, skipping 07-12: the header names
        only the lines that were enabled at acquisition, so the inventory is that list rather than a
        contiguous range, and a count would hide it.
        """
        available_signals = IntanDigitalInterface(file_path=self.FILE_PATH)._available_signals

        expected_available_signals = {
            "DIGITAL-IN-01": {"kind": "line", "stream_name": self.DIGITAL_IN, "channel_id": "DIGITAL-IN-01"},
            "DIGITAL-IN-02": {"kind": "line", "stream_name": self.DIGITAL_IN, "channel_id": "DIGITAL-IN-02"},
            "DIGITAL-IN-03": {"kind": "line", "stream_name": self.DIGITAL_IN, "channel_id": "DIGITAL-IN-03"},
            "DIGITAL-IN-04": {"kind": "line", "stream_name": self.DIGITAL_IN, "channel_id": "DIGITAL-IN-04"},
            "DIGITAL-IN-05": {"kind": "line", "stream_name": self.DIGITAL_IN, "channel_id": "DIGITAL-IN-05"},
            "DIGITAL-IN-06": {"kind": "line", "stream_name": self.DIGITAL_IN, "channel_id": "DIGITAL-IN-06"},
            "DIGITAL-IN-13": {"kind": "line", "stream_name": self.DIGITAL_IN, "channel_id": "DIGITAL-IN-13"},
            "DIGITAL-IN-14": {"kind": "line", "stream_name": self.DIGITAL_IN, "channel_id": "DIGITAL-IN-14"},
            "DIGITAL-IN-15": {"kind": "line", "stream_name": self.DIGITAL_IN, "channel_id": "DIGITAL-IN-15"},
            "DIGITAL-OUT-01": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-01"},
            "DIGITAL-OUT-02": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-02"},
            "DIGITAL-OUT-03": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-03"},
            "DIGITAL-OUT-04": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-04"},
            "DIGITAL-OUT-05": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-05"},
            "DIGITAL-OUT-06": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-06"},
            "DIGITAL-OUT-07": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-07"},
            "DIGITAL-OUT-08": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-08"},
            "DIGITAL-OUT-09": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-09"},
            "DIGITAL-OUT-10": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-10"},
            "DIGITAL-OUT-11": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-11"},
            "DIGITAL-OUT-12": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-12"},
            "DIGITAL-OUT-13": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-13"},
            "DIGITAL-OUT-14": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-14"},
            "DIGITAL-OUT-15": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-15"},
            "DIGITAL-OUT-16": {"kind": "line", "stream_name": self.DIGITAL_OUT, "channel_id": "DIGITAL-OUT-16"},
        }
        assert available_signals == expected_available_signals

    def test_get_metadata(self):
        """get_metadata is configuration-derived: it lists every line regardless of which ones fired, so
        the set is decided by the format, not by the samples (and no traces are read to produce it). A
        custom metadata_key namespaces the Events block."""
        interface = IntanDigitalInterface(file_path=self.FILE_PATH, metadata_key="digital")
        metadata = interface.get_metadata()

        event_types = metadata["Events"]["digital"]["event_types"]
        assert len(event_types) == 25
        # Each line is one event_type named after its header channel name, idle lines included.
        assert event_types["DIGITAL-IN-01"] == {"event_name": "DIGITAL-IN-01"}
        assert event_types["DIGITAL-OUT-16"] == {"event_name": "DIGITAL-OUT-16"}
        assert interface._events_data_dict is None  # get_metadata did not trigger a trace read

    def test_add_to_nwbfile(self):
        """Which lines get a table is decided by the Intan header, not by the data: every line the header
        names is written to nwbfile.events. A line that never fires is an empty (zero-row) table, not a
        dropped one."""
        interface = IntanDigitalInterface(file_path=self.FILE_PATH)
        nwbfile = mock_NWBFile()  # already carries a session_start_time
        interface.add_to_nwbfile(nwbfile=nwbfile)  # in-memory, no disk IO
        events = nwbfile.events

        assert len(events) == 25  # one EventsTable per line, each named after that line

        # The toggling lines carry their events, one row per high pulse, on both words.
        non_empty = {name: len(table) for name, table in events.items() if len(table)}
        assert non_empty == {
            "DIGITAL-IN-13": 3,
            "DIGITAL-IN-14": 10,
            "DIGITAL-IN-15": 10,
            "DIGITAL-OUT-13": 3,
            "DIGITAL-OUT-14": 10,
            "DIGITAL-OUT-15": 10,
        }


class TestIntanDigitalFileWithoutDigitalChannels:
    """An Intan session recorded with its digital inputs and outputs switched off."""

    # Amplifier-only RHD: the header declares neither digital word, so neo reports no digital stream.
    # Ordinary data rather than a defect, since Intan's header names only the lines that were enabled
    # at acquisition.
    FILE_PATH = ECEPHY_DATA_PATH / "intan" / "test_tetrode_240502_162925" / "test_tetrode_240502_162925.rhd"

    def test_a_file_with_no_digital_channels_is_refused_at_construction(self):
        """The interface says what is wrong with the file rather than what is wrong with the arguments.

        Without this, the default configuration derived from an empty inventory comes out empty and is
        refused by the shared validator's empty-configuration guard, whose message tells the caller to
        pass the ``None`` they just passed.
        """
        with pytest.raises(ValueError, match="carries no digital channels"):
            IntanDigitalInterface(file_path=self.FILE_PATH)
