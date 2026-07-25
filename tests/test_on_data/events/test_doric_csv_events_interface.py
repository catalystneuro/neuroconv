import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import DoricCSVEventsInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH

FILE_PATH = OPHYS_DATA_PATH / "events_datasets" / "doric" / "csv_export" / "interval_events.csv"


class TestDoricCSVEvents:
    """DoricCSVEventsInterface edge-detects each Digital I/O column of a DoricStudio CSV export.

    The fixture (``interval_events.csv``) has a grouped two-row header and a single digital column
    ``DI/O-1`` on a ``Time(s)`` clock, carrying three pulses (durations 0.96, 2.0, 2.0 s).
    """

    @pytest.fixture
    def interface(self):
        return DoricCSVEventsInterface(file_path=FILE_PATH)

    def test_get_metadata(self):
        # metadata_key is set on the interface (__init__) and namespaces its events metadata.
        metadata_key = "doric_metadata_key"
        interface = DoricCSVEventsInterface(file_path=FILE_PATH, metadata_key=metadata_key)
        metadata = interface.get_metadata()

        # DI/O-1 keyed by the raw column name (identity-in-header); the human-facing event_name drops
        # the slash (an NWB object name cannot hold "/").
        expected_events_metadata = {
            metadata_key: {
                "event_types": {
                    "DI/O-1": {"event_name": "DIO-1"},
                },
            },
        }
        assert metadata["Events"] == expected_events_metadata

    def test_add_to_nwbfile_default_high_period(self, interface):
        """The default detect is high_period: onset at each rising edge, duration to the falling edge."""
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        events_table = nwbfile.get_events_table("DIO-1")  # "DI/O-1" with the slash dropped
        assert events_table.colnames == ("timestamp", "duration")

        expected_timestamps = [15.9069085, 30.8718085, 45.8699085]  # three pulses (rising edges)
        assert np.allclose(events_table["timestamp"][:], expected_timestamps)

        expected_durations = [0.9628, 2.0003, 2.0003]  # rise-to-fall span of each pulse, in seconds
        assert np.allclose(events_table["duration"][:], expected_durations, atol=1e-4)

    def test_rising_detect_is_onset_only(self):
        """detect='rising' reads point events (onset timestamps only, no duration column)."""
        interface = DoricCSVEventsInterface(file_path=FILE_PATH, event_specs={"DI/O-1": {"detect": "rising"}})
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        events_table = nwbfile.get_events_table("DIO-1")
        assert events_table.colnames == ("timestamp",)
        assert np.allclose(events_table["timestamp"][:], [15.9069085, 30.8718085, 45.8699085])

    def test_unknown_digital_line_raises(self):
        """event_specs naming a column that is not a Digital I/O line fails loudly at construction."""
        with pytest.raises(ValueError, match="not one of the file's lines"):
            DoricCSVEventsInterface(file_path=FILE_PATH, event_specs={"DI/O-9": {"detect": "rising"}})
