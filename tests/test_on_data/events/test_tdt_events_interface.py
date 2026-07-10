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
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

TDT_DATA_PATH = ECEPHY_DATA_PATH / "tdt"

# A tank with one onset-only strobe store, PAB_: 30 events whose data codes cycle through [16, 2064, 0].
PAYLOAD_TANK = str(TDT_DATA_PATH / "epocs_with_payload")

# A tank with a 235-event onset-only counter store (Tick) plus three durative stores (s1s_/s4s_/sms_),
# each carrying real STRON/STROFF offset durations, which the interface does not support yet.
OFFSETS_TANK = str(TDT_DATA_PATH / "epocs_with_offsets_1")
DURATIVE_STORES = ["s1s_", "s4s_", "sms_"]

# The anonymized tanks share this fixed session start date.
ANONYMIZED_SESSION_START = "1970-01-12T13:46:40+00:00"


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


class TestTDTEventsCounter:
    """A counter (onset-only, timestamp-only) store: ``Tick`` in ``epocs_with_offsets_1``, with the
    tank's durative stores excluded so only the writable counter remains."""

    @pytest.fixture
    def interface(self):
        return TDTEventsInterface(folder_path=OFFSETS_TANK, exclude_events=DURATIVE_STORES)

    def test_session_start_time(self, interface):
        assert interface.get_metadata()["NWBFile"]["session_start_time"] == ANONYMIZED_SESSION_START

    def test_lists_counter_epoc(self, interface):
        event_types = interface.get_metadata()["Events"]["tdt_events"]["event_types"]
        assert set(event_types.keys()) == {"Tick"}
        entry = event_types["Tick"]
        assert entry["event_name"] == "Tick"
        assert entry.get("columns", {}) == {}  # a counter store is timestamp-only, so no value columns

    def test_exclude_events(self):
        # Excluding every store leaves no event types.
        interface = TDTEventsInterface(folder_path=OFFSETS_TANK, exclude_events=DURATIVE_STORES + ["Tick"])
        assert interface.get_metadata()["Events"]["tdt_events"]["event_types"] == {}

    def test_metadata_key_default_and_override(self, interface):
        # No EventTables block is seeded: a solo store names its own table from event_name, so
        # metadata["Events"] holds only the per-interface metadata_key block.
        assert set(interface.get_metadata()["Events"].keys()) == {"tdt_events"}

        renamed = TDTEventsInterface(folder_path=OFFSETS_TANK, exclude_events=DURATIVE_STORES, metadata_key="my_tank")
        assert set(renamed.get_metadata()["Events"].keys()) == {"my_tank"}

    def test_metadata_schema_is_valid(self, interface):
        Draft7Validator.check_schema(interface.get_metadata_schema())

    def test_add_to_nwbfile_writes_events(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        tick_events = nwbfile.get_events_table("Tick")  # "Tick" has no underscore, so it stays verbatim
        assert isinstance(tick_events, EventsTable)
        assert tick_events.colnames == ("timestamp",)
        assert len(tick_events) == 235

    def test_round_trip(self, interface, tmp_path):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        nwbfile_path = tmp_path / "test_tdt_events.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_events = io.read().get_events_table("Tick")
            assert isinstance(read_events, EventsTable)
            assert len(read_events) == 235


class TestTDTEventsStrobe:
    """The ``PAB_`` strobe store in ``epocs_with_payload``: 30 events whose codes cycle [16, 2064, 0]."""

    @pytest.fixture
    def interface(self):
        return TDTEventsInterface(folder_path=PAYLOAD_TANK)

    def test_get_events(self, interface):
        events = interface.get_events()
        assert set(events) == {"PAB_"}
        for array in events["PAB_"].values():
            assert len(array) == 30

    def test_metadata_seeds_strobe_labels(self, interface):
        metadata = interface.get_metadata()
        entry = metadata["Events"]["tdt_events"]["event_types"]["PAB_"]
        # The PAB_ store gets one categorical 'strobe' column (keyed by its payload field); the three
        # distinct codes are seeded as an editable raw-code -> label map.
        strobe = entry["columns"]["strobe"]
        assert strobe["column_categories"]["labels"] == {0: "0", 16: "16", 2064: "2064"}
        assert strobe["column_name"] == "strobe"
        # The type names its own (solo) table from event_name and carries its description; no EventTables
        # entry is seeded (the writer drops the trailing padding "_", so the table object is "PAB").
        assert entry["event_name"] == "PAB_"
        assert entry["event_description"] == "Onset times of the TDT epoc 'PAB_', labeled by strobe value."
        assert "EventTables" not in metadata["Events"]

    def test_add_to_nwbfile_writes_labeled_events(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        pab_events = nwbfile.get_events_table("PAB")  # "PAB_" store, trailing padding "_" dropped
        assert isinstance(pab_events, EventsTable)
        assert len(pab_events) == 30
        # The 30 events cycle through the three codes.
        assert list(pab_events["strobe"][:]) == ["16", "2064", "0"] * 10

    def test_user_relabeling_round_trip(self, interface, tmp_path):
        metadata = interface.get_metadata()
        labels = metadata["Events"]["tdt_events"]["event_types"]["PAB_"]["columns"]["strobe"]["column_categories"][
            "labels"
        ]
        labels.update({0: "none", 16: "left", 2064: "right"})
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = tmp_path / "test_tdt_strobe.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_events = io.read().get_events_table("PAB")
            assert isinstance(read_events, EventsTable)
            # Codes [16, 2064, 0] map through the user's relabeling.
            assert list(read_events["strobe"][:]) == ["left", "right", "none"] * 10


class TestTDTEventsDurative:
    """The durative stores in ``epocs_with_offsets_1`` (``s1s_``/``s4s_``/``sms_``) carry real
    STRON/STROFF offsets, written as per-event durations in the table's ``duration`` column."""

    @pytest.fixture
    def interface(self):
        return TDTEventsInterface(folder_path=OFFSETS_TANK, exclude_events=["Tick"])

    def test_add_to_nwbfile_writes_durations(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        # Each store ("s1s_"/"s4s_"/"sms_") becomes a table named from the store (padding "_" dropped,
        # capitalized), carrying a "duration" column of real per-event STROFF durations (~1 s, ~4 s, ~0.25 s).
        for table_name, expected_duration in [("S1s", 1.0), ("S4s", 4.0), ("Sms", 0.25)]:
            table = nwbfile.get_events_table(table_name)
            assert isinstance(table, EventsTable)
            assert table.colnames == ("timestamp", "duration")
            assert len(table) == 5
            assert np.allclose(table["duration"][:], expected_duration, atol=0.01)
