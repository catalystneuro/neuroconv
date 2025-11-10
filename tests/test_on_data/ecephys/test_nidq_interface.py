import numpy as np
import pytest
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import SpikeGLXNIDQInterface

# enable to run locally in interactive mode
try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

if not ECEPHY_DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {ECEPHY_DATA_PATH}!")


def test_nidq_interface_digital_data(tmp_path):
    """Test digital channels with default and custom metadata configurations."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"
    interface = SpikeGLXNIDQInterface(folder_path=folder_path)

    # Test 1: Verify metadata structure with Events section
    metadata = interface.get_metadata()
    assert "Events" in metadata
    assert "SpikeGLXNIDQ" in metadata["Events"]
    assert "nidq#XD0" in metadata["Events"]["SpikeGLXNIDQ"]

    # Default configuration - should contain extractor labels
    xd0_config = metadata["Events"]["SpikeGLXNIDQ"]["nidq#XD0"]
    assert xd0_config["name"] == "EventsNIDQDigitalChannelXD0"
    assert xd0_config["labels"] is not None
    assert len(xd0_config["labels"]) == 2  # OFF and ON
    assert xd0_config["label_mapping"] is not None

    # Test 2: Write with default configuration
    nwbfile_path = tmp_path / "nidq_test_digital_default.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        assert len(nwbfile.acquisition) == 1
        events = nwbfile.acquisition["EventsNIDQDigitalChannelXD0"]
        assert events.timestamps.size == 326
        # Check that data alternates between the two label indices
        assert len(np.unique(events.data)) == 2
        # The exact label-to-index mapping depends on extractor, but should have equal counts
        unique_data = np.unique(events.data)
        assert np.sum(events.data == unique_data[0]) == 163
        assert np.sum(events.data == unique_data[1]) == 163

    # Test 3: Customize metadata for semantic labels
    # Get fresh metadata and override with custom semantic labels
    metadata = interface.get_metadata()
    metadata["Events"]["SpikeGLXNIDQ"]["nidq#XD0"] = {
        "name": "EventsCustomCamera",
        "description": "Custom camera with semantic labels",
        "labels": ["exposure_end", "frame_start"],
        "label_mapping": {"XD0 OFF": 0, "XD0 ON": 1},
    }

    nwbfile_path_custom = tmp_path / "nidq_test_digital_custom.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path_custom, metadata=metadata, overwrite=True)

    with NWBHDF5IO(nwbfile_path_custom, "r") as io:
        nwbfile = io.read()
        assert "EventsCustomCamera" in nwbfile.acquisition
        events = nwbfile.acquisition["EventsCustomCamera"]
        assert list(events.labels) == ["exposure_end", "frame_start"]
        # Check that both semantic labels are used
        unique_data = np.unique(events.data)
        assert len(unique_data) == 2
        assert np.sum(events.data == unique_data[0]) == 163
        assert np.sum(events.data == unique_data[1]) == 163


def test_nidq_interface_analog_data(tmp_path):
    """Test analog channels with default metadata_key."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"
    interface = SpikeGLXNIDQInterface(folder_path=folder_path)

    # Test metadata structure with default metadata_key
    assert interface.metadata_key == "SpikeGLXNIDQ"
    metadata = interface.get_metadata()
    assert "TimeSeries" in metadata
    assert "SpikeGLXNIDQ" in metadata["TimeSeries"]
    assert metadata["TimeSeries"]["SpikeGLXNIDQ"]["name"] == "TimeSeriesNIDQ"

    # Write to NWB and verify
    nwbfile_path = tmp_path / "nidq_test_analog.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        assert len(nwbfile.acquisition) == 1  # The time series object
        time_series = nwbfile.acquisition["TimeSeriesNIDQ"]
        assert time_series.name == "TimeSeriesNIDQ"
        # Check that description contains channel information
        assert "Analog data from the NIDQ board" in time_series.description
        assert "XA0" in time_series.description
        assert "XA7" in time_series.description
        number_of_samples = time_series.data.shape[0]
        assert number_of_samples == 60_864
        number_of_channels = time_series.data.shape[1]
        assert number_of_channels == 8
        assert len(nwbfile.devices) == 1


def test_nidq_interface_with_custom_metadata_key(tmp_path):
    """Test custom metadata_key for multiple NIDQ interface scenario."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"
    interface = SpikeGLXNIDQInterface(folder_path=folder_path, metadata_key="nidq_custom")

    # Verify custom metadata_key is used throughout
    assert interface.metadata_key == "nidq_custom"
    metadata = interface.get_metadata()

    # Check TimeSeries uses custom key
    assert "TimeSeries" in metadata
    assert "nidq_custom" in metadata["TimeSeries"]
    assert metadata["TimeSeries"]["nidq_custom"]["name"] == "TimeSeriesNIDQ"

    # Write to NWB and verify the custom key was used
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, stub_test=True)

    assert "TimeSeriesNIDQ" in nwbfile.acquisition
    time_series = nwbfile.acquisition["TimeSeriesNIDQ"]
    # Verify that analog data was written
    assert time_series.data is not None
    assert hasattr(time_series, "timestamps") or hasattr(time_series, "rate")
