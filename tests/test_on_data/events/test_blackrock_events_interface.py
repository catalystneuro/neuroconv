import re

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import BlackrockEventsInterface
from neuroconv.tools.testing.data_interface_mixins import EventsInterfaceTestMixin

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class BlackrockEventsInterfaceMixin(EventsInterfaceTestMixin):
    """Builds ``self.interface`` from ``data_interface_cls`` and ``interface_kwargs`` set on the subclass."""

    data_interface_cls = BlackrockEventsInterface

    @pytest.fixture
    def interface(self):
        return self.data_interface_cls(**self.interface_kwargs)


class TestDigitalInput16BitWords(BlackrockEventsInterfaceMixin):
    """A spec 2.2 file whose digital packets use the high bits of the 16-bit port."""

    interface_kwargs = dict(
        file_path=ECEPHY_DATA_PATH
        / "blackrock"
        / "version_2_2"
        / "events"
        / "digital_input_16_bit_words"
        / "digital_input_16_bit_words.nev"
    )
    expected_temporal_alignment_keys = ("digital_input",)

    def test_get_metadata(self, interface):
        expected_columns = {
            "digital_input": {
                "column_name": "digital_input",
                "description": "The native digital input value stored in this packet. Its interpretation depends on capture mode.",
            },
            "packet_insertion_reason": {
                "column_name": "packet_insertion_reason",
                "description": (
                    "Why the packet was written, as the bit flags of the Blackrock file specification. Bit 0 is a "
                    "change on the digital input port; the other bits changed meaning between spec 2.x and spec 3.0."
                ),
            },
        }
        expected_metadata = {
            "blackrock_events": {
                "event_types": {"digital_input": {"event_name": "digital_input", "columns": expected_columns}},
            },
        }
        assert interface.get_metadata()["Events"] == expected_metadata

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        digital_input = nwbfile.events["DigitalInput"]
        expected_timestamps = np.array([4000, 13155, 22297, 31439, 40585, 49741]) / 30_000
        expected_values = [59136, 35328, 48896, 33280, 48896, 55808]
        assert digital_input.colnames == ("timestamp", "digital_input", "packet_insertion_reason")
        assert np.allclose(digital_input["timestamp"][:], expected_timestamps)
        assert list(digital_input["digital_input"][:]) == expected_values
        assert list(digital_input["packet_insertion_reason"][:]) == [1] * 6


class TestFrameCounterComments(BlackrockEventsInterfaceMixin):
    """A spec 2.3 file with digital packets and comments that count video frames."""

    interface_kwargs = dict(
        file_path=ECEPHY_DATA_PATH
        / "blackrock"
        / "version_2_3"
        / "events"
        / "frame_counter_comments"
        / "frame_counter_comments.nev"
    )
    expected_temporal_alignment_keys = ("digital_input", "comments")

    def test_session_start_time(self, interface):
        expected_session_start_time = "2018-03-30T20:11:56.770000+00:00"
        assert interface.get_metadata()["NWBFile"]["session_start_time"] == expected_session_start_time

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert sorted(nwbfile.events) == ["Comments", "DigitalInput"]
        assert len(nwbfile.events["DigitalInput"]) == 14

        comments = nwbfile.events["Comments"]
        expected_timestamps = np.array([29099, 59100, 89098, 119099]) / 30_000
        expected_texts = ["Frame:31", "Frame:61", "Frame:91", "Frame:121"]
        assert np.allclose(comments["timestamp"][:], expected_timestamps)
        assert list(comments["text"][:]) == expected_texts
        # These comments carry a colour instead of a start time.
        assert list(comments["character_set"][:]) == [0] * 4
        assert list(comments["flag"][:]) == [0] * 4
        assert list(comments["comment_data"][:]) == [0xFF00FF] * 4


class TestLogEvent(BlackrockEventsInterfaceMixin):
    """A spec 2.3 file with a log packet and a data loss comment that records when it was started."""

    interface_kwargs = dict(
        file_path=ECEPHY_DATA_PATH / "blackrock" / "version_2_3" / "events" / "log_event" / "log_event.nev"
    )
    expected_temporal_alignment_keys = ("comments", "log_events")

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        log_events = nwbfile.events["LogEvents"]
        assert np.allclose(log_events["timestamp"][:], [15933 / 30_000])
        assert list(log_events["mode"][:]) == [1]
        assert list(log_events["application"][:]) == ["NSP"]
        assert list(log_events["text"][:]) == ["-19 interrupts missed."]

        # On the 30 kHz clock the file records the comment's start as a timestamp of its own, 16781.
        comments = nwbfile.events["Comments"]
        assert list(comments["text"][:]) == ["Data Loss. Information Possibly Lost On The NSP!"]
        assert np.allclose(comments["timestamp"][:], [17088 / 30_000])
        assert list(comments["flag"][:]) == [1]
        assert list(comments["comment_data"][:]) == [16781]


class TestVideoSync(BlackrockEventsInterfaceMixin):
    """A spec 2.3 file with video sync packets from NeuroMotive."""

    interface_kwargs = dict(
        file_path=ECEPHY_DATA_PATH
        / "blackrock"
        / "version_2_3"
        / "events"
        / "video_sync_and_tracking"
        / "video_sync_and_tracking.nev"
    )
    expected_temporal_alignment_keys = ("video_sync",)

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        video_sync = nwbfile.events["VideoSync"]
        assert len(video_sync) == 77
        assert video_sync.colnames == ("timestamp", "file_number", "frame_number", "elapsed_milliseconds", "source_id")
        assert np.allclose(video_sync["timestamp"][:3], np.array([113, 14900, 15499]) / 30_000)
        assert list(video_sync["frame_number"][:3]) == [61410, 0, 1]
        assert list(video_sync["elapsed_milliseconds"][:3]) == [2131417, 481, 501]


class TestRecordingEventsAndButtonTrigger(BlackrockEventsInterfaceMixin):
    """A spec 3.0 file with PTP timestamps, paused and resumed, with a button press and a comment."""

    interface_kwargs = dict(
        file_path=ECEPHY_DATA_PATH
        / "blackrock"
        / "version_3_0"
        / "events"
        / "recording_events_and_button_trigger"
        / "recording_events_and_button_trigger.nev"
    )
    expected_temporal_alignment_keys = ("comments", "recording_events", "button_triggers")

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        # PTP timestamps count nanoseconds.
        recording_events = nwbfile.events["RecordingEvents"]
        expected_timestamps = (
            np.array([1793159866930678947, 1793159872500679855, 1793159876120680504, 1793159907350685468]) / 1e9
        )
        assert np.allclose(recording_events["timestamp"][:], expected_timestamps)
        assert list(recording_events["reason"][:]) == ["start", "pause", "resume", "stop"]

        button_triggers = nwbfile.events["ButtonTriggers"]
        assert np.allclose(button_triggers["timestamp"][:], [1793159880210114401 / 1e9])
        assert list(button_triggers["trigger_type"][:]) == [1]

    def test_comment_start_time_on_the_ptp_clock(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        # The comment is written twice. With flag 1 on the PTP clock, the data field is the microseconds from the
        # start of the comment back to the packet, 3332200 here.
        comments = nwbfile.events["Comments"]
        assert list(comments["text"][:]) == ["late comment", "late comment"]
        assert list(comments["flag"][:]) == [0, 1]
        assert list(comments["comment_data"][:]) == [0, 3332200]


class TestBlackrockEventsInterfaceEdgeCases:
    """Files the interface refuses, each read without running a conversion."""

    def test_file_with_no_event_packets_raises(self):
        file_path = (
            ECEPHY_DATA_PATH / "blackrock" / "version_2_3" / "events" / "header_only_nev" / "header_only_nev.nev"
        )

        expected_message = "'header_only_nev.nev' holds no event packets."
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            BlackrockEventsInterface(file_path=file_path)

    def test_spec_20_file_with_only_spikes_raises(self):
        # Spec 2.0 has the spec 2.1 layout. This file holds spike packets only.
        file_path = (
            ECEPHY_DATA_PATH / "blackrock" / "version_2_0" / "spikes" / "packet_bytes_110" / "packet_bytes_110.nev"
        )

        expected_message = "'packet_bytes_110.nev' holds no event packets."
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            BlackrockEventsInterface(file_path=file_path)

    def test_file_shorter_than_basic_header_raises(self, tmp_path):
        file_path = tmp_path / "short.nev"
        file_path.write_bytes(b"NEURALEV" + b"\x00" * 20)

        expected_message = (
            "'short.nev' is 28 bytes long, shorter than the 336-byte basic header of a Blackrock event file."
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            BlackrockEventsInterface(file_path=file_path)

    def test_unknown_file_identifier_raises(self, tmp_path):
        file_path = tmp_path / "not_blackrock.nev"
        file_path.write_bytes(b"NOTANEV!" + b"\x00" * 400)

        expected_message = "'not_blackrock.nev' does not start with a Blackrock event file identifier."
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            BlackrockEventsInterface(file_path=file_path)
