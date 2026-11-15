import re

import pytest

from neuroconv.datainterfaces.ecephys.blackrock._blackrock_events_reader import (
    read_event_file,
)

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class TestDigitalInput16BitWords:
    """A spec 2.2 file whose digital packets use the high bits of the 16-bit port."""

    file_path = (
        ECEPHY_DATA_PATH
        / "blackrock"
        / "version_2_2"
        / "events"
        / "digital_input_16_bit_words"
        / "digital_input_16_bit_words.nev"
    )

    def test_digital_events(self):
        events = read_event_file(self.file_path)

        expected_digital_events = [
            (4000, 1, 59136),
            (13155, 1, 35328),
            (22297, 1, 48896),
            (31439, 1, 33280),
            (40585, 1, 48896),
            (49741, 1, 55808),
        ]
        assert events.spec == "2.2"
        assert events.digital_events.tolist() == expected_digital_events


class TestDigitalInputTrellis:
    """A spec 2.2 file written by Trellis, with a long run of digital packets."""

    file_path = (
        ECEPHY_DATA_PATH
        / "blackrock"
        / "version_2_2"
        / "events"
        / "digital_input_trellis"
        / "digital_input_trellis.nev"
    )

    def test_digital_events(self):
        events = read_event_file(self.file_path)

        expected_first_digital_events = [
            (537352, 1, 329),
            (537356, 1, 366),
            (537360, 1, 372),
            (537364, 1, 357),
            (537369, 1, 370),
        ]
        assert events.application == "Trellis[1.14.2.39]"
        assert len(events.digital_events) == 643
        assert events.digital_events[:5].tolist() == expected_first_digital_events


class TestFrameCounterComments:
    """A spec 2.3 file with digital packets and comments that count video frames."""

    file_path = (
        ECEPHY_DATA_PATH
        / "blackrock"
        / "version_2_3"
        / "events"
        / "frame_counter_comments"
        / "frame_counter_comments.nev"
    )

    def test_comments(self):
        events = read_event_file(self.file_path)

        expected_texts = ["Frame:31", "Frame:61", "Frame:91", "Frame:121"]
        expected_timestamps = [29099, 59100, 89098, 119099]
        assert [comment["text"] for comment in events.comments] == expected_texts
        assert [comment["timestamp"] for comment in events.comments] == expected_timestamps
        # Flag 0 means the data field is a colour, so the comment has no start time.
        assert all(comment["start_timestamp"] is None for comment in events.comments)

    def test_digital_events(self):
        events = read_event_file(self.file_path)

        expected_first_digital_events = [(15069, 1, 65533), (15219, 1, 65525), (30069, 1, 65533)]
        assert len(events.digital_events) == 14
        assert events.digital_events[:3].tolist() == expected_first_digital_events


class TestLogEvent:
    """A spec 2.3 file with a log packet and a data loss comment."""

    file_path = ECEPHY_DATA_PATH / "blackrock" / "version_2_3" / "events" / "log_event" / "log_event.nev"

    def test_log_event(self):
        events = read_event_file(self.file_path)

        expected_log_events = [dict(timestamp=15933, mode=1, application="NSP", text="-19 interrupts missed.")]
        assert events.log_events == expected_log_events

    def test_comment_start_time_on_the_sample_clock(self):
        events = read_event_file(self.file_path)

        # With flag 1 on the 30 kHz clock, the data field is the timestamp the comment was started.
        expected_comment = dict(
            timestamp=17088,
            char_set=0,
            flag=1,
            data=16781,
            text="Data Loss. Information Possibly Lost On The NSP!",
            start_timestamp=16781,
        )
        assert events.comments == [expected_comment]


class TestVideoSync:
    """A spec 2.3 file with video sync packets from NeuroMotive."""

    file_path = (
        ECEPHY_DATA_PATH
        / "blackrock"
        / "version_2_3"
        / "events"
        / "video_sync_and_tracking"
        / "video_sync_and_tracking.nev"
    )

    def test_video_sync_events(self):
        events = read_event_file(self.file_path)
        fields = ["timestamp", "file_number", "frame_number", "elapsed_time", "source_id"]

        expected_first_video_sync_events = [(113, 0, 61410, 2131417, 0), (14900, 0, 0, 481, 0), (15499, 0, 1, 501, 0)]
        assert len(events.video_sync_events) == 77
        assert events.video_sync_events[:3][fields].tolist() == expected_first_video_sync_events


class TestRecordingEventsAndButtonTrigger:
    """A spec 3.0 file with PTP timestamps, paused and resumed, with a button press and a comment."""

    file_path = (
        ECEPHY_DATA_PATH
        / "blackrock"
        / "version_3_0"
        / "events"
        / "recording_events_and_button_trigger"
        / "recording_events_and_button_trigger.nev"
    )

    def test_recording_events(self):
        events = read_event_file(self.file_path)

        expected_recording_events = [
            dict(timestamp=1793159866930678947, reason="start"),
            dict(timestamp=1793159872500679855, reason="pause"),
            dict(timestamp=1793159876120680504, reason="resume"),
            dict(timestamp=1793159907350685468, reason="stop"),
        ]
        assert events.is_ptp
        assert events.recording_events == expected_recording_events

    def test_button_trigger(self):
        events = read_event_file(self.file_path)

        expected_button_trigger_events = [(1793159880210114401, 1)]
        assert events.button_trigger_events[["timestamp", "trigger_type"]].tolist() == expected_button_trigger_events

    def test_comment_start_time_on_the_ptp_clock(self):
        events = read_event_file(self.file_path)

        # The comment is written twice. With flag 1 on the PTP clock, the data field is the microseconds from the
        # start of the comment back to the packet.
        expected_comments = [
            dict(
                timestamp=1793159903693851549,
                char_set=0,
                flag=0,
                data=0,
                text="late comment",
                start_timestamp=None,
            ),
            dict(
                timestamp=1793159903693851549,
                char_set=0,
                flag=1,
                data=3332200,
                text="late comment",
                start_timestamp=1793159900361651549,
            ),
        ]
        assert events.comments == expected_comments


class TestSpec20EventFile:
    """A spec 2.0 event file, which has the same layout as spec 2.1 and holds only spikes."""

    file_path = ECEPHY_DATA_PATH / "blackrock" / "version_2_0" / "spikes" / "packet_bytes_110" / "packet_bytes_110.nev"

    def test_reads_with_no_events(self):
        events = read_event_file(self.file_path)

        assert events.spec == "2.0"
        assert events.time_origin is None
        assert len(events.digital_events) == 0
        assert events.comments == []


class TestBlackrockEventsReaderEdgeCases:
    """A file with headers and no packets, and files that are not Blackrock event files."""

    def test_header_only_file(self):
        file_path = (
            ECEPHY_DATA_PATH / "blackrock" / "version_2_3" / "events" / "header_only_nev" / "header_only_nev.nev"
        )
        events = read_event_file(file_path)

        assert len(events.digital_events) == 0
        assert events.comments == []
        assert events.recording_events == []

    def test_file_shorter_than_basic_header_raises(self, tmp_path):
        file_path = tmp_path / "short.nev"
        file_path.write_bytes(b"NEURALEV" + b"\x00" * 20)

        expected_message = (
            "'short.nev' is 28 bytes long, shorter than the 336-byte basic header of a Blackrock event file."
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            read_event_file(file_path)

    def test_unknown_file_identifier_raises(self, tmp_path):
        file_path = tmp_path / "not_blackrock.nev"
        file_path.write_bytes(b"NOTANEV!" + b"\x00" * 400)

        expected_message = "'not_blackrock.nev' does not start with a Blackrock event file identifier."
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            read_event_file(file_path)
