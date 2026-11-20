import struct
from datetime import datetime, timezone

import numpy as np
import pytest
from pynwb import NWBHDF5IO, read_nwb

from neuroconv import NWBConverter
from neuroconv.datainterfaces import Plexon2EventsInterface
from neuroconv.tools.testing.data_interface_mixins import EventsInterfaceTestMixin

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

PL2_DATA_PATH = ECEPHY_DATA_PATH / "plexon" / "pl2"
TETRODE_PATH = PL2_DATA_PATH / "trode_layout" / "tetrode" / "spikes_wideband_field_potentials_auxiliary_and_events.pl2"
PLEXUTIL_PATH = PL2_DATA_PATH / "header_variant" / "plexutil_conversion" / "spikes_and_events.pl2"


class TestPlexon2EventsInterface(EventsInterfaceTestMixin):
    data_interface_cls = Plexon2EventsInterface
    expected_temporal_alignment_keys = ("EVT01", "EVT02", "EVT03", "Strobed")
    interface_kwargs = {"file_path": TETRODE_PATH}
    expected_event_sources = (
        *(f"KBD{key}" for key in range(1, 9)),
        *(f"EVT{channel:02}" for channel in range(1, 33)),
        "Strobed",
        "RSTART",
        "RSTOP",
        "CPX1",
        "CPX2",
        "CPX3",
    )

    def check_read_nwb(self, nwbfile_path):
        super().check_read_nwb(nwbfile_path)
        nwbfile = read_nwb(nwbfile_path)
        try:
            np.testing.assert_array_equal(nwbfile.events["Strobed"]["strobed_word"][:], [65281, 65282, 65283, 65284])
            for name, elapsed_ticks in {
                "EVT01": [27242, 35560],
                "EVT02": [31401, 35597],
                "EVT03": [39800],
                "Strobed": [27279, 31439, 35637, 39837],
            }.items():
                np.testing.assert_array_equal(
                    nwbfile.events[name]["timestamp"][:], (np.asarray(elapsed_ticks) + 3339180) / 40000
                )
            assert nwbfile.events["EVT01"].colnames == ("timestamp",)
        finally:
            nwbfile.read_io.close()

    def test_source_datetime(self, setup_interface):
        assert self.interface.get_metadata()["NWBFile"]["session_start_time"] == datetime(2013, 11, 20, 16, 4, 21)


def test_discovery_and_empty_channels_on_shifted_source_numbers(tmp_path):
    path = (
        PL2_DATA_PATH
        / "source_numbering"
        / "configuration_dependent_source_ids"
        / "spikes_wideband_spike_filtered_field_potentials_and_auxiliary.pl2"
    )
    available_sources = Plexon2EventsInterface.get_available_event_sources(file_path=path)
    assert {"EVT04", "Strobed", "KBD1", "RSTOP"}.issubset(available_sources)
    assert Plexon2EventsInterface(file_path=path).get_event_type_source_ids() == []

    selected = Plexon2EventsInterface(
        file_path=path,
        event_extraction_configuration={"EVT04": {"source": "EVT04"}, "Strobed": {"source": "Strobed"}},
    )
    output = tmp_path / "silent.nwb"
    metadata = selected.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime(2026, 11, 19, tzinfo=timezone.utc)
    selected.run_conversion(nwbfile_path=output, metadata=metadata)
    with NWBHDF5IO(output, mode="r") as io:
        events = io.read().events
        assert len(events["EVT04"]) == len(events["Strobed"]) == 0
        assert events["Strobed"]["strobed_word"].data.dtype == np.uint16


def test_deferred_source_is_declared_but_not_readable():
    with pytest.raises(ValueError, match="cannot read 'KBD1'"):
        Plexon2EventsInterface(file_path=TETRODE_PATH, event_extraction_configuration={"key": {"source": "KBD1"}})


def test_word_selection_rejects_float_in_interface_and_converter():
    class Plexon2Converter(NWBConverter):
        data_interface_classes = {"events": Plexon2EventsInterface}

    source_data = {
        "file_path": TETRODE_PATH,
        "event_extraction_configuration": {
            "strobes": {
                "source": "Strobed",
                "separation": {"by_payload_fields": ["strobed_word"], "select": [65281.0]},
            },
        },
    }
    with pytest.raises(ValueError, match="valid integer"):
        Plexon2EventsInterface(**source_data)
    with pytest.raises(ValueError, match="valid integer"):
        Plexon2Converter(source_data={"events": source_data})


def test_plexutil_preserves_gaps_and_every_repeated_word():
    interface = Plexon2EventsInterface(file_path=PLEXUTIL_PATH)
    assert interface.get_event_type_source_ids() == ["Event001", "Event002", "Event003", "Strobed"]
    assert interface.get_metadata()["NWBFile"]["session_start_time"] == datetime(2017, 9, 8, 10, 56, 4)
    times = interface.get_event_times("Strobed")
    assert len(times) == 1071
    np.testing.assert_array_equal(
        times[:7], np.asarray([101580, 132752, 247086, 278258, 349820, 455172, 561543]) / 40000
    )
    assert times[-1] > 2900

    split = Plexon2EventsInterface(
        file_path=PLEXUTIL_PATH,
        event_extraction_configuration={
            "strobes": {"source": "Strobed", "separation": {"by_payload_fields": ["strobed_word"]}}
        },
    )
    word_18_hits = split.get_event_times("strobes_18")
    assert len(word_18_hits) > 2
    np.testing.assert_array_equal(word_18_hits[:2], times[[0, 5]])
    assert sum(len(split.get_event_times(name)) for name in split.get_event_type_source_ids()) == 1071


def test_footerless_padded_blocks_keep_equal_timestamps_and_native_identity(tmp_path):
    # The channel number is the same in three sources. A control block deliberately
    # uses the identical pair as a digital block and must be excluded by record type.
    def channel_header(source, channel, name, source_name):
        record = bytearray(368)
        struct.pack_into("<BBH", record, 0, 0xD6, source, 176)
        record[16 : 16 + len(name)] = name
        struct.pack_into("<II", record, 80, source, channel)
        record[112 : 112 + len(source_name)] = source_name
        return record

    def event_block(kind, source, channel, ticks, values, padding=0):
        count = len(ticks)
        record = struct.pack("<BBHHQ2x", kind, source, 5 * count + padding, channel, count)
        record += struct.pack(f"<{count}Q{count}H", *ticks, *values) + bytes(2 * padding)
        return record + bytes(-len(record) % 16)

    header = bytearray(0x480)
    header[:16] = b"\xfe\x00\x00\x00\x00\x00\x00\x00\x03\x00PLEXON"
    header[0x10], header[0x11], header[0xD0] = 0xD2, 0x0E, 0xD3
    struct.pack_into("<dI", header, 0x258, 40000.0, 3)
    channels = (
        channel_header(12, 1, b"Repeated", b"Single-bit events")
        + channel_header(13, 1, b"Repeated", b"Other events")
        + channel_header(14, 1, b"", b"Multi-DI strobed")
    )
    late_tick = 2**33
    blocks = (
        event_block(0x59, 13, 1, [0], [1])
        + event_block(0x5A, 12, 1, [20], [1])
        + event_block(0x5A, 13, 1, [late_tick, late_tick], [65535, 65535], padding=12)
        + event_block(0x5A, 14, 1, [late_tick + 40], [32785])
    )
    data_start = len(header) + len(channels)
    struct.pack_into("<5Q", header, 0x20, data_start, data_start, data_start + len(blocks), 0, 10)
    path = tmp_path / "footerless.pl2"
    path.write_bytes(header + channels + blocks)

    interface = Plexon2EventsInterface(file_path=path)
    assert interface.get_event_type_source_ids() == [
        "Repeated_source12_channel1",
        "Repeated_source13_channel1",
        "source14_channel1",
    ]
    assert interface.get_event_times("Repeated_source12_channel1").tolist() == [30 / 40000]

    selected = Plexon2EventsInterface(
        file_path=path,
        event_extraction_configuration={
            "words": {
                "source": "Repeated_source13_channel1",
                "separation": {"by_payload_fields": ["strobed_word"], "select": [65535, 17, None]},
            },
            "other": {"source": "source14_channel1"},
        },
    )
    assert selected.get_event_type_source_ids() == ["words_65535", "words_17", "words_missing", "other"]
    selected.temporal_alignment["words_65535"].shift_times(2.0)
    metadata = selected.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime(2026, 11, 19, tzinfo=timezone.utc)
    metadata["Events"][selected.metadata_key]["event_types"]["words_65535"]["event_name"] = "Renamed"
    output = tmp_path / "selected.nwb"
    selected.run_conversion(nwbfile_path=output, metadata=metadata)
    with NWBHDF5IO(output, mode="r") as io:
        events = io.read().events
        assert events["Renamed"]["timestamp"][:].tolist() == [(late_tick + 10) / 40000 + 2.0] * 2
        assert events["Renamed"]["strobed_word"][:].tolist() == [65535, 65535]
        assert events["Other"]["timestamp"][:].tolist() == [(late_tick + 50) / 40000]
        assert events["Other"]["strobed_word"][:].tolist() == [32785]
        for name in ("Words17", "WordsMissing"):
            assert events[name]["strobed_word"].data.dtype == np.uint16
            assert len(events[name]) == 0
