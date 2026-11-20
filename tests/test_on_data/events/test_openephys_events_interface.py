from datetime import datetime

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import OpenEphysBinaryEventsInterface
from neuroconv.tools.testing.data_interface_mixins import EventsInterfaceTestMixin

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class TestOpenEphysBinaryEventsInterfaceEdgeCases:
    """Stream discovery, argument errors and streams with nothing to write, each read from a published
    recording without running a conversion."""

    with_sync_folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "v0.6.x_neuropixels_with_sync"
    multiexp_folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "v0.6.x_neuropixels_multiexp_multistream"
    missing_folders_folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "v0.6.x_neuropixels_missing_folders"
    two_nodes_folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "v0.5.x_two_nodes"
    no_events_folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "v0.6.x_onebox_neuropixels_nontrivial_wiring"

    def test_get_stream_names(self):
        # Every event stream the recording wrote, named as SpikeInterface names the recording streams.
        stream_names = OpenEphysBinaryEventsInterface.get_stream_names(folder_path=self.with_sync_folder_path)
        assert stream_names == [
            "Record Node 104#MessageCenter",
            "Record Node 104#NI-DAQmx-103.PXIe-6341",
            "Record Node 104#Neuropix-PXI-100.ProbeA-AP",
            "Record Node 104#Neuropix-PXI-100.ProbeA-LFP",
        ]

    def test_get_stream_names_skips_folders_never_written(self):
        # This recording's structure.oebin lists four event streams but only two were written to disk
        # (ProbeC and MessageCenter are absent); the streams that exist are still read.
        stream_names = OpenEphysBinaryEventsInterface.get_stream_names(folder_path=self.missing_folders_folder_path)
        assert stream_names == [
            "Record Node 101#NI-DAQmx-103.PXIe-6341",
            "Record Node 101#Neuropix-PXI-100.ProbeB",
        ]

    def test_stream_name_required_when_several(self):
        with pytest.raises(ValueError, match="More than one event stream is detected"):
            OpenEphysBinaryEventsInterface(folder_path=self.with_sync_folder_path)

    def test_unknown_stream_name(self):
        with pytest.raises(ValueError, match="is not in the available streams"):
            OpenEphysBinaryEventsInterface(
                folder_path=self.with_sync_folder_path, stream_name="Record Node 104#NotAStream"
            )

    def test_block_index_required_when_several_experiments(self):
        with pytest.raises(ValueError, match="More than one experiment is detected"):
            OpenEphysBinaryEventsInterface(
                folder_path=self.multiexp_folder_path, stream_name="Record Node 104#NI-DAQmx-103.PXIe-6341"
            )

    def test_block_index_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            OpenEphysBinaryEventsInterface(folder_path=self.multiexp_folder_path, block_index=3)

    def test_session_start_time_absent(self):
        # Both Record Nodes of this session wrote their streams and no settings.xml, so no start time is
        # reported and nothing raises over it. It also names its nodes 'RecordNode103', without the space.
        stream_names = OpenEphysBinaryEventsInterface.get_stream_names(folder_path=self.two_nodes_folder_path)
        assert stream_names == [
            "RecordNode103#Message_Center-904.0/TEXT_group_1",
            "RecordNode105#Message_Center-904.0/TEXT_group_1",
        ]

        interface = OpenEphysBinaryEventsInterface(folder_path=self.two_nodes_folder_path, stream_name=stream_names[0])
        assert "session_start_time" not in interface.get_metadata()["NWBFile"]

    def test_no_recording_found(self, tmp_path):
        with pytest.raises(ValueError, match="No Open Ephys binary recording was found"):
            OpenEphysBinaryEventsInterface(folder_path=tmp_path)

    def test_message_center_without_messages_writes_an_empty_table(self):
        interface = OpenEphysBinaryEventsInterface(
            folder_path=self.no_events_folder_path, stream_name="Record Node 101#MessageCenter"
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        expected_table_lengths = {"Messages": 0}
        assert {name: len(table) for name, table in nwbfile.events.items()} == expected_table_lengths

    def test_stream_without_events_or_declared_lines_writes_an_empty_table(self):
        interface = OpenEphysBinaryEventsInterface(
            folder_path=self.no_events_folder_path, stream_name="Record Node 101#OneBox-111.ProbeA"
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert [len(table) for table in nwbfile.events.values()] == [0]


class OpenEphysBinaryEventsInterfaceMixin:
    """Builds ``self.interface`` from ``data_interface_cls`` and ``interface_kwargs`` set on the subclass."""

    data_interface_cls = OpenEphysBinaryEventsInterface

    @pytest.fixture
    def interface(self):
        return self.data_interface_cls(**self.interface_kwargs)


class TestDigitalLines(OpenEphysBinaryEventsInterfaceMixin, EventsInterfaceTestMixin):
    """The digital input lines of a NI-DAQmx board: four lines that fired, each written as its own table
    of every edge it produced."""

    interface_kwargs = dict(
        folder_path=ECEPHY_DATA_PATH / "openephysbinary" / "v0.6.x_neuropixels_with_sync",
        stream_name="Record Node 104#NI-DAQmx-103.PXIe-6341",
    )
    expected_temporal_alignment_keys = ("Record_Node_104_NI_DAQmx_103_PXIe_6341",)

    def test_get_metadata(self, interface):
        event_types = interface.get_metadata()["Events"]["open_ephys_events"]["event_types"]
        assert tuple(event_types) == self.expected_temporal_alignment_keys
        columns = event_types[self.expected_temporal_alignment_keys[0]]["columns"]
        assert set(columns) == {"state", "line", "onset", "full_word"}
        assert columns["onset"]["column_categories"]["labels"] == {"rising": "rising", "falling": "falling"}

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert len(nwbfile.events) == 1
        table = next(iter(nwbfile.events.values()))
        assert table.colnames == ("timestamp", "state", "line", "onset", "full_word")
        assert len(table) == 3143 + 1121 + 62630 + 93947
        first_edges_on_line_one = np.flatnonzero(np.asarray(table["line"][:]) == 1)[:4]
        assert np.allclose(
            np.asarray(table["timestamp"][:])[first_edges_on_line_one], [728.069181, 728.569167, 729.069233, 729.569267]
        )
        assert list(np.asarray(table["state"][:])[first_edges_on_line_one]) == [-1, 1, -1, 1]
        assert list(np.asarray(table["onset"][:])[first_edges_on_line_one]) == [
            "falling",
            "rising",
            "falling",
            "rising",
        ]
        assert list(np.asarray(table["full_word"][:])[first_edges_on_line_one]) == [66, 67, 66, 67]

    def test_session_start_time(self, interface):
        # Read from the Record Node's settings.xml, so an events-only conversion carries the same start
        # time the recording interface gives the same session.
        assert interface.get_metadata()["NWBFile"]["session_start_time"] == datetime(2023, 8, 30, 23, 41, 36)

    def test_coded_word_is_kept(self, interface):
        # The latched word is what a coded port is read from: line 6 fires while lines 7, 2 and 1 are
        # also high (99 = 64 + 32 + 2 + 1), which is the payload the neo path drops.
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        table = next(iter(nwbfile.events.values()))
        line_six = np.asarray(table["line"][:]) == 6
        assert list(np.asarray(table["full_word"][:])[line_six][:4]) == [35, 67, 99, 3]


class TestUnclosedInterval(OpenEphysBinaryEventsInterfaceMixin):
    """An experiment whose recording stopped with a line still high, so its rising edges outnumber its
    falling ones. Taking the edges as they are keeps the line whole; pairing them into intervals is
    where such a line is lost."""

    interface_kwargs = dict(
        folder_path=ECEPHY_DATA_PATH / "openephysbinary" / "v0.6.x_neuropixels_multiexp_multistream",
        stream_name="Record Node 101#NI-DAQmx-103.PXIe-6341",
        block_index=2,
    )

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        table = next(iter(nwbfile.events.values()))
        line_one = np.asarray(table["line"][:]) == 1
        edges = list(np.asarray(table["onset"][:])[line_one])
        assert len(edges) == 1453
        assert edges.count("rising") == 727
        assert edges.count("falling") == 726


class TestBlockIndexSelectsExperiment(OpenEphysBinaryEventsInterfaceMixin):
    """The experiments of a session restart the clock, so each is read on its own through ``block_index``."""

    interface_kwargs = dict(
        folder_path=ECEPHY_DATA_PATH / "openephysbinary" / "v0.6.x_neuropixels_multiexp_multistream",
        stream_name="Record Node 101#NI-DAQmx-103.PXIe-6341",
        block_index=1,
    )

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        # experiment3 opens with a falling edge (the line was already high when recording started) and
        # holds 1493 transitions on line 1, against experiment6's 1453.
        table = next(iter(nwbfile.events.values()))
        line_one = np.asarray(table["line"][:]) == 1
        edges = np.asarray(table["onset"][:])[line_one]
        assert len(edges) == 1493
        assert edges[0] == "falling"

    def test_session_start_time(self, interface):
        # The GUI writes one settings file per experiment, so the start time is experiment3's own
        # (settings_3.xml, 11:09:55) and not the one settings.xml holds for experiment1 (10:52:24).
        assert interface.get_metadata()["NWBFile"]["session_start_time"] == datetime(2022, 5, 3, 11, 9, 55)


class TestMessages(OpenEphysBinaryEventsInterfaceMixin, EventsInterfaceTestMixin):
    """The Message Center stream: free text annotations, written as one table of messages."""

    interface_kwargs = dict(
        folder_path=ECEPHY_DATA_PATH / "openephysbinary" / "v0.6.x_neuropixels_with_sync",
        stream_name="Record Node 104#MessageCenter",
    )
    expected_temporal_alignment_keys = ("messages",)

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


class TestPreV06Layout(OpenEphysBinaryEventsInterfaceMixin, EventsInterfaceTestMixin):
    """A recording written before v0.6, which names the states array ``channel_states``, counts its
    timestamps in samples rather than seconds, and declares eight lines of which only line 8 fired."""

    interface_kwargs = dict(
        folder_path=ECEPHY_DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking",
        stream_name="Rhythm_FPGA-100.0/TTL_1",
    )
    expected_temporal_alignment_keys = ("Rhythm_FPGA_100_0_TTL_1",)

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert len(nwbfile.events) == 1
        line8 = next(iter(nwbfile.events.values()))
        assert line8.colnames == ("timestamp", "state", "line", "onset", "full_word", "full_word_pattern")
        assert len(line8) == 14
        # 1046013 samples at 30 kHz, the sampling rate the stream declares in structure.oebin.
        assert np.allclose(line8["timestamp"][:4], [34.8671, 34.867133, 35.100367, 35.1004])
        assert list(line8["onset"][:4]) == ["rising", "falling", "rising", "falling"]
        assert list(line8["full_word"][:4]) == [128, 0, 128, 0]
        assert list(line8["full_word_pattern"][:4]) == ["10000000", "00000000"] * 2


class TestStreamWithoutEvents(OpenEphysBinaryEventsInterfaceMixin):
    """A recorded stream with no edges still has one table."""

    interface_kwargs = dict(
        folder_path=ECEPHY_DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking",
        stream_name="Sync_Port-129.0/TTL_1",
    )

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert [len(table) for table in nwbfile.events.values()] == [0]
