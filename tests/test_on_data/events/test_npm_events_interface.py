import numpy as np
import pytest
from pydantic import ValidationError
from pynwb.event import EventsTable
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import NPMEventsInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH

NPM_EVENTS_PATH = OPHYS_DATA_PATH / "events_datasets" / "NPM"


class TestNPMEventsInterface:
    """NPMEventsInterface is a thin CSVEventsInterface that fixes the two NPM columns (onset time,
    event-type label) and forwards time_unit. These tests exercise that delta against the real gin
    fixtures prepared for the interface, one per label dtype (string, numeric code, boolean, single
    type). Each distinct label becomes its own EventsTable, named by CamelCasing an all-lowercase label
    (whitenoise -> Whitenoise) but keeping a numeric/boolean label verbatim (1 -> "1", True -> "True")."""

    @pytest.fixture
    def string_interface(self):
        file_path = NPM_EVENTS_PATH / "event_type_as_string" / "bl72bl82_12feb2024_stimuli.csv"
        return NPMEventsInterface(file_path=file_path)

    @pytest.fixture
    def number_interface(self):
        file_path = NPM_EVENTS_PATH / "event_type_as_number" / "ttls.csv"
        return NPMEventsInterface(file_path=file_path)

    @pytest.fixture
    def bool_interface(self):
        file_path = NPM_EVENTS_PATH / "event_type_as_bool" / "PagCeAVgatFear_1442_ts0.csv"
        return NPMEventsInterface(file_path=file_path)

    @pytest.fixture
    def single_type_interface(self):
        file_path = NPM_EVENTS_PATH / "single_event_type" / "PagCeAVgatFear_1512_ts0.csv"
        return NPMEventsInterface(file_path=file_path)

    def test_string_labels(self, string_interface):
        """String labels: two stimulus types split into two EventsTables, all-lowercase labels
        CamelCased into the table object names."""
        assert list(string_interface.get_metadata()["Events"]["bl72bl82_12feb2024_stimuli"]["event_types"]) == [
            "whitenoise",
            "pinknoise",
        ]

        nwbfile = mock_NWBFile()
        string_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=string_interface.get_metadata())

        assert set(nwbfile.events.keys()) == {"Whitenoise", "Pinknoise"}
        whitenoise_table = nwbfile.get_events_table("Whitenoise")
        assert isinstance(whitenoise_table, EventsTable)
        assert whitenoise_table.colnames == ("timestamp",)
        np.testing.assert_allclose(
            whitenoise_table["timestamp"][:], [49926132.47, 50895334.07, 51622233.11], rtol=0, atol=1e-6
        )
        np.testing.assert_allclose(
            nwbfile.get_events_table("Pinknoise")["timestamp"][:],
            [49956358.72, 50531909.04, 51107373.17],
            rtol=0,
            atol=1e-6,
        )

    def test_numeric_labels(self, number_interface):
        """Numeric code labels: codes 1 and 3 split into two tables kept verbatim as "1" and "3"."""
        assert list(number_interface.get_metadata()["Events"]["ttls"]["event_types"]) == ["1", "3"]

        nwbfile = mock_NWBFile()
        number_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=number_interface.get_metadata())

        assert set(nwbfile.events.keys()) == {"1", "3"}
        np.testing.assert_allclose(
            nwbfile.get_events_table("1")["timestamp"][:],
            [
                35727623.424000002,
                35747641.088,
                35979698.585600004,
                35999721.267200001,
                36231782.796800002,
                36251805.504000001,
                36483858.892800003,
                36503881.472000003,
                36735943.104000002,
                36755969.843199998,
            ],
            rtol=0,
            atol=1e-6,
        )
        np.testing.assert_allclose(
            nwbfile.get_events_table("3")["timestamp"][:],
            [
                35767655.411200002,
                35769662.604800001,
                36019735.603200004,
                36021746.867200002,
                36271823.782400005,
                36273831.155200005,
                36523903.872000001,
                36525907.123199999,
                36775988.2368,
                36777987.225600004,
            ],
            rtol=0,
            atol=1e-6,
        )

    def test_bool_labels(self, bool_interface):
        """Boolean labels: pandas parses the True/False column as bools, so each becomes an event type
        named verbatim "True"/"False" -- documents how the interface handles a boolean label column."""
        assert list(bool_interface.get_metadata()["Events"]["PagCeAVgatFear_1442_ts0"]["event_types"]) == [
            "True",
            "False",
        ]

        nwbfile = mock_NWBFile()
        bool_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=bool_interface.get_metadata())

        assert set(nwbfile.events.keys()) == {"True", "False"}
        np.testing.assert_allclose(
            nwbfile.get_events_table("True")["timestamp"][:],
            [24233.706688, 24348.892736, 24440.805728, 24558.94976, 24656.243808],
            rtol=0,
            atol=1e-6,
        )
        np.testing.assert_allclose(
            nwbfile.get_events_table("False")["timestamp"][:],
            [24261.742688, 24376.91072, 24468.843712, 24586.99376, 24684.305792],
            rtol=0,
            atol=1e-6,
        )

    def test_single_event_type(self, single_type_interface):
        """A file whose label column is a single constant code is one event type "1" -- the fixed
        event-type column always splits by label, so it is one table named after that label."""
        assert list(single_type_interface.get_metadata()["Events"]["PagCeAVgatFear_1512_ts0"]["event_types"]) == ["1"]

        nwbfile = mock_NWBFile()
        single_type_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=single_type_interface.get_metadata())

        assert set(nwbfile.events.keys()) == {"1"}
        np.testing.assert_allclose(
            nwbfile.get_events_table("1")["timestamp"][:],
            [
                40436705.7152,
                40464720.704,
                40543575.7568,
                40571615.3472,
                40637574.912,
                40665630.9248,
                40736289.344,
                40764337.088,
                40845146.112,
                40873157.056,
            ],
            rtol=0,
            atol=1e-6,
        )

    def test_metadata_key_defaults_to_file_stem(self, string_interface):
        """With no metadata_key, NPM inherits CSVEventsInterface's default: the file stem."""
        metadata = string_interface.get_metadata()
        assert "bl72bl82_12feb2024_stimuli" in metadata["Events"]
        assert list(metadata["Events"]["bl72bl82_12feb2024_stimuli"]["event_types"]) == ["whitenoise", "pinknoise"]

    def test_time_unit_forwarded(self):
        """time_unit is forwarded to CSVEventsInterface, dividing the raw onset times by 1000."""
        file_path = NPM_EVENTS_PATH / "event_type_as_string" / "bl72bl82_12feb2024_stimuli.csv"
        interface = NPMEventsInterface(file_path=file_path, time_unit="milliseconds")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        np.testing.assert_allclose(
            nwbfile.get_events_table("Whitenoise")["timestamp"][:],
            [49926.13247, 50895.33407, 51622.23311],
            rtol=0,
            atol=1e-9,
        )

    def test_invalid_time_unit_raises(self):
        """time_unit is restricted to the known units by the Literal annotation."""
        file_path = NPM_EVENTS_PATH / "event_type_as_string" / "bl72bl82_12feb2024_stimuli.csv"
        with pytest.raises(ValidationError):
            NPMEventsInterface(file_path=file_path, time_unit="nanoseconds")
