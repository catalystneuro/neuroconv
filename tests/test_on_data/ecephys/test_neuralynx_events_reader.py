import re
from datetime import datetime

import pytest

from neuroconv.datainterfaces.ecephys.neuralynx._neuralynx_events_reader import (
    read_event_file,
)

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class TestCheetah64HardwareEvents:
    """Cheetah 5.4 on Cheetah64 hardware, where every TTL word has the highest line of the port set."""

    file_path = (
        ECEPHY_DATA_PATH
        / "neuralynx"
        / "cheetah"
        / "version_5_4_0"
        / "continuous_signals"
        / "cheetah64_hardware"
        / "Events.nev"
    )

    def test_ttl_values_are_unsigned_port_words(self):
        event_file = read_event_file(self.file_path)

        expected_ttl_values = [0xFFE1, 0xFFE0, 0xFFE4, 0xFFE2, 0xFFE0]
        assert list(event_file.records["ttl_value"]) == expected_ttl_values

    def test_records(self):
        event_file = read_event_file(self.file_path)
        records = event_file.records

        expected_timestamps = [701704988, 701705978, 702004628, 702404588, 702429602]
        assert list(records["timestamp"]) == expected_timestamps
        assert records["event_string"][0] == "Cheetah 32 DIO board 0 input TTL (0xFFE1)"

        # This Cheetah version names the device and board in the text but not the port.
        assert set(records["device"]) == {"Cheetah 32 DIO"}
        assert set(records["ttl_direction"]) == {"input"}
        assert set(records["board"]) == {0}
        assert set(records["port"]) == {-1}

    def test_header(self):
        event_file = read_event_file(self.file_path)

        assert event_file.time_opened == datetime(2012, 5, 29, 14, 23, 19, 380000)
        assert event_file.time_closed == datetime(2012, 5, 29, 15, 26, 47, 983000)
        assert event_file.closed_properly
        assert event_file.trailing_bytes == 0


class TestTwoPortsInOneStream:
    """Cheetah 5.6 with TTL records from ports 0 and 3, interleaved with text events typed during the recording."""

    file_path = (
        ECEPHY_DATA_PATH
        / "neuralynx"
        / "cheetah"
        / "version_5_6_0"
        / "continuous_signals"
        / "header_only_ncs"
        / "Events.nev"
    )

    def test_ports_are_read_from_the_text(self):
        event_file = read_event_file(self.file_path)
        records = event_file.records

        # The text events say nothing about a port, so theirs stays -1.
        expected_ports = [-1, 3, -1, 3, -1, 0, -1, 3, -1, 0]
        assert list(records["port"]) == expected_ports

        expected_event_strings = [
            "detectioin",
            "TTL Input on AcqSystem1_0 board 0 port 3 value (0x0000).",
            "detectioin",
            "TTL Input on AcqSystem1_0 board 0 port 3 value (0x0000).",
            "stimulation",
            "TTL Input on AcqSystem1_0 board 0 port 0 value (0x0000).",
            "detectioin",
            "TTL Input on AcqSystem1_0 board 0 port 3 value (0x0000).",
            "stimulation",
            "TTL Input on AcqSystem1_0 board 0 port 0 value (0x0000).",
        ]
        assert list(records["event_string"]) == expected_event_strings

        expected_ttl_values = [0x40, 0x0, 0x40, 0x0, 0x2, 0x0, 0x40, 0x0, 0x2, 0x0]
        assert list(records["ttl_value"]) == expected_ttl_values


class TestNeuralynxEventFileReaderEdgeCases:
    """Headers that are missing a part, and files too short to hold a header."""

    def test_file_not_closed_properly(self):
        file_path = (
            ECEPHY_DATA_PATH
            / "neuralynx"
            / "files_with_errors"
            / "cheetah"
            / "version_5_5_1"
            / "file_not_closed_properly"
            / "Events.nev"
        )
        event_file = read_event_file(file_path)

        assert not event_file.closed_properly
        assert event_file.time_opened == datetime(2019, 12, 13, 15, 13, 26, 211000)
        assert event_file.time_closed is None
        assert len(event_file.records) == 58

    def test_header_without_date_lines(self):
        # Pegasus 2.1.1 wrote this header without its opened and closed lines, so there are no times to read.
        file_path = ECEPHY_DATA_PATH / "neuralynx" / "NoDateHeader" / "NoDateHeader.nev"
        event_file = read_event_file(file_path)

        assert event_file.time_opened is None
        assert event_file.time_closed is None
        assert len(event_file.records) == 15
        assert event_file.records["event_string"][0] == "Starting Recording"
        assert event_file.records["port"][1] == 2

    def test_file_shorter_than_header_raises(self, tmp_path):
        file_path = tmp_path / "Events.nev"
        file_path.write_bytes(b"######## Neuralynx Data File Header\r\n")

        expected_message = "'Events.nev' is 37 bytes long, shorter than the 16384-byte Neuralynx header."
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            read_event_file(file_path)
