from datetime import datetime, timezone

import numpy as np
import pytest
from jsonschema.validators import Draft7Validator
from pynwb import NWBHDF5IO
from pynwb.event import EventsTable
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

    def test_default_lists_all_epocs(self, interface):
        event_types = interface.get_metadata()["Events"]["tdt_events"]["event_types"]
        assert set(event_types.keys()) == set(EPOC_NAME_TO_LENGTH)
        for epoc_name, entry in event_types.items():
            # Photo_249 stores are all counters (timestamp-only), so no value columns.
            assert entry["event_name"] == epoc_name
            assert entry.get("columns", {}) == {}

    def test_exclude_events(self):
        interface = TDTEventsInterface(folder_path=TDT_TANK_PATH, exclude_events=["LNRW", "LNnR"])
        event_types = interface.get_metadata()["Events"]["tdt_events"]["event_types"]
        assert set(event_types.keys()) == {"PrtR", "RNPS"}

    def test_metadata_key_default_and_override(self):
        interface = TDTEventsInterface(folder_path=TDT_TANK_PATH)
        # No EventTables block is seeded: each store is a solo table named from its event_name, so
        # metadata["Events"] holds only the per-interface metadata_key block.
        assert set(interface.get_metadata()["Events"].keys()) == {"tdt_events"}

        interface = TDTEventsInterface(folder_path=TDT_TANK_PATH, metadata_key="my_tank")
        events_metadata = interface.get_metadata()["Events"]
        assert set(events_metadata.keys()) == {"my_tank"}
        assert set(events_metadata["my_tank"]["event_types"].keys()) == set(EPOC_NAME_TO_LENGTH)

    def test_metadata_schema_is_valid(self, interface):
        Draft7Validator.check_schema(interface.get_metadata_schema())

    def test_add_to_nwbfile_writes_events(self, interface):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        prtr_events = nwbfile.get_events_table("PrtR")
        assert isinstance(prtr_events, EventsTable)
        assert prtr_events.colnames == ("timestamp",)
        assert len(prtr_events) == 49

    def test_real_offset_raises(self, interface, monkeypatch):
        # A real (buddy) offset store has falling edges strictly inside each interval, so the
        # synthesized-fill check fails and the unsupported case raises.
        fake_block = _FakeBlock(
            {
                "PrtR": _FakeEpoc(
                    np.array([1.0, 2.0, 3.0]),
                    np.array([1.5, 2.5, 3.5]),
                    np.array([1.0, 2.0, 3.0]),
                )
            }
        )
        monkeypatch.setattr(interface, "load", lambda **kwargs: fake_block)
        # The raise happens in _get_events_data_dict, so the value columns are never read; the entry just
        # needs the required event_name/event_description to get past table-identity resolution.
        metadata = {
            "Events": {"tdt_events": {"event_types": {"PrtR": {"event_name": "PrtR", "event_description": "d"}}}}
        }
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
            read_events = read_nwbfile.get_events_table("LNnR")
            assert isinstance(read_events, EventsTable)
            assert len(read_events) == 1457


class TestTDTEventsStrobeInterface:
    """Covers the ``PAB_`` strobe store in the Photometry-161823 stubbed tank."""

    @pytest.fixture
    def interface(self):
        return TDTEventsInterface(folder_path=STROBE_TANK_PATH, exclude_events=["Vid1", "Tick"])

    def test_metadata_seeds_strobe_labels(self, interface):
        metadata = interface.get_metadata()
        column = metadata["Events"]["tdt_events"]["event_types"]["PAB_"]
        # The PAB_ store gets one categorical 'strobe' column (keyed by its payload field); the three
        # distinct codes are seeded as an editable raw-code -> label map.
        strobe = column["columns"]["strobe"]
        assert strobe["column_categories"]["labels"] == {0: "0", 16: "16", 2064: "2064"}
        assert strobe["column_name"] == "strobe"
        # The type names its own (solo) table from event_name and carries its description; no EventTables
        # entry is seeded (the writer keeps the raw store name "PAB_" verbatim as the table object name).
        assert column["event_name"] == "PAB_"
        assert column["event_description"] == "Onset times of the TDT epoc 'PAB_', labeled by strobe value."
        assert "EventTables" not in metadata["Events"]

    def test_counter_store_has_no_labels(self):
        interface = TDTEventsInterface(folder_path=STROBE_TANK_PATH, exclude_events=["PAB_", "Vid1"])
        column = interface.get_metadata()["Events"]["tdt_events"]["event_types"]["Tick"]
        assert column.get("columns", {}) == {}

    def test_add_to_nwbfile_writes_labeled_events(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        pab_events = nwbfile.get_events_table("PAB_")
        assert isinstance(pab_events, EventsTable)
        assert len(pab_events) == 5
        # The categorical 'strobe' column carries the per-event strobe codes [16, 2064, 0, 16, 2064].
        assert list(pab_events["strobe"][:]) == ["16", "2064", "0", "16", "2064"]

    def test_user_relabeling_round_trip(self, interface, tmp_path):
        metadata = interface.get_metadata()
        column = metadata["Events"]["tdt_events"]["event_types"]["PAB_"]
        column["columns"]["strobe"]["column_categories"]["labels"] = {0: "none", 16: "left", 2064: "right"}
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = tmp_path / "test_tdt_strobe.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_events = io.read().get_events_table("PAB_")
            assert isinstance(read_events, EventsTable)
            # Codes [16, 2064, 0, 16, 2064] map through the user's relabeling.
            assert list(read_events["strobe"][:]) == [
                "left",
                "right",
                "none",
                "left",
                "right",
            ]
