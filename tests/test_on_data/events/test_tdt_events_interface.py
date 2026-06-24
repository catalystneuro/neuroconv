from datetime import datetime, timezone

import ndx_events
import numpy as np
import pytest
from jsonschema.validators import Draft7Validator
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import TDTEventsInterface
from neuroconv.datainterfaces.events.tdt_events.tdteventsdatainterface import (
    _data_is_counter,
    _offset_is_synthesized,
)

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH

TDT_DATA_PATH = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT"
TDT_TANK_PATH = str(TDT_DATA_PATH / "Photo_249_391-200721-120136_stubbed")
# Epoc onset lengths in the Photo_249 stubbed tank.
EPOC_NAME_TO_LENGTH = {"PrtR": 49, "RNPS": 11, "LNRW": 50, "LNnR": 1457}

# A stubbed tank with a real strobe store, ``PAB_``: 5 events with codes [16, 2064, 0, 16, 2064].
STROBE_TANK_PATH = str(TDT_DATA_PATH / "Photometry-161823_stubbed")


class _FakeEpoc:
    """Minimal stand-in for a ``tdt`` epoc store, exposing the onset/offset/data arrays."""

    def __init__(self, onset, offset, data):
        self.onset = onset
        self.offset = offset
        self.data = data


class _FakeBlock:
    """Minimal stand-in for a ``tdt.read_block`` result, exposing an ``epocs`` mapping."""

    def __init__(self, epocs):
        self.epocs = epocs


class TestDetectors:
    def test_synthesized_offset_is_detected(self):
        onset = np.array([1.0, 2.0, 3.0])
        offset = np.array([2.0, 3.0, np.inf])  # TDT fill: offset[i] == onset[i + 1], last is inf
        assert _offset_is_synthesized(onset, offset)

    def test_real_offset_is_not_synthesized(self):
        onset = np.array([1.0, 2.0, 3.0])
        offset = np.array([1.5, 2.5, 3.5])  # genuine falling edges strictly inside each interval
        assert not _offset_is_synthesized(onset, offset)

    def test_single_event_offset_is_synthesized(self):
        onset = np.array([1.0])
        offset = np.array([np.inf])
        assert _offset_is_synthesized(onset, offset)

    def test_counter_data_is_detected(self):
        assert _data_is_counter(np.array([1.0, 2.0, 3.0, 4.0]))
        assert _data_is_counter(np.array([0.0, 1.0, 2.0]))

    def test_strobe_codes_are_not_a_counter(self):
        assert not _data_is_counter(np.array([16.0, 2064.0, 0.0, 16.0]))


class TestTDTEventsInterface:
    @pytest.fixture
    def interface(self):
        return TDTEventsInterface(folder_path=TDT_TANK_PATH)

    def test_get_events(self, interface):
        events = interface.get_events()
        for epoc_name, event in events.items():
            expected_length = EPOC_NAME_TO_LENGTH[epoc_name]
            assert len(event["onset"]) == expected_length
            assert len(event["offset"]) == expected_length
            assert len(event["data"]) == expected_length

    def test_session_start_time(self, interface):
        metadata = interface.get_metadata()
        expected = datetime(2020, 7, 21, 17, 2, 24, 999999, tzinfo=timezone.utc).isoformat()
        assert metadata["NWBFile"]["session_start_time"] == expected

    def test_default_event_names_lists_all_epocs(self, interface):
        events_metadata = interface.get_metadata()["Events"]["TDTEvents"]
        assert set(events_metadata.keys()) == set(EPOC_NAME_TO_LENGTH)
        for epoc_name, event in events_metadata.items():
            assert event["name"] == epoc_name

    def test_selected_event_names(self):
        interface = TDTEventsInterface(folder_path=TDT_TANK_PATH, event_names=["PrtR", "RNPS"])
        events_metadata = interface.get_metadata()["Events"]["TDTEvents"]
        assert list(events_metadata.keys()) == ["PrtR", "RNPS"]

    def test_metadata_key_default_and_override(self):
        interface = TDTEventsInterface(folder_path=TDT_TANK_PATH)
        assert set(interface.get_metadata()["Events"].keys()) == {"TDTEvents"}

        interface = TDTEventsInterface(folder_path=TDT_TANK_PATH, metadata_key="my_tank")
        events_metadata = interface.get_metadata()["Events"]
        assert set(events_metadata.keys()) == {"my_tank"}
        assert set(events_metadata["my_tank"].keys()) == set(EPOC_NAME_TO_LENGTH)

    def test_metadata_schema_is_valid(self, interface):
        Draft7Validator.check_schema(interface.get_metadata_schema())

    def test_add_to_nwbfile_writes_events(self, interface):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        prtr_events = nwbfile.acquisition["PrtR"]
        assert isinstance(prtr_events, ndx_events.Events)
        assert len(prtr_events.timestamps) == 49

    def test_real_offset_raises(self, interface, monkeypatch):
        # A real (buddy) offset store has falling edges strictly inside each interval, so the
        # synthesized-fill check fails and the unsupported case raises.
        fake_block = _FakeBlock(
            {"PrtR": _FakeEpoc(np.array([1.0, 2.0, 3.0]), np.array([1.5, 2.5, 3.5]), np.array([1.0, 2.0, 3.0]))}
        )
        monkeypatch.setattr(interface, "load", lambda **kwargs: fake_block)
        metadata = {"Events": {"TDTEvents": {"PrtR": {"name": "PrtR", "description": "d"}}}}
        with pytest.raises(NotImplementedError, match=r"real offset.*issues/new"):
            interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)

    def test_round_trip(self, interface, tmp_path):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = tmp_path / "test_tdt_events.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()
            read_events = read_nwbfile.acquisition["LNnR"]
            assert isinstance(read_events, ndx_events.Events)
            assert len(read_events.timestamps) == 1457


class TestTDTEventsStrobeInterface:
    """Covers the ``PAB_`` strobe store in the Photometry-161823 stubbed tank."""

    @pytest.fixture
    def interface(self):
        return TDTEventsInterface(folder_path=STROBE_TANK_PATH, event_names=["PAB_"])

    def test_metadata_seeds_strobe_labels(self, interface):
        entry = interface.get_metadata()["Events"]["TDTEvents"]["PAB_"]
        # The PAB_ store's three distinct codes are seeded as an editable raw-code -> label map.
        assert entry["labels"] == {0: "0", 16: "16", 2064: "2064"}
        assert entry["description"] == "Onset times of the TDT epoc 'PAB_', labeled by strobe value."

    def test_counter_store_has_no_labels(self):
        interface = TDTEventsInterface(folder_path=STROBE_TANK_PATH, event_names=["Tick"])
        entry = interface.get_metadata()["Events"]["TDTEvents"]["Tick"]
        assert "labels" not in entry

    def test_add_to_nwbfile_writes_labeled_events(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        pab_events = nwbfile.acquisition["PAB_"]
        assert isinstance(pab_events, ndx_events.LabeledEvents)
        # labels are ordered by numeric code; data indexes into them, recovering [16, 2064, 0, 16, 2064].
        assert pab_events.labels == ["0", "16", "2064"]
        np.testing.assert_array_equal(pab_events.data, [1, 2, 0, 1, 2])
        assert len(pab_events.timestamps) == 5

    def test_user_relabeling_round_trip(self, interface, tmp_path):
        metadata = interface.get_metadata()
        metadata["Events"]["TDTEvents"]["PAB_"]["labels"] = {0: "none", 16: "left", 2064: "right"}
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = tmp_path / "test_tdt_strobe.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_events = io.read().acquisition["PAB_"]
            assert isinstance(read_events, ndx_events.LabeledEvents)
            assert list(read_events.labels) == ["none", "left", "right"]
            np.testing.assert_array_equal(read_events.data, [1, 2, 0, 1, 2])
