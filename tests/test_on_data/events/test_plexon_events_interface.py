from datetime import timezone
from struct import pack, pack_into

import numpy as np
import pytest
from pynwb import NWBHDF5IO, read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import PlexonEventsInterface
from neuroconv.tools.testing.data_interface_mixins import EventsInterfaceTestMixin
from tests.test_on_data.setup_paths import ECEPHY_DATA_PATH

PLX_PATH = ECEPHY_DATA_PATH / "plexon" / "plx"
TETRODE_PATH = PLX_PATH / "trode_layout" / "tetrode" / "spikes_wideband_field_potentials_and_events.plx"


class TestPlexonEventsInterface(EventsInterfaceTestMixin):
    data_interface_cls = PlexonEventsInterface
    interface_kwargs = {"file_path": TETRODE_PATH}
    expected_temporal_alignment_keys = ("EVT01", "EVT02", "EVT03", "Strobed")
    event_source_discovery_kwargs = {"file_path": TETRODE_PATH}
    expected_event_sources = (
        *(f"EVT{channel:02d}" for channel in range(1, 33)),
        "Strobed",
        "Start",
        "Stop",
        *(f"KBD{channel}" for channel in range(1, 9)),
    )
    expected_default_event_type_ids = expected_temporal_alignment_keys
    populated_event_source = "EVT01"
    silent_event_source = "EVT32"

    def check_read_nwb(self, nwbfile_path):
        super().check_read_nwb(nwbfile_path)
        nwbfile = read_nwb(nwbfile_path)
        try:
            assert set(nwbfile.events) == set(self.expected_temporal_alignment_keys)
            assert nwbfile.events["EVT01"].colnames == ("timestamp",)
            assert nwbfile.events["EVT01"]["timestamp"][:].tolist() == [0.68105, 0.889]
            assert nwbfile.events["EVT02"]["timestamp"][:].tolist() == [0.785025, 0.889925]
            assert nwbfile.events["EVT03"]["timestamp"][:].tolist() == [0.995]
            strobed = nwbfile.events["Strobed"]
            assert strobed["timestamp"][:].tolist() == [0.681975, 0.785975, 0.890925, 0.995925]
            np.testing.assert_array_equal(strobed["strobed_word"][:], [65281, 65282, 65283, 65284])
        finally:
            nwbfile.read_io.close()


def test_plexon_event_source_discovery_and_silent_selection(tmp_path):
    sources = PlexonEventsInterface.get_available_event_sources(TETRODE_PATH)
    assert len(sources) == 43
    assert sources["EVT32"]["supported_operations"] == []
    assert sources["Strobed"]["supported_operations"] == ["separation"]
    assert sources["KBD1"]["unsupported_reason"]
    assert sources["Start"]["unsupported_reason"]

    interface = PlexonEventsInterface(
        TETRODE_PATH,
        event_extraction_configuration={
            "silent_input": {"source": "EVT32"},
            "strobes": {
                "source": "Strobed",
                "separation": {"by_payload_fields": ["strobed_word"], "select": [65282, 65535]},
            },
        },
    )
    assert interface.get_event_type_source_ids() == ["silent_input", "strobes_65282", "strobes_65535"]
    assert list(interface.temporal_alignment.keys()) == ["silent_input", "strobes_65282", "strobes_65535"]

    metadata = interface.get_metadata()
    session_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=timezone.utc)
    metadata["NWBFile"]["session_start_time"] = session_time
    nwbfile_path = tmp_path / "selected.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    with NWBHDF5IO(nwbfile_path, mode="r") as io:
        events = io.read().events
        assert len(events["SilentInput"]) == 0
        assert events["Strobes65282"]["strobed_word"][:].tolist() == [65282]
        assert len(events["Strobes65535"]) == 0
        assert events["Strobes65535"]["strobed_word"][:].dtype == np.uint16


def test_plexon_deferred_recording_control_source():
    with pytest.raises(ValueError, match="cannot read 'Start'"):
        PlexonEventsInterface(TETRODE_PATH, event_extraction_configuration={"control": {"source": "Start"}})


def test_plexon_custom_header_name_and_timestamp_clock():
    file_path = (
        PLX_PATH / "timestamp_clock" / "one_megahertz_forty_bit_timestamps" / "sorted_spikes_and_strobed_events.plx"
    )
    interface = PlexonEventsInterface(
        file_path,
        event_extraction_configuration={
            "strobes": {
                "source": "events",
                "separation": {"by_payload_fields": ["strobed_word"], "select": [100]},
            }
        },
    )
    assert interface.get_event_type_source_ids() == ["strobes_100"]
    assert interface.get_event_times("strobes_100").tolist() == [8593.72036, 8593.866827]


def test_plexon_padded_events_repeated_words_and_native_name_collisions(tmp_path):
    file_path = tmp_path / "events.plx"
    names = [(0, ""), (3, "0"), (4, "input"), (5, "input"), (6, "input_4"), (241, "card_two")]
    header = bytearray(7504)
    header[:4] = b"PLEX"
    pack_into("<i", header, 4, 106)
    pack_into("<4i", header, 136, 1_000_000, 0, len(names), 0)
    channel_headers = b"".join(pack("<32si260x", name.encode("ascii"), channel) for channel, name in names)
    blocks = b"".join(
        [
            pack("<hHIhHhh8x", 4, 1, 11, 241, 65300, 1, 4),
            pack("<hHIhHhh", 4, 1, 11, 241, 65281, 0, 0),
            pack("<hHIhHhh", 4, 1, 11, 241, 65300, 0, 0),
            pack("<hHIhHhh", 4, 1, 1000, 0, 0, 0, 0),
        ]
    )
    file_path.write_bytes(header + channel_headers + blocks)

    sources = PlexonEventsInterface.get_available_event_sources(file_path)
    assert list(sources) == ["0_0", "0", "input_4_4", "input_5", "input_4", "card_two"]
    interface = PlexonEventsInterface(file_path)
    assert interface.get_event_type_source_ids() == ["0_0", "card_two"]
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile, metadata=interface.get_metadata())
    expected_timestamp = ((1 << 32) | 11) / 1_000_000
    words = nwbfile.events["CardTwo"]
    np.testing.assert_array_equal(words["timestamp"][:], [expected_timestamp] * 3)
    np.testing.assert_array_equal(words["strobed_word"][:], [65300, 65281, 65300])

    interface = PlexonEventsInterface(
        file_path,
        event_extraction_configuration={
            "strobes": {"source": "card_two", "separation": {"by_payload_fields": ["strobed_word"]}},
        },
    )
    assert interface.get_event_type_source_ids() == ["strobes_65300", "strobes_65281"]
    metadata = interface.get_metadata()
    event_types = metadata["Events"][interface.metadata_key]["event_types"]
    for event_type, entry in event_types.items():
        entry["table_metadata_key"] = "captured_words"
        entry["event_name"] = event_type.split("_")[-1]
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile, metadata=metadata)
    table = nwbfile.events["CapturedWords"]
    np.testing.assert_array_equal(table["timestamp"][:], [expected_timestamp] * 3)
    np.testing.assert_array_equal(table["strobed_word"][:], [65300, 65300, 65281])
