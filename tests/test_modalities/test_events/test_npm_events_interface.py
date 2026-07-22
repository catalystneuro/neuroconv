import pytest
from pydantic import ValidationError
from pynwb.event import EventsTable
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import NPMEventsInterface

# A raw NPM event file is a headerless two-column CSV: onset time (in the recording's raw time base)
# plus an event-type label. Here "stim" fires at 1/3/5 and "noise" at 2/4; each distinct label becomes
# its own EventsTable named after the label ("stim" -> "Stim").
TWO_TYPE_ROWS = [(1.0, "stim"), (2.0, "noise"), (3.0, "stim"), (4.0, "noise"), (5.0, "stim")]

# A legacy NPM session whose label column is a numeric code (all value 1): a single event type "1".
NUMERIC_LABEL_ROWS = [(10.0, 1), (20.0, 1), (30.0, 1)]


class TestNPMEventsInterface:
    """NPMEventsInterface is a thin CSVEventsInterface that fixes the two NPM columns and forwards
    time_unit, so these tests cover only that delta -- the generic CSV events behavior (label
    splitting, metadata schema, session_start_time, round-trip) is covered by the CSV events tests."""

    @pytest.fixture
    def two_type_file(self, tmp_path):
        file_path = tmp_path / "npm_events.csv"
        lines = [f"{onset},{label}" for onset, label in TWO_TYPE_ROWS]
        file_path.write_text("\n".join(lines) + "\n")
        return file_path

    @pytest.fixture
    def numeric_label_file(self, tmp_path):
        file_path = tmp_path / "npm_events_numeric.csv"
        lines = [f"{onset},{label}" for onset, label in NUMERIC_LABEL_ROWS]
        file_path.write_text("\n".join(lines) + "\n")
        return file_path

    @pytest.fixture
    def interface(self, two_type_file):
        return NPMEventsInterface(file_path=two_type_file)

    def test_fixed_headerless_two_columns(self, interface):
        """From only a file_path, the fixed columns 0/1 read the headerless CSV and split it per label
        into one EventsTable each (labels CamelCased). This is the format knowledge the class encodes."""
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert set(nwbfile.events.keys()) == {"Stim", "Noise"}
        stim_table = nwbfile.get_events_table("Stim")
        assert isinstance(stim_table, EventsTable)
        assert stim_table.colnames == ("timestamp",)
        assert list(stim_table["timestamp"][:]) == [1.0, 3.0, 5.0]
        assert list(nwbfile.get_events_table("Noise")["timestamp"][:]) == [2.0, 4.0]

    def test_default_metadata_key(self, interface):
        """NPM namespaces its metadata under "npm_events" by default (not the CSV file-stem default)."""
        assert list(interface.get_metadata()["Events"]["npm_events"]["event_types"]) == ["stim", "noise"]

    def test_time_unit_forwarded(self, two_type_file):
        """time_unit is forwarded to CSVEventsInterface, dividing the raw onset times by 1000."""
        interface = NPMEventsInterface(file_path=two_type_file, time_unit="milliseconds")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert list(nwbfile.get_events_table("Stim")["timestamp"][:]) == pytest.approx([0.001, 0.003, 0.005])

    def test_invalid_time_unit_raises(self, two_type_file):
        """time_unit is restricted to the known units by the Literal annotation."""
        with pytest.raises(ValidationError):
            NPMEventsInterface(file_path=two_type_file, time_unit="nanoseconds")

    def test_numeric_label_file(self, numeric_label_file):
        """A two-column event file with a numeric label column is a single event type '1'."""
        interface = NPMEventsInterface(file_path=numeric_label_file)
        assert list(interface.get_metadata()["Events"]["npm_events"]["event_types"]) == ["1"]

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        assert list(nwbfile.get_events_table("1")["timestamp"][:]) == [10.0, 20.0, 30.0]
