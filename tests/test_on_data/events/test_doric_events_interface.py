from datetime import datetime

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import DoricEventsInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH


class TestDoricEventsSingleLine:
    """DoricEventsInterface edge-detects each DigitalIO line of a modern ``.doric`` file.

    ``single_line.doric`` (modern DataAcquisition layout, ~1000 Hz) has one toggling line ``Camera1``
    (six single-sample pulses) and a held-constant line ``DigitalCh1`` (skipped), plus a ``Created``
    session timestamp.
    """

    FILE_PATH = OPHYS_DATA_PATH / "events_datasets" / "doric" / "root_is_data_acquisition" / "single_line.doric"

    @pytest.fixture
    def interface(self):
        return DoricEventsInterface(file_path=self.FILE_PATH)

    def test_get_metadata(self, interface):
        metadata = interface.get_metadata()

        # Only Camera1 is seeded (the constant DigitalCh1 carries no event), named after the line
        # (identity-in-header, no source prose).
        expected_events_metadata = {
            "doric_events": {
                "event_types": {
                    "Camera1": {"event_name": "Camera1"},
                },
            },
        }
        assert metadata["Events"] == expected_events_metadata

        # session_start_time is read from the file's "Created" HDF5 attribute.
        assert metadata["NWBFile"]["session_start_time"] == datetime(2024, 6, 24, 13, 58, 38)

    def test_add_to_nwbfile(self, interface):
        """The default detect is high_period: onset at each rising edge, duration to the falling edge."""
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        camera_events = nwbfile.get_events_table("Camera1")  # kept verbatim (no slash to drop)
        assert camera_events.colnames == ("timestamp", "duration")

        expected_timestamps = [0.002, 0.018, 0.035, 0.051, 0.068, 0.085]  # six rising edges
        assert np.allclose(camera_events["timestamp"][:], expected_timestamps)

        # Single-sample pulses at ~1000 Hz: each high period is one frame (~0.001 s).
        assert np.allclose(camera_events["duration"][:], [0.001] * 6, atol=1e-6)

    def test_rising_detect_is_onset_only(self):
        """detect='rising' reads point events (onset timestamps only, no duration column)."""
        interface = DoricEventsInterface(file_path=self.FILE_PATH, event_specs={"Camera1": {"detect": "rising"}})
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        camera_events = nwbfile.get_events_table("Camera1")
        assert camera_events.colnames == ("timestamp",)
        assert np.allclose(camera_events["timestamp"][:], [0.002, 0.018, 0.035, 0.051, 0.068, 0.085])

    def test_unknown_line_raises(self):
        """event_specs naming a line that is not a DigitalIO line fails loudly at construction."""
        with pytest.raises(ValueError, match="not one of the file's lines"):
            DoricEventsInterface(file_path=self.FILE_PATH, event_specs={"NoSuchLine": {"detect": "rising"}})

    def test_entry_without_detect_raises(self):
        """A half-filled event_specs entry fails at construction rather than falling back to a default."""
        with pytest.raises(ValueError, match="does not set 'detect'"):
            DoricEventsInterface(file_path=self.FILE_PATH, event_specs={"Camera1": {}})


class TestDoricEventsMultiLine:
    """``multi_line.doric`` carries three toggling lines and no embedded session timestamp.

    Lines: ``CAM1`` (three short pulses), ``EXC1`` (one ~23 ms pulse), and ``EXC2`` (two pulses, the
    last still high at the file's end so its high_period duration is ``NaN``, a truncated interval).
    The root carries no ``Created`` attribute, so ``session_start_time`` is not populated.
    """

    FILE_PATH = OPHYS_DATA_PATH / "events_datasets" / "doric" / "root_is_data_acquisition" / "multi_line.doric"

    @pytest.fixture
    def interface(self):
        return DoricEventsInterface(file_path=self.FILE_PATH)

    def test_get_metadata(self):
        # metadata_key is set on the interface (__init__) and namespaces its events metadata.
        metadata_key = "doric_metadata_key"
        interface = DoricEventsInterface(file_path=self.FILE_PATH, metadata_key=metadata_key)
        metadata = interface.get_metadata()

        # Three toggling lines, so three event types are seeded (one EventsTable each), named after the
        # line (identity-in-header, no source prose).
        expected_events_metadata = {
            metadata_key: {
                "event_types": {
                    "CAM1": {"event_name": "CAM1"},
                    "EXC1": {"event_name": "EXC1"},
                    "EXC2": {"event_name": "EXC2"},
                },
            },
        }
        assert metadata["Events"] == expected_events_metadata

    def test_add_to_nwbfile(self, interface):
        """Each toggling line becomes its own EventsTable (one table per line), durative by default."""
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime(2024, 1, 1)  # not in the file; supply for the write
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        events = nwbfile.events

        # One EventsTable per digital line, each named after the line.
        assert set(events.keys()) == {"CAM1", "EXC1", "EXC2"}

        # CAM1: three single-sample pulses.
        cam1 = events["CAM1"]
        assert cam1.colnames == ("timestamp", "duration")
        np.testing.assert_allclose(cam1["timestamp"][:], [0.026, 0.051, 0.076], atol=1e-6)
        np.testing.assert_allclose(cam1["duration"][:], [0.001, 0.001, 0.001], atol=1e-6)

        # EXC1: one ~23 ms pulse.
        exc1 = events["EXC1"]
        assert exc1.colnames == ("timestamp", "duration")
        np.testing.assert_allclose(exc1["timestamp"][:], [0.05], atol=1e-6)
        np.testing.assert_allclose(exc1["duration"][:], [0.023], atol=1e-6)

        # EXC2: two pulses; the last is still high at the file's end, so it has no closing edge and its
        # duration is NaN (a truncated interval).
        exc2 = events["EXC2"]
        assert exc2.colnames == ("timestamp", "duration")
        np.testing.assert_allclose(exc2["timestamp"][:], [0.025, 0.075], atol=1e-6)
        np.testing.assert_allclose(exc2["duration"][:], [0.023, np.nan], atol=1e-6)  # equal_nan by default

    def test_metadata_propagation(self):
        """The editable events metadata reaches each event type by ``metadata_key`` -> its
        ``event_type_source_id`` (the line name, the join key) and sets a friendly ``event_name``, which
        the writer CamelCases into the table's NWB object name, and an ``event_description``, which becomes
        that table's description. Names and descriptions are the whole annotation surface here: these
        events are timestamps (+durations) only, no value column."""
        metadata_key = "doric_metadata_key"

        # Per line, defined once and reused both when setting the metadata and when asserting the result:
        # the source id (the line name) that addresses it, the event_name we set (which CamelCases into
        # the table object name given beside it), and the event_description we set.
        cam_id, cam_name, cam_table = "CAM1", "camera_trigger", "CameraTrigger"
        exc1_id, exc1_name, exc1_table = "EXC1", "excitation_one", "ExcitationOne"
        exc2_id, exc2_name, exc2_table = "EXC2", "excitation_two", "ExcitationTwo"
        cam_description = "Camera trigger pulses."
        exc1_description = "First excitation channel gate."
        exc2_description = "Second excitation channel gate."

        interface = DoricEventsInterface(file_path=self.FILE_PATH, metadata_key=metadata_key)
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime(2024, 1, 1)  # not in the file; supply for the write

        # Reach the event types by metadata_key -> event_type_source_id (the addressing/join keys).
        event_types = metadata["Events"][metadata_key]["event_types"]
        assert set(event_types) == {cam_id, exc1_id, exc2_id}

        event_types[cam_id]["event_name"] = cam_name
        event_types[cam_id]["event_description"] = cam_description
        event_types[exc1_id]["event_name"] = exc1_name
        event_types[exc1_id]["event_description"] = exc1_description
        event_types[exc2_id]["event_name"] = exc2_name
        event_types[exc2_id]["event_description"] = exc2_description

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        events = nwbfile.events

        # Each event_name CamelCases into its table's NWB object name; the line names are the addressing
        # keys, not the table names.
        assert set(events.keys()) == {cam_table, exc1_table, exc2_table}
        assert events[cam_table].description == cam_description
        assert events[exc1_table].description == exc1_description
        assert events[exc2_table].description == exc2_description

    def test_selection_by_inclusion(self):
        """Naming one line derives only that line; the others are not written."""
        interface = DoricEventsInterface(file_path=self.FILE_PATH, event_specs={"CAM1": {"detect": "high_period"}})
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime(2024, 1, 1)
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert set(nwbfile.events.keys()) == {"CAM1"}
