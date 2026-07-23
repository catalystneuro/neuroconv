from datetime import datetime

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import DoricEventsInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH


class TestDoricEvents:
    """DoricEventsInterface converts every toggling DigitalIO line to rising-edge onset events.

    The fixture file is a modern DataAcquisition-layout .doric with a DigitalIO group: a real camera
    line (``Camera1``, 6 single-sample pulses) and a constant line (``DigitalCh1``, held high, skipped).
    """

    @pytest.fixture
    def interface(self):
        file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "doric" / "BBC300_Acq_0093_stub.doric"
        return DoricEventsInterface(file_path=file_path)

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
        events_metadata = metadata["Events"]
        assert events_metadata == expected_events_metadata

        # session_start_time is read from the stub's "Created" HDF5 attribute.
        expected_session_start_time = datetime(2024, 6, 24, 13, 58, 38)
        session_start_time = metadata["NWBFile"]["session_start_time"]
        assert session_start_time == expected_session_start_time

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        camera_events = nwbfile.get_events_table("Camera1")  # no underscore, kept verbatim

        expected_colnames = ("timestamp",)
        assert camera_events.colnames == expected_colnames

        expected_timestamps = [0.002, 0.018, 0.035, 0.051, 0.068, 0.085]
        timestamps = camera_events["timestamp"][:]
        assert np.allclose(timestamps, expected_timestamps)
