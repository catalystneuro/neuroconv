"""Tests for BaseDataInterface.run_conversion method."""

from pynwb import NWBHDF5IO

from neuroconv.tools.testing.mock_interfaces import MockTimeSeriesInterface


def test_base_data_interface_append_on_disk(tmp_path):
    """Test that append_on_disk_nwbfile works for BaseDataInterface.run_conversion."""
    nwbfile_path = tmp_path / "test_append.nwb"

    # First write - create the file with first TimeSeries
    interface1 = MockTimeSeriesInterface(num_channels=3, duration=0.1, metadata_key="TimeSeriesFirst")
    metadata1 = interface1.get_metadata()
    metadata1["TimeSeries"]["TimeSeriesFirst"]["name"] = "TimeSeriesFirst"
    interface1.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata1)

    # Verify first interface data was written
    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        assert "TimeSeriesFirst" in nwbfile.acquisition
        assert nwbfile.acquisition["TimeSeriesFirst"].data.shape[1] == 3

    # Append to existing file with second interface (another TimeSeries)
    interface2 = MockTimeSeriesInterface(num_channels=2, duration=0.1, metadata_key="TimeSeriesSecond")
    metadata2 = interface2.get_metadata()
    metadata2["TimeSeries"]["TimeSeriesSecond"]["name"] = "TimeSeriesSecond"
    interface2.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata2, append_on_disk_nwbfile=True)

    # Verify both interfaces' data exists
    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        # First TimeSeries
        assert "TimeSeriesFirst" in nwbfile.acquisition
        assert nwbfile.acquisition["TimeSeriesFirst"].data.shape[1] == 3
        # Second TimeSeries
        assert "TimeSeriesSecond" in nwbfile.acquisition
        assert nwbfile.acquisition["TimeSeriesSecond"].data.shape[1] == 2
