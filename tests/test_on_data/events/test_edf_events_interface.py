from datetime import datetime

import numpy as np
import pytest
from pydantic import ValidationError
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.datainterfaces import EDFEventsInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


_EVENTS_PATH = ECEPHY_DATA_PATH / "edf" / "events"


def test_edf_subsecond_annotations_roundtrip(tmp_path):
    interface = EDFEventsInterface(file_path=_EVENTS_PATH / "test_subsecond.edf")
    assert interface.get_metadata()["NWBFile"]["session_start_time"] == datetime(2020, 1, 24, 4, 5, 56, 394531)

    output_path = tmp_path / "subsecond.nwb"
    interface.run_conversion(nwbfile_path=output_path)
    with NWBHDF5IO(path=output_path) as io:
        nwbfile = io.read()
        assert list(nwbfile.events) == ["EDFAnnotations"]
        table = nwbfile.events["EDFAnnotations"]
        assert table.colnames == ("timestamp", "annotation")
        np.testing.assert_allclose(table["timestamp"][:], [1.9511719, 3.4921875, 290.5019531, 583.5722656])
        assert list(table["annotation"][:]) == ["XLSpike", "Clip Note", "XLEvent", "XLSpike"]


def test_edf_mixed_durations_and_shared_timestamps_roundtrip(tmp_path):
    interface = EDFEventsInterface(file_path=_EVENTS_PATH / "event_edge_cases.edf")
    output_path = tmp_path / "edge_cases.nwb"
    interface.run_conversion(nwbfile_path=output_path)
    with NWBHDF5IO(path=output_path) as io:
        table = io.read().events["EDFAnnotations"]
        np.testing.assert_array_equal(table["timestamp"][:], [1, 2, 3, 4, 5, 5, 5, 6, 7.5, 8.25, 9.5])
        np.testing.assert_array_equal(
            table["duration"][:], [np.nan, 0, np.nan, np.nan, np.nan, np.nan, np.nan, 4, 4, np.nan, 20]
        )
        assert list(table["annotation"][:]) == [
            "unicode_cjk 大 (U+5927)",
            "instantaneous_zero_duration",
            "instantaneous_no_duration_field",
            "unicode_math exp(jπ)+1=0",
            "same_onset_first",
            "same_onset_second",
            "same_onset_third",
            "overlapping_epoch_first",
            "overlapping_epoch_second",
            "subsecond_onset",
            "epoch_extends_past_end_of_file",
        ]


def test_bdf_annotation_signals_are_one_text_stream(tmp_path):
    interface = EDFEventsInterface(file_path=_EVENTS_PATH / "event_markers.bdf")
    output_path = tmp_path / "markers.nwb"
    interface.run_conversion(nwbfile_path=output_path)
    with NWBHDF5IO(path=output_path) as io:
        nwbfile = io.read()
        assert list(nwbfile.events) == ["EDFAnnotations"]
        table = nwbfile.events["EDFAnnotations"]
        assert len(table) == 541
        assert list(table["annotation"][:4]) == ["200", "222", "1", "202"]
        np.testing.assert_array_equal(table["timestamp"][:4], [0.5, 1, 1.65, 2.15])
        np.testing.assert_array_equal(table["duration"][:4], [0, 0, 0, 0])


def test_edf_annotation_groups_discover_original_text():
    interface = EDFEventsInterface(
        file_path=_EVENTS_PATH / "test_subsecond.edf",
        event_extraction_configuration={"markers": {"separation": {"by_payload_fields": ["annotation"]}}},
    )
    assert interface.get_event_type_source_ids() == ["markers_XLSpike", "markers_Clip Note", "markers_XLEvent"]
    np.testing.assert_allclose(interface.get_event_times("markers_XLSpike"), [1.9511719, 583.5722656])


def test_edf_annotation_selection_roundtrip_through_converter(tmp_path):
    class Converter(NWBConverter):
        data_interface_classes = {"annotations": EDFEventsInterface}

    converter = Converter(
        source_data={
            "annotations": {
                "file_path": _EVENTS_PATH / "test_subsecond.edf",
                "event_extraction_configuration": {
                    "markers": {
                        "source": "annotations",
                        "separation": {"by_payload_fields": ["annotation"], "select": ["XLSpike", "absent"]},
                    }
                },
            }
        },
    )
    output_path = tmp_path / "selection.nwb"
    converter.run_conversion(nwbfile_path=output_path)
    with NWBHDF5IO(path=output_path) as io:
        events = io.read().events
        assert set(events) == {"MarkersXlspike", "MarkersAbsent"}
        np.testing.assert_allclose(events["MarkersXlspike"]["timestamp"][:], [1.9511719, 583.5722656])
        assert list(events["MarkersXlspike"]["annotation"][:]) == ["XLSpike", "XLSpike"]
        assert len(events["MarkersAbsent"]) == 0
        assert events["MarkersAbsent"]["annotation"].data.dtype.kind == "O"


def test_edf_annotation_selection_requires_text():
    with pytest.raises(ValidationError, match="Input should be a valid string"):
        EDFEventsInterface(
            file_path=_EVENTS_PATH / "event_markers.bdf",
            event_extraction_configuration={
                "markers": {"separation": {"by_payload_fields": ["annotation"], "select": [200]}}
            },
        )


def test_edf_discontinuous_annotations_preserve_full_text(tmp_path):
    source = (_EVENTS_PATH / "event_edge_cases.edf").read_bytes()
    fixed_header = bytearray(source[:256])
    fixed_header[184:192] = b"512     "
    fixed_header[192:197] = b"EDF+D"
    fixed_header[236:244] = b"2       "
    fixed_header[244:252] = b"0       "
    fixed_header[252:256] = b"1   "
    signal_header = bytearray(b" " * 256)
    signal_header[:16] = b"EDF Annotations "
    signal_header[216:224] = b"360     "

    long_text = "  " + "é" * 300 + "  "
    first_record = b"+0.25\x14\x14" + long_text.encode("utf-8") + b"\x14003\x14\x00"
    first_record += b"-0.25\x14before start\x14\x00"
    second_record = b"+12.25\x14\x14\x00+12.375\x150\x14after gap\x14\x00"
    path = tmp_path / "discontinuous.edf"
    path.write_bytes(
        fixed_header + signal_header + first_record.ljust(720, b"\x00") + second_record.ljust(720, b"\x00")
    )

    interface = EDFEventsInterface(file_path=path)
    output_path = tmp_path / "discontinuous.nwb"
    interface.run_conversion(nwbfile_path=output_path)
    with NWBHDF5IO(path=output_path) as io:
        table = io.read().events["EDFAnnotations"]
        assert list(table["annotation"][:]) == ["before start", long_text, "003", "after gap"]
        np.testing.assert_array_equal(table["timestamp"][:], [-0.5, 0, 0, 12.125])
        np.testing.assert_array_equal(table["duration"][:], [np.nan, np.nan, np.nan, 0])
