from datetime import datetime

import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import SpikeGLXSyncChannelInterface

from ..setup_paths import ECEPHY_DATA_PATH

SPIKEGLX_PATH = ECEPHY_DATA_PATH / "spikeglx"


class TestSpikeGLXSyncChannelInterfaceValidation:
    """Tests for SpikeGLXSyncChannelInterface validation logic."""

    def test_invalid_stream_id_no_sync(self, tmp_path):
        """Test that interface raises error when stream_id doesn't contain '-SYNC'."""
        with pytest.raises(ValueError, match="stream_id must contain '-SYNC'"):
            SpikeGLXSyncChannelInterface(
                folder_path=tmp_path,
                stream_id="imec0.ap",
            )

    def test_obx_not_implemented(self, tmp_path):
        """Test that OneBox sync channels raise NotImplementedError."""
        with pytest.raises(NotImplementedError, match="OneBox.*not yet implemented"):
            SpikeGLXSyncChannelInterface(
                folder_path=tmp_path,
                stream_id="obx0-SYNC",
            )


class TestSpikeGLXSyncChannelInterface:
    """Tests for SpikeGLXSyncChannelInterface with sync channel data."""

    test_folder = SPIKEGLX_PATH / "Noise4Sam_g0"

    def test_get_metadata(self):
        """Test that metadata is generated correctly, including session start time."""

        metadata_key = "custom_metadata_key"
        interface = SpikeGLXSyncChannelInterface(
            folder_path=self.test_folder,
            stream_id="imec0.ap-SYNC",
            metadata_key=metadata_key,
        )

        metadata = interface.get_metadata()

        # Define expected metadata structure
        expected_device = {
            "name": "NeuropixelsImec0",
            "description": "Neuropixels probe 0 used with SpikeGLX.",
            "manufacturer": "Imec",
        }

        expected_timeseries = {
            "name": "TimeSeriesImec0Sync",
            "description": (
                "Synchronization channel (SY0) from Neuropixel probe 0 "
                "AP stream (stream: imec0.ap-SYNC). Contains a 16-bit status word where bit 6 carries a 1 Hz "
                "square wave (toggling between 0 and 1 every 0.5 seconds) used for sub-millisecond timing "
                "alignment across acquisition devices and data streams. The other bits carry hardware status "
                "and error flags. For NP1.0 probes, the sync channel appears identically in both AP and LF files. "
                "The sync signal can be generated internally by the Imec module (PXIe or OneBox) or externally "
                "by an NI-DAQ device acting as the master sync generator for multi-device setups."
            ),
        }

        # Check device metadata
        assert "Devices" in metadata
        assert len(metadata["Devices"]) == 1
        assert metadata["Devices"][0] == expected_device

        # Check TimeSeries metadata
        assert "TimeSeries" in metadata
        assert metadata_key in metadata["TimeSeries"]
        assert metadata["TimeSeries"][metadata_key] == expected_timeseries

        # Check session start time matches the expected value from test data
        expected_session_start_time = datetime.fromisoformat("2020-11-03T10:35:10")
        assert "NWBFile" in metadata
        assert "session_start_time" in metadata["NWBFile"]
        assert metadata["NWBFile"]["session_start_time"] == expected_session_start_time

    def test_run_conversion(self, tmp_path):
        """Test that sync channel data is added to NWB file correctly."""
        interface = SpikeGLXSyncChannelInterface(
            folder_path=self.test_folder,
            stream_id="imec0.ap-SYNC",
        )

        metadata = interface.get_metadata()
        nwbfile_path = tmp_path / "test_sync_channel.nwb"

        # Get expected sampling rate from the recording extractor
        expected_rate = interface.recording_extractor.get_sampling_frequency()

        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        # Read and verify NWB file structure
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()

            # Check that device was added
            assert "NeuropixelsImec0" in nwbfile.devices
            device = nwbfile.devices["NeuropixelsImec0"]
            assert device.manufacturer == "Imec"

            # Check that TimeSeries was added to acquisition
            assert "TimeSeriesImec0Sync" in nwbfile.acquisition
            timeseries = nwbfile.acquisition["TimeSeriesImec0Sync"]

            # Verify TimeSeries properties
            assert timeseries.name == "TimeSeriesImec0Sync"
            assert "Synchronization channel" in timeseries.description

            # Verify shape as tuple and exact sampling rate
            assert timeseries.data.shape == (1155, 1)  # Expected shape for full recording
            assert timeseries.rate == expected_rate

    def test_stub_test(self):
        """Test that stub_test parameter creates data with exactly 100 samples."""
        interface = SpikeGLXSyncChannelInterface(
            folder_path=self.test_folder,
            stream_id="imec0.ap-SYNC",
        )

        # Create NWBFile with stub data without iterator wrapping
        nwbfile = interface.create_nwbfile(stub_test=True, iterator_type=None)

        # Verify stub creates exactly 100 samples
        # Note: iterator_type=None means data is not wrapped in an iterator so we can access shape directly
        timeseries = nwbfile.acquisition["TimeSeriesImec0Sync"]
        assert timeseries.data.shape == (100, 1)  # Exactly 100 samples, 1 channel

    def test_adding_sync_from_lf_band(self):
        """Test interface with LF sync stream instead of AP."""
        from spikeinterface.extractors.extractor_classes import (
            SpikeGLXRecordingExtractor,
        )

        interface = SpikeGLXSyncChannelInterface(
            folder_path=self.test_folder,
            stream_id="imec0.lf-SYNC",
        )

        # Verify metadata is generated correctly for LF stream
        metadata = interface.get_metadata()
        assert metadata["TimeSeries"]["SpikeGLXSync"]["name"] == "TimeSeriesImec0Sync"
        assert "LF stream" in metadata["TimeSeries"]["SpikeGLXSync"]["description"]

        # Create NWBFile without iterator wrapping to access data directly
        nwbfile = interface.create_nwbfile(stub_test=True, iterator_type=None)

        # Verify TimeSeries is present
        assert "TimeSeriesImec0Sync" in nwbfile.acquisition
        timeseries = nwbfile.acquisition["TimeSeriesImec0Sync"]

        # Verify shape as tuple
        assert timeseries.data.shape == (100, 1)

        # Get expected data from recording extractor
        recording = SpikeGLXRecordingExtractor(
            folder_path=self.test_folder,
            stream_id="imec0.lf-SYNC",
            all_annotations=True,
        )
        expected_traces = recording.get_traces(start_frame=0, end_frame=100)

        # Verify data values match the source recording
        import numpy as np

        np.testing.assert_array_equal(timeseries.data[:], expected_traces)


if __name__ == "__main__":
    pytest.main([__file__])
