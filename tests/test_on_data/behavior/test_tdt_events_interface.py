from datetime import datetime, timezone

import ndx_events
import pytest
from jsonschema.validators import Draft7Validator
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import TDTEventsInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH

TDT_TANK_PATH = str(OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT" / "Photo_249_391-200721-120136_stubbed")
# Epoc onset lengths in the Photo_249 stubbed tank.
EPOC_NAME_TO_LENGTH = {"PrtR": 49, "RNPS": 11, "LNRW": 50, "LNnR": 1457}


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
        events_metadata = interface.get_metadata()["Behavior"]["TDTEvents"]["Events"]
        epoc_names = {event["epoc_name"] for event in events_metadata}
        assert epoc_names == set(EPOC_NAME_TO_LENGTH)
        for event in events_metadata:
            assert event["name"] == event["epoc_name"]

    def test_selected_event_names(self):
        interface = TDTEventsInterface(folder_path=TDT_TANK_PATH, event_names=["PrtR", "RNPS"])
        events_metadata = interface.get_metadata()["Behavior"]["TDTEvents"]["Events"]
        epoc_names = [event["epoc_name"] for event in events_metadata]
        assert epoc_names == ["PrtR", "RNPS"]

    def test_metadata_schema_is_valid(self, interface):
        Draft7Validator.check_schema(interface.get_metadata_schema())

    def test_add_to_nwbfile_writes_events(self, interface):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        behavior_module = nwbfile.processing["behavior"]
        prtr_events = behavior_module.data_interfaces["PrtR"]
        assert isinstance(prtr_events, ndx_events.Events)
        assert len(prtr_events.timestamps) == 49

    def test_round_trip(self, interface, tmp_path):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = tmp_path / "test_tdt_events.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()
            read_events = read_nwbfile.processing["behavior"].data_interfaces["LNnR"]
            assert isinstance(read_events, ndx_events.Events)
            assert len(read_events.timestamps) == 1457
