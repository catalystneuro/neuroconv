from datetime import datetime

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import OpenEphysBinaryEventsInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

OPENEPHYS_DATA_PATH = ECEPHY_DATA_PATH / "openephysbinary"
WITH_SYNC_PATH = OPENEPHYS_DATA_PATH / "v0.6.x_neuropixels_with_sync"
MULTIEXP_PATH = OPENEPHYS_DATA_PATH / "v0.6.x_neuropixels_multiexp_multistream"
MISSING_FOLDERS_PATH = OPENEPHYS_DATA_PATH / "v0.6.x_neuropixels_missing_folders"
PRE_V06_PATH = OPENEPHYS_DATA_PATH / "v0.4.4.1_with_video_tracking"
TWO_NODES_PATH = OPENEPHYS_DATA_PATH / "v0.5.x_two_nodes"

NIDQ_STREAM = "Record Node 104#NI-DAQmx-103.PXIe-6341"
MESSAGE_STREAM = "Record Node 104#MessageCenter"


def test_get_stream_names():
    # Every event stream the recording wrote, named as SpikeInterface names the recording streams.
    stream_names = OpenEphysBinaryEventsInterface.get_stream_names(folder_path=WITH_SYNC_PATH)
    assert stream_names == [
        "Record Node 104#MessageCenter",
        "Record Node 104#NI-DAQmx-103.PXIe-6341",
        "Record Node 104#Neuropix-PXI-100.ProbeA-AP",
        "Record Node 104#Neuropix-PXI-100.ProbeA-LFP",
    ]


def test_get_stream_names_skips_folders_never_written():
    # This recording's structure.oebin lists four event streams but only two were written to disk
    # (ProbeC and MessageCenter are absent); the streams that exist are still read.
    stream_names = OpenEphysBinaryEventsInterface.get_stream_names(folder_path=MISSING_FOLDERS_PATH)
    assert stream_names == [
        "Record Node 101#NI-DAQmx-103.PXIe-6341",
        "Record Node 101#Neuropix-PXI-100.ProbeB",
    ]


def test_stream_name_required_when_several():
    with pytest.raises(ValueError, match="More than one event stream is detected"):
        OpenEphysBinaryEventsInterface(folder_path=WITH_SYNC_PATH)


def test_unknown_stream_name():
    with pytest.raises(ValueError, match="is not in the available streams"):
        OpenEphysBinaryEventsInterface(folder_path=WITH_SYNC_PATH, stream_name="Record Node 104#NotAStream")


def test_block_index_required_when_several_experiments():
    with pytest.raises(ValueError, match="More than one experiment is detected"):
        OpenEphysBinaryEventsInterface(folder_path=MULTIEXP_PATH, stream_name=NIDQ_STREAM)


def test_block_index_out_of_range():
    with pytest.raises(ValueError, match="out of range"):
        OpenEphysBinaryEventsInterface(folder_path=MULTIEXP_PATH, block_index=3)


def test_session_start_time_absent():
    # Both Record Nodes of this session wrote their streams and no settings.xml, so no start time is
    # reported and nothing raises over it. It also names its nodes 'RecordNode103', without the space.
    stream_names = OpenEphysBinaryEventsInterface.get_stream_names(folder_path=TWO_NODES_PATH)
    assert stream_names == [
        "RecordNode103#Message_Center-904.0/TEXT_group_1",
        "RecordNode105#Message_Center-904.0/TEXT_group_1",
    ]

    interface = OpenEphysBinaryEventsInterface(folder_path=TWO_NODES_PATH, stream_name=stream_names[0])
    assert "session_start_time" not in interface.get_metadata()["NWBFile"]


def test_no_recording_found(tmp_path):
    with pytest.raises(ValueError, match="No Open Ephys binary recording was found"):
        OpenEphysBinaryEventsInterface(folder_path=tmp_path)


class OpenEphysBinaryEventsInterfaceMixin:
    """Builds ``self.interface`` from ``data_interface_cls`` and ``interface_kwargs`` set on the subclass."""

    data_interface_cls = OpenEphysBinaryEventsInterface

    @pytest.fixture
    def interface(self):
        return self.data_interface_cls(**self.interface_kwargs)


class TestDigitalLines(OpenEphysBinaryEventsInterfaceMixin):
    """The digital input lines of a NI-DAQmx board: four lines that fired, each written as its own table
    of every edge it produced."""

    interface_kwargs = dict(folder_path=WITH_SYNC_PATH, stream_name=NIDQ_STREAM)

    def test_get_metadata(self, interface):
        # One entry per line that fired, keyed by the line, each carrying the two columns the format
        # itself explains: the direction of the transition and the latched port value. What the line
        # was wired to is not in the file, so the name stays the line's own until a user renames it.
        expected_columns = {
            "state": {
                "column_name": "edge",
                "description": "The direction of the transition that produced this event.",
                "column_categories": {"labels": {1: "rising", -1: "falling"}},
            },
            "full_word": {
                "column_name": "full_word",
                "description": "The state of the first 64 TTL lines at the moment of this event.",
            },
        }
        expected_metadata = {
            "open_ephys_events": {
                "event_types": {
                    line: {"event_name": line, "columns": expected_columns}
                    for line in ["line1", "line2", "line6", "line7"]
                },
            },
        }
        assert interface.get_metadata()["Events"] == expected_metadata

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert sorted(nwbfile.events) == ["Line1", "Line2", "Line6", "Line7"]

        # Every edge is a row of its line's table, rising and falling alike, so the row count is the
        # number of transitions the line recorded rather than the number of pulses it can be read as.
        assert {name: len(table) for name, table in nwbfile.events.items()} == {
            "Line1": 3143,
            "Line2": 1121,
            "Line6": 62630,
            "Line7": 93947,
        }

        line1 = nwbfile.events["Line1"]
        assert line1.colnames == ("timestamp", "edge", "full_word")
        assert np.allclose(line1["timestamp"][:4], [728.069181, 728.569167, 729.069233, 729.569267])
        assert list(line1["edge"][:4]) == ["falling", "rising", "falling", "rising"]
        assert list(line1["full_word"][:4]) == [66, 67, 66, 67]

    def test_session_start_time(self, interface):
        # Read from the Record Node's settings.xml, so an events-only conversion carries the same start
        # time the recording interface gives the same session.
        assert interface.get_metadata()["NWBFile"]["session_start_time"] == datetime(2023, 8, 30, 23, 41, 36)

    def test_coded_word_is_kept(self, interface):
        # The latched word is what a coded port is read from: line 6 fires while lines 7, 2 and 1 are
        # also high (99 = 64 + 32 + 2 + 1), which is the payload the neo path drops.
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        line6 = nwbfile.events["Line6"]
        assert list(line6["full_word"][:4]) == [35, 67, 99, 3]


class TestUnclosedInterval(OpenEphysBinaryEventsInterfaceMixin):
    """An experiment whose recording stopped with a line still high, so its rising edges outnumber its
    falling ones. Taking the edges as they are keeps the line whole; pairing them into intervals is
    where such a line is lost."""

    interface_kwargs = dict(
        folder_path=MULTIEXP_PATH,
        stream_name="Record Node 101#NI-DAQmx-103.PXIe-6341",
        block_index=2,
    )

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        line1 = nwbfile.events["Line1"]
        edges = list(line1["edge"][:])
        assert len(line1) == 1453
        assert edges.count("rising") == 727
        assert edges.count("falling") == 726


class TestBlockIndexSelectsExperiment(OpenEphysBinaryEventsInterfaceMixin):
    """The experiments of a session restart the clock, so each is read on its own through ``block_index``."""

    interface_kwargs = dict(
        folder_path=MULTIEXP_PATH,
        stream_name="Record Node 101#NI-DAQmx-103.PXIe-6341",
        block_index=1,
    )

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        # experiment3 opens with a falling edge (the line was already high when recording started) and
        # holds 1493 transitions on line 1, against experiment6's 1453.
        line1 = nwbfile.events["Line1"]
        assert len(line1) == 1493
        assert line1["edge"][0] == "falling"

    def test_session_start_time(self, interface):
        # The GUI writes one settings file per experiment, so the start time is experiment3's own
        # (settings_3.xml, 11:09:55) and not the one settings.xml holds for experiment1 (10:52:24).
        assert interface.get_metadata()["NWBFile"]["session_start_time"] == datetime(2022, 5, 3, 11, 9, 55)


class TestMessages(OpenEphysBinaryEventsInterfaceMixin):
    """The Message Center stream: free text annotations, written as one table of messages."""

    interface_kwargs = dict(folder_path=WITH_SYNC_PATH, stream_name=MESSAGE_STREAM)

    def test_get_metadata(self, interface):
        expected_metadata = {
            "open_ephys_events": {
                "event_types": {
                    "messages": {
                        "event_name": "messages",
                        "columns": {"text": {"column_name": "text", "description": "The text of this message."}},
                    },
                },
            },
        }
        assert interface.get_metadata()["Events"] == expected_metadata

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        messages = nwbfile.events["Messages"]
        assert messages.colnames == ("timestamp", "text")
        assert len(messages) == 1124
        assert list(messages["text"][:2]) == ["NP OPTO 5 2 1 blue 14"] * 2
        assert np.allclose(messages["timestamp"][:2], [1339.694967, 1339.694967])


class TestPreV06Layout(OpenEphysBinaryEventsInterfaceMixin):
    """A recording written before v0.6, which names the states array ``channel_states`` and counts its
    timestamps in samples rather than seconds."""

    interface_kwargs = dict(folder_path=PRE_V06_PATH, stream_name="Rhythm_FPGA-100.0/TTL_1")

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        line8 = nwbfile.events["Line8"]
        assert line8.colnames == ("timestamp", "edge", "full_word")
        assert len(line8) == 14
        # 1046013 samples at 30 kHz, the sampling rate the stream declares in structure.oebin.
        assert np.allclose(line8["timestamp"][:4], [34.8671, 34.867133, 35.100367, 35.1004])
        assert list(line8["edge"][:4]) == ["rising", "falling", "rising", "falling"]
        assert list(line8["full_word"][:4]) == [128, 0, 128, 0]


class TestStreamWithoutEvents(OpenEphysBinaryEventsInterfaceMixin):
    """A stream that was recorded and never fired. A line is only known here by having toggled, so a
    stream where none did reports no event types and writes no table."""

    interface_kwargs = dict(folder_path=PRE_V06_PATH, stream_name="Sync_Port-129.0/TTL_1")

    def test_get_metadata(self, interface):
        assert interface.get_metadata()["Events"] == {}

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert nwbfile.events == {}
