import hashlib

import numpy as np
import pytest
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import AxonEventsInterface
from neuroconv.tools.testing.data_interface_mixins import EventsInterfaceTestMixin

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

TAG_PATH = ECEPHY_DATA_PATH / "axon" / "intracellular_data" / "tags"


class TestAxonEventsInterface(EventsInterfaceTestMixin):
    data_interface_cls = AxonEventsInterface
    interface_kwargs = {"file_path": TAG_PATH / "time_and_comment.abf"}
    expected_temporal_alignment_keys = ("tags_time", "tags_comment")

    def test_mixed_tag_types(self):
        interface = self.data_interface_cls(**self.interface_kwargs)
        tables = interface.create_nwbfile().events
        assert set(tables) == {"TimeAndCommentAxonEventsTagsTime", "TimeAndCommentAxonEventsTagsComment"}
        for kind, timestamp in [("time", 3.357), ("comment", 5.557)]:
            table = tables[f"TimeAndCommentAxonEventsTags{kind.title()}"]
            np.testing.assert_allclose(table["timestamp"][:], [timestamp])
            assert list(table["tag_type"][:]) == [kind]
            assert "tag_time" not in table.colnames


def test_between_sweeps():
    for name in ("abf1.abf", "abf2.abf"):
        interface = AxonEventsInterface(file_path=TAG_PATH / name)
        (table,) = interface.create_nwbfile().events.values()
        np.testing.assert_allclose(table["timestamp"][:], [173.9776, 294.8608])
        assert list(table["comment"][:]) == ["+TGOT", "-TGOT"]
        assert list(table["sweep_index"][:]) == [-1, -1]


def test_combined_table_after_alignment():
    interface = AxonEventsInterface(
        file_path=TAG_PATH / "time_and_comment.abf", event_extraction_configuration={"tags": {}}
    )
    interface.temporal_alignment["tags"].set_times([7.0, 6.0])
    (table,) = interface.create_nwbfile().events.values()
    assert list(table["timestamp"][:]) == [6.0, 7.0]
    assert list(table["tag_type"][:]) == ["comment", "time"]


def test_separation_and_empty_selection():
    configuration = {"markers": {"separation": {"by_payload_fields": ["tag_type"], "select": ["comment", "external"]}}}
    interface = AxonEventsInterface(
        file_path=TAG_PATH / "time_and_comment.abf", event_extraction_configuration=configuration
    )
    assert interface.get_event_type_source_ids() == ["markers_comment", "markers_external"]
    assert len(interface.get_event_times("markers_external")) == 0
    table = interface.create_nwbfile().events["TimeAndCommentAxonEventsMarkersComment"]
    assert list(table["tag_type"][:]) == ["comment"]


def test_two_field_selection():
    configuration = {
        "markers": {
            "source": "tags",
            "separation": {
                "by_payload_fields": ["tag_type", "comment"],
                "select": [{"tag_type": "time", "comment": None}],
            },
        }
    }
    interface = AxonEventsInterface(
        file_path=TAG_PATH / "time_and_comment.abf", event_extraction_configuration=configuration
    )
    assert len(interface.get_event_times("markers_time_missing")) == 1


def test_missing_source_and_wrong_value_type():
    with pytest.raises(ValueError, match="available sources"):
        AxonEventsInterface(
            file_path=TAG_PATH / "time_and_comment.abf", event_extraction_configuration={"x": {"source": "other"}}
        )
    configuration = {"x": {"source": "tags", "separation": {"by_payload_fields": ["tag_type"], "select": [1]}}}
    with pytest.raises(ValueError, match="recorded values have type"):
        AxonEventsInterface(file_path=TAG_PATH / "time_and_comment.abf", event_extraction_configuration=configuration)


def test_compressed_voice():
    interface = AxonEventsInterface(file_path=TAG_PATH / "voice_compressed.abf")
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile)
    voice = next(iter(nwbfile.acquisition.values()))
    assert voice.rate == 11025
    assert voice.offset == -1
    assert voice.conversion == 1 / 128
    assert hashlib.sha256(voice.data.tobytes()).hexdigest() == (
        "3674223f57c3640f672a64df4d2d2d5bbcedab32cfc362f53ae0e1e9b8b64651"
    )


def test_untagged_file_and_empty_selection_round_trip(tmp_path):
    untagged = TAG_PATH.parent / "abf2_zero_current_clamp.abf"
    interface = AxonEventsInterface(file_path=untagged)
    assert interface.get_event_type_source_ids() == []
    interface.run_conversion(nwbfile_path=tmp_path / "untagged.nwb")
    with NWBHDF5IO(tmp_path / "untagged.nwb", "r") as io:
        assert not io.read().events
    configuration = {"markers": {"separation": {"by_payload_fields": ["tag_type"], "select": ["external"]}}}
    interface = AxonEventsInterface(
        file_path=TAG_PATH / "time_and_comment.abf", event_extraction_configuration=configuration
    )
    interface.run_conversion(nwbfile_path=tmp_path / "empty.nwb")
    with NWBHDF5IO(tmp_path / "empty.nwb", "r") as io:
        (table,) = io.read().events.values()
        assert len(table) == 0
        assert table["tag_type"].data.asstr()[:].tolist() == []


def test_overlapping_selections_share_voice_acquisition():
    configuration = {
        "all_tags": {},
        "voice": {"separation": {"by_payload_fields": ["tag_type"], "select": ["voice"]}},
    }
    interface = AxonEventsInterface(
        file_path=TAG_PATH / "annotation_and_voice_uncompressed.abf", event_extraction_configuration=configuration
    )
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile)
    assert len(nwbfile.acquisition) == 1
    name = next(iter(nwbfile.acquisition))
    event = interface._get_events_data_dict()["voice_voice"]
    assert event.payload["voice_series_name"][0] == name


def test_distinct_metadata_keys_name_distinct_tables():
    first = AxonEventsInterface(file_path=TAG_PATH / "time_and_comment.abf", metadata_key="first")
    second = AxonEventsInterface(file_path=TAG_PATH / "time_and_comment.abf", metadata_key="second")
    nwbfile = mock_NWBFile()
    first.add_to_nwbfile(nwbfile)
    second.add_to_nwbfile(nwbfile)
    assert set(nwbfile.events) == {"FirstTagsTime", "FirstTagsComment", "SecondTagsTime", "SecondTagsComment"}


def test_voice_and_annotation_round_trip(tmp_path):
    file_path = TAG_PATH / "annotation_and_voice_uncompressed.abf"
    interface = AxonEventsInterface(file_path=file_path)
    interface.temporal_alignment.shift_times(2.0)
    output_path = tmp_path / "voice.nwb"
    interface.run_conversion(nwbfile_path=output_path)
    with NWBHDF5IO(output_path, "r") as io:
        nwbfile = io.read()
        annotation_table = nwbfile.events["AnnotationAndVoiceUncompressedAxonEventsTagsAnnotation"]
        assert annotation_table["comment"][0] == "annotation tag"
        assert annotation_table["annotation"][0] == "Generated with abffio.dll: annotation text for tag 3"
        voice_table = nwbfile.events["AnnotationAndVoiceUncompressedAxonEventsTagsVoice"]
        voice_name = voice_table["voice_series_name"][0]
        voice = nwbfile.acquisition[voice_name]
        assert voice.starting_time == voice_table["timestamp"][0] == 3.5
        assert voice.rate == 8000
        assert voice.conversion == 1 / 32768
        assert voice.data.shape == (4000, 1)
        np.testing.assert_array_equal(voice.data[:4, 0], [0, 2709, 5099, 6885])


def test_discovery_and_missing_fields():
    file_path = TAG_PATH / "annotation_and_voice_uncompressed.abf"
    assert AxonEventsInterface.get_available_event_sources(file_path) == ["tags"]
    configuration = {
        "missing": {
            "separation": {
                "by_payload_fields": ["comment", "annotation"],
                "select": [{"comment": None, "annotation": None}],
            }
        }
    }
    interface = AxonEventsInterface(file_path=file_path, event_extraction_configuration=configuration)
    (table,) = interface.create_nwbfile().events.values()
    assert list(table["tag_type"][:]) == ["time"]


def test_unselected_voice_does_not_write_audio():
    interface = AxonEventsInterface(file_path=TAG_PATH / "annotation_and_voice_uncompressed.abf")
    metadata = interface.get_metadata()
    metadata["Events"][interface.metadata_key]["event_types"].clear()
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile, metadata=metadata)
    assert len(nwbfile.acquisition) == 0


def test_overlapping_voice_with_conflicting_alignment_raises_before_writing():
    configuration = {"all_tags": {}, "voice": {"separation": {"by_payload_fields": ["tag_type"], "select": ["voice"]}}}
    interface = AxonEventsInterface(
        file_path=TAG_PATH / "annotation_and_voice_uncompressed.abf", event_extraction_configuration=configuration
    )
    interface.temporal_alignment["voice_voice"].shift_times(2.0)
    nwbfile = mock_NWBFile()
    with pytest.raises(ValueError, match="conflicting aligned times"):
        interface.add_to_nwbfile(nwbfile)
    assert len(nwbfile.events) == 0
    assert len(nwbfile.acquisition) == 0


def test_missing_identifier_fallback_is_per_field(monkeypatch):
    from neuroconv.datainterfaces.icephys.axon import axoneventsinterface

    reader = axoneventsinterface.read_abf_tags(TAG_PATH / "annotation_and_voice_uncompressed.abf")
    reader.tags["comment"][1] = "missing"
    monkeypatch.setattr(axoneventsinterface, "read_abf_tags", lambda file_path: reader)
    configuration = {"x": {"separation": {"by_payload_fields": ["comment", "annotation"]}}}
    with pytest.warns(UserWarning, match="not_recorded"):
        interface = AxonEventsInterface(
            file_path=TAG_PATH / "annotation_and_voice_uncompressed.abf", event_extraction_configuration=configuration
        )
    identifiers = interface.get_event_type_source_ids()
    assert "x_not_recorded_missing" in identifiers
    assert "x_missing_missing" in identifiers
