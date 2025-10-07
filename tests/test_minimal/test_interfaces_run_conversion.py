"""Tests for BaseDataInterface.run_conversion method."""

from pynwb import NWBHDF5IO

from neuroconv.tools.testing.mock_interfaces import (
    MockRecordingInterface,
    MockSortingInterface,
)


def test_base_data_interface_append_on_disk(tmp_path):
    """Test that append_on_disk_nwbfile works for BaseDataInterface.run_conversion."""
    nwbfile_path = tmp_path / "test_append.nwb"

    # First write - create the file with sorting data
    interface1 = MockSortingInterface(num_units=3, durations=(0.1,))
    metadata = interface1.get_metadata()
    interface1.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

    # Verify first interface data was written
    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        assert nwbfile.units is not None
        assert len(nwbfile.units) == 3

    # Append to existing file with second interface (recording data)
    interface2 = MockRecordingInterface(num_channels=2, durations=(0.1,))
    interface2.run_conversion(nwbfile_path=nwbfile_path, append_on_disk_nwbfile=True)

    # Verify both interfaces' data exists
    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        # Units from first interface
        assert nwbfile.units is not None
        assert len(nwbfile.units) == 3
        # Recording from second interface
        assert "ElectricalSeries" in nwbfile.acquisition
