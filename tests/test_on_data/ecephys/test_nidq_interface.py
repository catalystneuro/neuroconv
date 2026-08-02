import re

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
    """The default digital path derives every line of the XD0 word into its own EventsTable.

    SpikeGLX packs its digital lines into one integer word per saved channel, so the board's handle is
    the word ``XD0`` and a line is reached by naming the bit. ``DigitalChannelTest_g0`` declares eight
    lines (``niXDChans1=0:7``) of which only bit 0 ever goes high, so the file must yield one populated
    table and seven zero-row ones: the lines existed in the recording, nothing fired on them.
    """
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"
    interface = SpikeGLXNIDQInterface(folder_path=folder_path)

    metadata = interface.get_metadata()
    default_metadata_key = "spikeglx_nidq"
    event_types = metadata["Events"][default_metadata_key]["event_types"]

    # One event type per declared line, identified by word plus bit plus reading.
    expected_event_types = {
        "XD0_bit0_high_period": {"event_name": "XD0_bit0_high_period"},
        "XD0_bit1_high_period": {"event_name": "XD0_bit1_high_period"},
        "XD0_bit2_high_period": {"event_name": "XD0_bit2_high_period"},
        "XD0_bit3_high_period": {"event_name": "XD0_bit3_high_period"},
        "XD0_bit4_high_period": {"event_name": "XD0_bit4_high_period"},
        "XD0_bit5_high_period": {"event_name": "XD0_bit5_high_period"},
        "XD0_bit6_high_period": {"event_name": "XD0_bit6_high_period"},
        "XD0_bit7_high_period": {"event_name": "XD0_bit7_high_period"},
    }
    assert event_types == expected_event_types

    nwbfile_path = tmp_path / "nidq_test_digital_default.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    nwbfile = read_nwb(nwbfile_path)
    # Events land in the dedicated /events group, not in acquisition.
    assert len(nwbfile.acquisition) == 0
    expected_table_names = {
        "XD0Bit0HighPeriod",
        "XD0Bit1HighPeriod",
        "XD0Bit2HighPeriod",
        "XD0Bit3HighPeriod",
        "XD0Bit4HighPeriod",
        "XD0Bit5HighPeriod",
        "XD0Bit6HighPeriod",
        "XD0Bit7HighPeriod",
    }
    assert set(nwbfile.events.keys()) == expected_table_names

    fired = nwbfile.events["XD0Bit0HighPeriod"]
    assert fired.colnames == ("timestamp", "duration")
    assert len(fired) == 163  # 326 edges read as 163 high periods

    # Timestamps are on the recording's own clock, which starts at the stream's t_start rather than at
    # zero, so the events sit on the same axis as an analog series written from the same board.
    np.testing.assert_allclose(fired["timestamp"][:3], [11.9944, 12.9944, 13.9944], atol=1e-4)
    np.testing.assert_allclose(fired["duration"][:3], [0.5, 0.5, 0.5], atol=1e-4)

    # The other seven lines are declared by the header but never toggle in this recording.
    assert len(nwbfile.events["XD0Bit1HighPeriod"]) == 0
    assert len(nwbfile.events["XD0Bit2HighPeriod"]) == 0
    assert len(nwbfile.events["XD0Bit3HighPeriod"]) == 0
    assert len(nwbfile.events["XD0Bit4HighPeriod"]) == 0
    assert len(nwbfile.events["XD0Bit5HighPeriod"]) == 0
    assert len(nwbfile.events["XD0Bit6HighPeriod"]) == 0
    assert len(nwbfile.events["XD0Bit7HighPeriod"]) == 0


def test_nidq_digital_channel_groups_is_deprecated(tmp_path):
    """The released argument still works, translated onto the new grammar, behind a FutureWarning.

    A group named one line and labelled its two states, and produced one `LabeledEvents` holding every
    edge. It now produces one `EventsTable` holding every edge, with the state carried by an `event_type`
    column instead of by an index into a `labels` list. Same object count, same row count, same labels.
    """
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"
    digital_channel_groups = {
        "camera": {"channels": {"nidq#XD0": {"labels_map": {0: "exposure_end", 1: "frame_start"}}}},
    }

    with pytest.warns(FutureWarning, match="digital_channel_groups is deprecated"):
        interface = SpikeGLXNIDQInterface(folder_path=folder_path, digital_channel_groups=digital_channel_groups)

    nwbfile_path = tmp_path / "nidq_test_digital_legacy.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    nwbfile = read_nwb(nwbfile_path)
    assert len(nwbfile.acquisition) == 0  # no more ndx-events LabeledEvents
    assert set(nwbfile.events.keys()) == {"Camera"}  # one object per group, as before

    camera = nwbfile.events["Camera"]
    assert camera.colnames == ("timestamp", "event_type")
    assert len(camera) == 326  # 163 rising plus 163 falling, as the LabeledEvents held

    # labels_map[1] labels the rising edge and labels_map[0] the falling one.
    event_types = np.asarray(camera["event_type"][:])
    assert set(event_types) == {"frame_start", "exposure_end"}
    assert np.sum(event_types == "frame_start") == 163
    assert np.sum(event_types == "exposure_end") == 163


def test_nidq_digital_channel_groups_may_reuse_labels_across_groups(tmp_path):
    """Two groups may label their states the same way, the way two `LabeledEvents` could.

    A label names a state inside one group's table, so `{0: "off", 1: "on"}` on every line is what the
    released argument's own error messages suggest and what a user reading them would write. The shared
    grammar's identifiers are global, so the translation qualifies them by group and hands the bare
    labels back at write time; without that the second group's `on` collides with the first's and the
    interface refuses to construct.
    """
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"
    digital_channel_groups = {
        "camera": {"channels": {"nidq#XD0": {"labels_map": {0: "off", 1: "on"}}}},
        "lick": {"channels": {"nidq#XD1": {"labels_map": {0: "off", 1: "on"}}}},
    }

    with pytest.warns(FutureWarning, match="digital_channel_groups is deprecated"):
        interface = SpikeGLXNIDQInterface(folder_path=folder_path, digital_channel_groups=digital_channel_groups)

    nwbfile_path = tmp_path / "nidq_test_digital_shared_labels.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    nwbfile = read_nwb(nwbfile_path)
    assert set(nwbfile.events.keys()) == {"Camera", "Lick"}  # one table per group, as before

    event_types = np.asarray(nwbfile.events["Camera"]["event_type"][:])
    assert np.sum(event_types == "on") == 163
    assert np.sum(event_types == "off") == 163

    # XD1 was recorded and never fired, which is a result rather than a reason to drop the table. Both
    # of its readings route into one table, so this is also the merged-table shape written with no rows.
    lick = nwbfile.events["Lick"]
    assert len(lick) == 0
    assert set(lick.colnames) == {"timestamp", "event_type"}


def test_nidq_detection_configuration_and_digital_channel_groups_conflict():
    """The two spellings write different NWB objects, so asking for both is an error, not a merge."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"

    with pytest.raises(ValueError, match="not both"):
        SpikeGLXNIDQInterface(
            folder_path=folder_path,
            digital_channel_groups={"camera": {"channels": {"nidq#XD0": {"labels_map": {0: "off", 1: "on"}}}}},
            detection_configuration={"XD0": [{"signal_conditioning": {"bits": [0]}, "detection": "rising"}]},
        )


def test_nidq_detection_configuration_selects_one_line():
    """A caller-supplied configuration reads only the lines it names, with the reading it names."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"
    interface = SpikeGLXNIDQInterface(
        folder_path=folder_path,
        detection_configuration={
            "XD0": [{"signal_conditioning": {"bits": [0]}, "detection": "rising", "event_name": "camera_frame"}]
        },
    )

    from pynwb.testing.mock.file import mock_NWBFile

    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

    assert set(nwbfile.events.keys()) == {"CameraFrame"}
    camera = nwbfile.events["CameraFrame"]
    assert camera.colnames == ("timestamp",)  # a point reading carries no duration
    assert len(camera) == 163


def test_nidq_digital_metadata_customization(tmp_path):
    """The deprecated metadata shape is still what get_metadata hands back, and still honoured.

    Existing code edits `metadata["Events"][metadata_key][group_key]` with `name`, `description` and
    `meanings`. Those edits arrive at `add_to_nwbfile`, which is where they are translated onto the
    shape the events writer reads, so they keep working unchanged.
    """
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"
    labels_map = {0: "exposure_end", 1: "frame_start"}
    digital_channel_groups = {"camera": {"channels": {"nidq#XD0": {"labels_map": labels_map}}}}
    metadata_key = "custom_key"

    with pytest.warns(FutureWarning, match="digital_channel_groups is deprecated"):
        interface = SpikeGLXNIDQInterface(
            folder_path=folder_path,
            metadata_key=metadata_key,
            digital_channel_groups=digital_channel_groups,
        )

    metadata = interface.get_metadata()

    # The old shape, keyed by group, is what a user has always been given here.
    assert metadata["Events"][metadata_key]["camera"]["name"] == "Camera"
    assert metadata["Events"][metadata_key]["camera"]["description"] == "On and Off Events from channel XD0"

    metadata["Events"][metadata_key]["camera"]["name"] = "CameraFrameTrigger"
    metadata["Events"][metadata_key]["camera"]["description"] = "Camera frame timing events"
    metadata["Events"][metadata_key]["camera"]["meanings"] = {
        "frame_start": "New camera frame acquisition started",
        "exposure_end": "Camera exposure period ended, frame readout complete",
    }

    nwbfile = interface.create_nwbfile(metadata=metadata)

    assert len(nwbfile.acquisition) == 0
    assert set(nwbfile.events.keys()) == {"CameraFrameTrigger"}

    camera = nwbfile.events["CameraFrameTrigger"]
    assert camera.description == "Camera frame timing events"
    assert len(camera) == 326

    event_types = np.asarray(camera["event_type"][:])
    assert np.sum(event_types == "frame_start") == 163
    assert np.sum(event_types == "exposure_end") == 163


def test_nidq_partial_labels_map():
    """Test that partial labels_map raises ValueError at init."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"

    # Provide partial labels_map - only one label when extractor has two unique values
    expected_error = (
        "Incomplete labels_map for channel 'nidq#XD0' in group 'camera'. "
        "Expected keys {0, 1}, got {0}. "
        "labels_map must cover all 2 unique values from the extractor. "
        "Example: {0: 'label_0', 1: 'label_1'}"
    )
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        SpikeGLXNIDQInterface(
            folder_path=folder_path,
            digital_channel_groups={
                "camera": {
                    "channels": {
                        "nidq#XD0": {"labels_map": {0: "custom_label_0"}},  # Missing key 1
                    },
                },
            },
        )


def test_nidq_digital_groups_invalid_channel():
    """Test that invalid channel IDs raise ValueError at init."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"

    expected_error = (
        "Invalid digital channel 'nidq#XD99' in group 'camera'. "
        "Available digital channels: ['nidq#XD0', 'nidq#XD1', 'nidq#XD2', 'nidq#XD3', "
        "'nidq#XD4', 'nidq#XD5', 'nidq#XD6', 'nidq#XD7']"
    )
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        SpikeGLXNIDQInterface(
            folder_path=folder_path,
            digital_channel_groups={
                "camera": {
                    "channels": {
                        "nidq#XD99": {"labels_map": {0: "off", 1: "on"}},  # XD99 doesn't exist
                    },
                },
            },
        )


def test_nidq_digital_groups_missing_channels_key():
    """Test that missing 'channels' key raises ValueError at init."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"

    expected_error = "Digital group 'camera' missing required 'channels' field."
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        SpikeGLXNIDQInterface(
            folder_path=folder_path,
            digital_channel_groups={
                "camera": {
                    "labels_map": {0: "off", 1: "on"},  # Wrong structure - missing 'channels'
                },
            },
        )


def test_nidq_digital_groups_missing_labels_map():
    """Test that missing 'labels_map' key raises ValueError at init."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"

    expected_error = (
        "Channel 'nidq#XD0' in group 'camera' missing required 'labels_map' field. "
        "Example: {'nidq#XD0': {'labels_map': {0: 'off', 1: 'on'}}}"
    )
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        SpikeGLXNIDQInterface(
            folder_path=folder_path,
            digital_channel_groups={
                "camera": {
                    "channels": {
                        "nidq#XD0": {},  # Missing labels_map
                    },
                },
            },
        )


def test_nidq_digital_groups_multi_channel_not_supported():
    """Test that multi-channel groups raise ValueError (not yet supported)."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"

    expected_error = (
        "Currently only single-channel groups are supported. "
        "Multi-channel groups will be supported when ndx-events EventsTable "
        "is integrated into NWB core."
    )
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        SpikeGLXNIDQInterface(
            folder_path=folder_path,
            digital_channel_groups={
                "cameras": {
                    "channels": {
                        "nidq#XD0": {"labels_map": {0: "off", 1: "on"}},
                        "nidq#XD1": {"labels_map": {0: "off", 1: "on"}},  # Second channel in the same group
                    },
                },
            },
        )


def test_nidq_analog_data(tmp_path):
    """Test analog channels with default behavior (no grouping)."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"
    interface = SpikeGLXNIDQInterface(folder_path=folder_path)

    # Test metadata structure with default metadata_key
    assert interface.metadata_key == "spikeglx_nidq"
    metadata = interface.get_metadata()
    time_series_metadata = metadata.get("TimeSeries", {})

    # Expected TimeSeries metadata structure (default: single TimeSeries with all channels)
    expected_time_series_metadata = {
        "spikeglx_nidq": {
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
            "audio": {
                "channels": ["nidq#XA0", "nidq#XA1"],
            },
            "accelerometer": {
                "channels": ["nidq#XA2", "nidq#XA3", "nidq#XA4"],
            },
            "temperature": {
                "channels": ["nidq#XA5", "nidq#XA6", "nidq#XA7"],
            },
        },
    )

    # Get metadata - should have 3 group entries with CamelCase names
    metadata = interface.get_metadata()
    time_series_metadata = metadata["TimeSeries"]["spikeglx_nidq"]

    # Check that metadata has correct structure with default CamelCase names
    assert "audio" in time_series_metadata
    assert time_series_metadata["audio"]["name"] == "Audio"
    assert "group 'audio'" in time_series_metadata["audio"]["description"]

    assert "accelerometer" in time_series_metadata
    assert time_series_metadata["accelerometer"]["name"] == "Accelerometer"

    assert "temperature" in time_series_metadata
    assert time_series_metadata["temperature"]["name"] == "Temperature"

    # Customize metadata (names and descriptions)
    metadata["TimeSeries"]["spikeglx_nidq"]["audio"]["name"] = "TimeSeriesAudioSignals"
    metadata["TimeSeries"]["spikeglx_nidq"]["audio"]["description"] = "Audio signals from microphones"

    metadata["TimeSeries"]["spikeglx_nidq"]["accelerometer"]["name"] = "TimeSeriesAccelerometer"
    metadata["TimeSeries"]["spikeglx_nidq"]["accelerometer"]["description"] = "3-axis accelerometer data"

    metadata["TimeSeries"]["spikeglx_nidq"]["temperature"]["name"] = "TimeSeriesTemperature"
    metadata["TimeSeries"]["spikeglx_nidq"]["temperature"]["description"] = "Temperature sensor readings"

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
                "audio": {
                    "channels": ["nidq#XA0", "nidq#XA99"],  # XA99 doesn't exist
                },
            },
        )


def test_nidq_analog_groups_missing_channels_key():
    """Test that missing 'channels' key raises ValueError at init."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"

    expected_error = "Analog group 'audio' missing required 'channels' field."
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        SpikeGLXNIDQInterface(
            folder_path=folder_path,
            analog_channel_groups={
                "audio": {},  # Missing 'channels' key
            },
        )


def test_nidq_analog_groups_with_default_metadata(tmp_path):
    """Test that groups work with default metadata (no customization)."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"

    # Create interface with grouping
    interface = SpikeGLXNIDQInterface(
        folder_path=folder_path,
        analog_channel_groups={
            "audio": {
                "channels": ["nidq#XA0", "nidq#XA1"],
            },
            "sensors": {
                "channels": ["nidq#XA2", "nidq#XA3"],
            },
        },
    )

    # Write with default metadata (no customization)
    nwbfile_path = tmp_path / "nidq_test_default_groups.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path)

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
    time_series_metadata = metadata["TimeSeries"]["spikeglx_nidq"]

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


def test_analog_empty_dict_excludes_all_channels():
    """Test that analog_channel_groups={} excludes all analog channels."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"

    # Create interface with empty dict for analog grouping
    interface = SpikeGLXNIDQInterface(
        folder_path=folder_path,
        analog_channel_groups={},
    )

    # Verify that the interface has analog channels available
    assert interface.has_analog_channels
    assert len(interface.analog_channel_ids) == 8

    # But no TimeSeries metadata is generated
    metadata = interface.get_metadata()
    time_series_metadata = metadata.get("TimeSeries", {}).get("spikeglx_nidq", {})
    assert time_series_metadata == {}

    # And no acquisition is written
    nwbfile = interface.create_nwbfile()
    assert len(nwbfile.acquisition) == 0


def test_digital_empty_dict_excludes_all_channels():
    """Test that digital_channel_groups={} excludes all digital channels."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"

    # Create interface with empty dict for digital grouping
    interface = SpikeGLXNIDQInterface(
        folder_path=folder_path,
        digital_channel_groups={},
    )

    # Verify that the interface has digital channels available
    assert interface.has_digital_channels
    assert len(interface.event_extractor.channel_ids) == 8

    # But no Events metadata is generated
    metadata = interface.get_metadata()
    events_metadata = metadata.get("Events", {}).get("spikeglx_nidq", {})
    assert events_metadata == {}

    # And no acquisition is written
    nwbfile = interface.create_nwbfile()
    assert len(nwbfile.acquisition) == 0


def test_metadata_key_does_not_rename_series():
    """The key addresses the entries; the TimeSeries names live inside them and are unaffected."""
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"

    default_interface = SpikeGLXNIDQInterface(folder_path=folder_path)
    assert default_interface.metadata_key == "spikeglx_nidq"
    default_entry = default_interface.get_metadata()["TimeSeries"]["spikeglx_nidq"]
    assert default_entry["nidq_analog"]["name"] == "TimeSeriesNIDQ"

    custom_interface = SpikeGLXNIDQInterface(folder_path=folder_path, metadata_key="my_nidq")
    time_series_metadata = custom_interface.get_metadata()["TimeSeries"]
    assert set(time_series_metadata) == {"my_nidq"}
    assert time_series_metadata["my_nidq"]["nidq_analog"]["name"] == "TimeSeriesNIDQ"
