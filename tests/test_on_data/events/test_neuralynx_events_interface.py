import re

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import NeuralynxEventsInterface
from neuroconv.tools.testing.data_interface_mixins import EventsInterfaceTestMixin

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class NeuralynxEventsInterfaceMixin(EventsInterfaceTestMixin):
    """Builds ``self.interface`` from ``data_interface_cls`` and ``interface_kwargs`` set on the subclass."""

    data_interface_cls = NeuralynxEventsInterface
    expected_temporal_alignment_keys = ("event_records",)

    @pytest.fixture
    def interface(self):
        return self.data_interface_cls(**self.interface_kwargs)


class TestCheetah64HardwareEvents(NeuralynxEventsInterfaceMixin):
    """Cheetah 5.4 on Cheetah64 hardware, where every TTL word has the highest line of the port set."""

    interface_kwargs = dict(
        file_path=ECEPHY_DATA_PATH
        / "neuralynx"
        / "cheetah"
        / "version_5_4_0"
        / "continuous_signals"
        / "cheetah64_hardware"
        / "Events.nev"
    )

    def test_get_metadata(self, interface):
        expected_columns = {
            "event_id": {
                "column_name": "event_id",
                "description": "The event id Cheetah or Pegasus wrote for the record, naming the kind of event.",
            },
            "ttl_value": {
                "column_name": "ttl_value",
                "description": "The value of the 16-bit TTL port written with the record, one bit per line.",
            },
            "text": {"column_name": "text", "description": "The event string of the record."},
        }
        expected_metadata = {
            "neuralynx_events": {
                "event_types": {"event_records": {"event_name": "event_records", "columns": expected_columns}},
            },
        }
        metadata = interface.get_metadata()
        assert metadata["Events"] == expected_metadata
        assert metadata["NWBFile"]["session_start_time"] == "2012-05-29T14:23:19.380000"

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        event_records = nwbfile.events["EventRecords"]
        expected_timestamps = np.array([701704988, 701705978, 702004628, 702404588, 702429602]) / 1e6
        # The words are unsigned: each has the highest line of the port set, so it is 0x8000 or more.
        expected_ttl_values = [0xFFE1, 0xFFE0, 0xFFE4, 0xFFE2, 0xFFE0]
        assert event_records.colnames == ("timestamp", "event_id", "ttl_value", "text")
        assert np.allclose(event_records["timestamp"][:], expected_timestamps)
        assert list(event_records["ttl_value"][:]) == expected_ttl_values
        assert event_records["text"][0] == "Cheetah 32 DIO board 0 input TTL (0xFFE1)"


class TestNamedTTLValues(NeuralynxEventsInterfaceMixin):
    """Cheetah 6.4, where the user named two TTL values, so their records carry the name in place of the TTL text."""

    interface_kwargs = dict(
        file_path=ECEPHY_DATA_PATH
        / "neuralynx"
        / "cheetah"
        / "version_6_4_1_development"
        / "events"
        / "named_ttl_values"
        / "Events.nev"
    )

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        event_records = nwbfile.events["EventRecords"]
        expected_texts = [
            "Starting Recording",
            "start ontime",
            "detection",
            "stimulation",
            "TTL Input on AcqSystem1_0 board 0 port 0 value (0x0000).",
        ]
        assert len(event_records) == 12
        assert list(event_records["text"][:5]) == expected_texts
        # The named records keep their TTL value: "detection" is 0x1 and "stimulation" is 0x2.
        assert list(event_records["ttl_value"][:5]) == [0, 0, 1, 2, 0]
        assert list(event_records["event_id"][:5]) == [19, 4, 11, 11, 11]
        assert np.isclose(event_records["timestamp"][0], 1678794171607997 / 1e6)


class TestStimulationMessages(NeuralynxEventsInterfaceMixin):
    """Pegasus 2.2.1, with the messages a stimulation writes between the start and the stop of the recording."""

    interface_kwargs = dict(
        file_path=ECEPHY_DATA_PATH
        / "neuralynx"
        / "pegasus"
        / "version_2_2_1"
        / "events"
        / "stimulation_messages"
        / "Events.nev"
    )

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        event_records = nwbfile.events["EventRecords"]
        expected_texts = [
            "Starting Recording",
            "Stimulation triggered",
            "Stimulation delivery begins",
            "Stimulation delivery ends",
            "Stopping Recording",
        ]
        assert list(event_records["text"][:]) == expected_texts
        assert list(event_records["event_id"][:]) == [19, 23, 23, 23, 19]


class TestNeuralynxEventsInterfaceEdgeCases:
    """Headers that are missing a part, and files the interface refuses, each read without running a conversion."""

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
        interface = NeuralynxEventsInterface(file_path=file_path)

        # The opening time is still in the header, so the session start is read from it.
        assert interface.get_metadata()["NWBFile"]["session_start_time"] == "2019-12-13T15:13:26.211000"
        assert len(interface.get_event_times("event_records")) == 58

    def test_header_without_date_lines(self):
        # Pegasus 2.1.1 wrote this header without its opened and closed lines, so there is no session start.
        file_path = ECEPHY_DATA_PATH / "neuralynx" / "NoDateHeader" / "NoDateHeader.nev"
        interface = NeuralynxEventsInterface(file_path=file_path)

        assert "session_start_time" not in interface.get_metadata()["NWBFile"]
        assert len(interface.get_event_times("event_records")) == 15

    def test_file_with_no_records_raises(self, tmp_path):
        file_path = tmp_path / "Events.nev"
        file_path.write_bytes(b"######## Neuralynx Data File Header\r\n".ljust(2**14, b"\x00"))

        expected_message = "'Events.nev' holds no event records."
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            NeuralynxEventsInterface(file_path=file_path)

    def test_file_shorter_than_header_raises(self, tmp_path):
        file_path = tmp_path / "Events.nev"
        file_path.write_bytes(b"######## Neuralynx Data File Header\r\n")

        expected_message = "'Events.nev' is 37 bytes long, shorter than the 16384-byte Neuralynx header."
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            NeuralynxEventsInterface(file_path=file_path)
