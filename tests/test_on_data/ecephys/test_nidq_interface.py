import numpy as np
import pytest
from pynwb import read_nwb

from neuroconv.datainterfaces import SpikeGLXNIDQInterface

# enable to run locally in interactive mode
try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

if not ECEPHY_DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {ECEPHY_DATA_PATH}!")


def test_nidq_digital_data(tmp_path):
    """Test digital channels with default metadata configuration."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"
    interface = SpikeGLXNIDQInterface(folder_path=folder_path)

    # Verify metadata structure with Events section
    metadata = interface.get_metadata()
    events_metadata = metadata.get("Events", {})

    # Expected Events metadata structure for all 8 digital channels
    # Note: labels_map values are extractor-dependent
    expected_events_metadata = {
        "SpikeGLXNIDQ": {
            "nidq#XD0": {
                "name": "EventsNIDQDigitalChannelXD0",
                "description": "On and Off Events from channel XD0",
                "labels_map": {0: "XD0 OFF", 1: "XD0 ON"},
            },
            "nidq#XD1": {
                "name": "EventsNIDQDigitalChannelXD1",
                "description": "On and Off Events from channel XD1",
                "labels_map": {},
            },
            "nidq#XD2": {
                "name": "EventsNIDQDigitalChannelXD2",
                "description": "On and Off Events from channel XD2",
                "labels_map": {},
            },
            "nidq#XD3": {
                "name": "EventsNIDQDigitalChannelXD3",
                "description": "On and Off Events from channel XD3",
                "labels_map": {},
            },
            "nidq#XD4": {
                "name": "EventsNIDQDigitalChannelXD4",
                "description": "On and Off Events from channel XD4",
                "labels_map": {},
            },
            "nidq#XD5": {
                "name": "EventsNIDQDigitalChannelXD5",
                "description": "On and Off Events from channel XD5",
                "labels_map": {},
            },
            "nidq#XD6": {
                "name": "EventsNIDQDigitalChannelXD6",
                "description": "On and Off Events from channel XD6",
                "labels_map": {},
            },
            "nidq#XD7": {
                "name": "EventsNIDQDigitalChannelXD7",
                "description": "On and Off Events from channel XD7",
                "labels_map": {},
            },
        }
    }

    # Validate that events_metadata matches expected structure
    assert events_metadata == expected_events_metadata

    # Write with default configuration
    nwbfile_path = tmp_path / "nidq_test_digital_default.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    nwbfile = read_nwb(nwbfile_path)
    assert len(nwbfile.acquisition) == 1
    events = nwbfile.acquisition["EventsNIDQDigitalChannelXD0"]
    assert events.timestamps.size == 326
    # Check that data alternates between the two label indices
    assert len(np.unique(events.data)) == 2
    # The exact label-to-index mapping depends on extractor, but should have equal counts
    unique_data = np.unique(events.data)
    assert np.sum(events.data == unique_data[0]) == 163
    assert np.sum(events.data == unique_data[1]) == 163


def test_nidq_digital_metadata_customization(tmp_path):
    """Test digital channels with custom semantic labels."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"
    metadata_key = "custom_key"
    interface = SpikeGLXNIDQInterface(folder_path=folder_path, metadata_key=metadata_key)

    # Customize metadata for semantic labels
    metadata = interface.get_metadata()
    labels_map = {0: "exposure_end", 1: "frame_start"}
    events_name = "EventsCustomCamera"
    metadata["Events"][metadata_key]["nidq#XD0"] = {
        "name": events_name,
        "description": "Custom camera with semantic labels",
        "labels_map": labels_map,
    }

    nwbfile_path = tmp_path / "nidq_test_digital_custom.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

    nwbfile = read_nwb(nwbfile_path)
    assert events_name in nwbfile.acquisition
    events = nwbfile.acquisition[events_name]
    assert list(events.labels) == list(labels_map.values())
    # Check that both semantic labels are used
    unique_data = np.unique(events.data)
    assert len(unique_data) == 2
    assert np.sum(events.data == unique_data[0]) == 163
    assert np.sum(events.data == unique_data[1]) == 163


def test_nidq_partial_labels_map(tmp_path):
    """Test that partial labels_map is auto-filled with defaults."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"
    interface = SpikeGLXNIDQInterface(folder_path=folder_path)

    # Get default metadata to see what the default labels are
    default_metadata = interface.get_metadata()
    default_labels_map = default_metadata["Events"]["SpikeGLXNIDQ"]["nidq#XD0"]["labels_map"]

    # Provide partial labels_map - only customize one label
    metadata = interface.get_metadata()
    metadata["Events"]["SpikeGLXNIDQ"]["nidq#XD0"] = {
        "name": "EventsPartialCustom",
        "description": "Partially customized labels",
        "labels_map": {0: "custom_label_0"},  # Only provide mapping for data value 0
    }

    nwbfile_path = tmp_path / "nidq_test_partial.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

    nwbfile = read_nwb(nwbfile_path)
    events = nwbfile.acquisition["EventsPartialCustom"]
    # Should have both labels: custom one and default one
    assert len(events.labels) == 2
    assert events.labels[0] == "custom_label_0"  # Custom label for data value 0
    assert events.labels[1] == default_labels_map[1]  # Default label for data value 1


def test_nidq_analog_data(tmp_path):
    """Test analog channels with default behavior (no grouping)."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"
    interface = SpikeGLXNIDQInterface(folder_path=folder_path)

    # Test metadata structure with default metadata_key
    assert interface.metadata_key == "SpikeGLXNIDQ"
    metadata = interface.get_metadata()
    time_series_metadata = metadata.get("TimeSeries", {})

    # Expected TimeSeries metadata structure (default: single TimeSeries with all channels)
    expected_time_series_metadata = {
        "SpikeGLXNIDQ": {
            "nidq_analog": {
                "name": "TimeSeriesNIDQ",
                "description": "Analog data from the NIDQ board. Channels are ['XA0', 'XA1', 'XA2', 'XA3', 'XA4', 'XA5', 'XA6', 'XA7'] in that order.",
            }
        }
    }

    # Validate that time_series_metadata matches expected structure
    assert time_series_metadata == expected_time_series_metadata

    # Write to NWB and verify
    nwbfile_path = tmp_path / "nidq_test_analog.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    nwbfile = read_nwb(nwbfile_path)
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


def test_nidq_analog_metadata_customization(tmp_path):
    """Test dividing analog channels into multiple TimeSeries with init-time grouping."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"

    # Divide the 8 analog channels (XA0-XA7) into 3 separate groups at init time
    interface = SpikeGLXNIDQInterface(
        folder_path=folder_path,
        analog_channel_groups={
            "audio": ["nidq#XA0", "nidq#XA1"],
            "accelerometer": ["nidq#XA2", "nidq#XA3", "nidq#XA4"],
            "temperature": ["nidq#XA5", "nidq#XA6", "nidq#XA7"],
        },
    )

    # Get metadata - should have 3 group entries with CamelCase names
    metadata = interface.get_metadata()
    time_series_metadata = metadata["TimeSeries"]["SpikeGLXNIDQ"]

    # Check that metadata has correct structure with default CamelCase names
    assert "audio" in time_series_metadata
    assert time_series_metadata["audio"]["name"] == "Audio"
    assert "group 'audio'" in time_series_metadata["audio"]["description"]

    assert "accelerometer" in time_series_metadata
    assert time_series_metadata["accelerometer"]["name"] == "Accelerometer"

    assert "temperature" in time_series_metadata
    assert time_series_metadata["temperature"]["name"] == "Temperature"

    # Customize metadata (names and descriptions)
    metadata["TimeSeries"]["SpikeGLXNIDQ"]["audio"]["name"] = "TimeSeriesAudioSignals"
    metadata["TimeSeries"]["SpikeGLXNIDQ"]["audio"]["description"] = "Audio signals from microphones"

    metadata["TimeSeries"]["SpikeGLXNIDQ"]["accelerometer"]["name"] = "TimeSeriesAccelerometer"
    metadata["TimeSeries"]["SpikeGLXNIDQ"]["accelerometer"]["description"] = "3-axis accelerometer data"

    metadata["TimeSeries"]["SpikeGLXNIDQ"]["temperature"]["name"] = "TimeSeriesTemperature"
    metadata["TimeSeries"]["SpikeGLXNIDQ"]["temperature"]["description"] = "Temperature sensor readings"

    # Write to NWB and verify multiple TimeSeries were created
    nwbfile_path = tmp_path / "nidq_test_multiple_timeseries.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

    nwbfile = read_nwb(nwbfile_path)

    # Should have 3 TimeSeries objects in acquisition
    assert len(nwbfile.acquisition) == 3

    # Verify audio TimeSeries
    assert "TimeSeriesAudioSignals" in nwbfile.acquisition
    audio_ts = nwbfile.acquisition["TimeSeriesAudioSignals"]
    assert audio_ts.data.shape[1] == 2  # 2 channels
    assert "Audio signals from microphones" in audio_ts.description

    # Verify accelerometer TimeSeries
    assert "TimeSeriesAccelerometer" in nwbfile.acquisition
    accel_ts = nwbfile.acquisition["TimeSeriesAccelerometer"]
    assert accel_ts.data.shape[1] == 3  # 3 channels
    assert "3-axis accelerometer data" in accel_ts.description

    # Verify temperature TimeSeries
    assert "TimeSeriesTemperature" in nwbfile.acquisition
    temp_ts = nwbfile.acquisition["TimeSeriesTemperature"]
    assert temp_ts.data.shape[1] == 3  # 3 channels
    assert "Temperature sensor readings" in temp_ts.description


def test_nidq_analog_invalid_channels_at_init(tmp_path):
    """Test that invalid channel IDs raise ValueError at interface initialization."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"

    # Try to create interface with invalid channel IDs
    with pytest.raises(ValueError, match="Invalid channels in group 'audio'"):
        SpikeGLXNIDQInterface(
            folder_path=folder_path,
            analog_channel_groups={
                "audio": ["nidq#XA0", "nidq#XA99"],  # XA99 doesn't exist
            },
        )


def test_nidq_analog_groups_with_default_metadata(tmp_path):
    """Test that groups work with default metadata (no customization)."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"

    # Create interface with grouping
    interface = SpikeGLXNIDQInterface(
        folder_path=folder_path,
        analog_channel_groups={
            "audio": ["nidq#XA0", "nidq#XA1"],
            "sensors": ["nidq#XA2", "nidq#XA3"],
        },
    )

    # Write with default metadata (no customization)
    nwbfile_path = tmp_path / "nidq_test_default_groups.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    nwbfile = read_nwb(nwbfile_path)

    # Should have 2 TimeSeries with CamelCase default names
    assert len(nwbfile.acquisition) == 2
    assert "Audio" in nwbfile.acquisition
    assert "Sensors" in nwbfile.acquisition

    # Verify channel counts
    assert nwbfile.acquisition["Audio"].data.shape[1] == 2
    assert nwbfile.acquisition["Sensors"].data.shape[1] == 2


def test_nidq_analog_backward_compatibility(tmp_path):
    """Test that analog_channel_groups=None maintains backward compatibility."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"

    # Create interface without grouping (None is default)
    interface = SpikeGLXNIDQInterface(folder_path=folder_path, analog_channel_groups=None)

    # Should behave exactly like main branch - single TimeSeries with all channels
    metadata = interface.get_metadata()
    time_series_metadata = metadata["TimeSeries"]["SpikeGLXNIDQ"]

    # Should have single "nidq_analog" entry
    assert "nidq_analog" in time_series_metadata
    assert time_series_metadata["nidq_analog"]["name"] == "TimeSeriesNIDQ"

    # Write and verify
    nwbfile_path = tmp_path / "nidq_test_backward_compat.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    nwbfile = read_nwb(nwbfile_path)
    assert len(nwbfile.acquisition) == 1
    assert "TimeSeriesNIDQ" in nwbfile.acquisition
    assert nwbfile.acquisition["TimeSeriesNIDQ"].data.shape[1] == 8  # All 8 channels
