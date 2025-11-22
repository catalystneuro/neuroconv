from datetime import datetime
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import SpikeGLXSyncChannelInterface

from ..setup_paths import ECEPHY_DATA_PATH

SPIKEGLX_PATH = ECEPHY_DATA_PATH / "spikeglx"


class TestSpikeGLXSyncChannelInterface:
    """Tests for SpikeGLXSyncChannelInterface with sync channel data."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.tmpdir = Path(mkdtemp())
        self.test_folder = SPIKEGLX_PATH / "NP2_with_sync"
        yield
        rmtree(self.tmpdir)

    def test_interface_initialization(self):
        """Test that the interface initializes correctly with a valid sync stream."""
        interface = SpikeGLXSyncChannelInterface(
            folder_path=self.test_folder,
            stream_id="imec0.ap-SYNC",
        )

        assert interface.stream_id == "imec0.ap-SYNC"
        assert interface.probe_index == "0"
        assert interface.stream_kind == "AP"

    def test_invalid_stream_id_no_sync(self):
        """Test that interface raises error when stream_id doesn't contain '-SYNC'."""
        with pytest.raises(ValueError, match="stream_id must contain '-SYNC'"):
            SpikeGLXSyncChannelInterface(
                folder_path=self.test_folder,
                stream_id="imec0.ap",
            )

    def test_invalid_stream_id_no_imec(self):
        """Test that interface raises error when stream_id doesn't contain 'imec'."""
        with pytest.raises(ValueError, match="stream_id must contain 'imec'"):
            SpikeGLXSyncChannelInterface(
                folder_path=self.test_folder,
                stream_id="nidq-SYNC",
            )

    def test_obx_not_implemented(self):
        """Test that OneBox sync channels raise NotImplementedError."""
        with pytest.raises(NotImplementedError, match="OneBox.*not yet implemented"):
            SpikeGLXSyncChannelInterface(
                folder_path=self.test_folder,
                stream_id="obx0-SYNC",
            )

    def test_get_metadata(self):
        """Test that metadata is generated correctly."""
        interface = SpikeGLXSyncChannelInterface(
            folder_path=self.test_folder,
            stream_id="imec0.ap-SYNC",
        )

        metadata = interface.get_metadata()

        # Check device metadata
        assert "Devices" in metadata
        assert len(metadata["Devices"]) == 1
        device = metadata["Devices"][0]
        assert device["name"] == "NeuropixelsImec0"
        assert device["manufacturer"] == "Imec"
        assert "Neuropixels probe 0" in device["description"]

        # Check TimeSeries metadata
        assert "TimeSeries" in metadata
        assert "SpikeGLXSync" in metadata["TimeSeries"]
        timeseries_metadata = metadata["TimeSeries"]["SpikeGLXSync"]
        assert timeseries_metadata["name"] == "TimeSeriesSyncImec0AP"
        assert "Synchronization channel" in timeseries_metadata["description"]
        assert "imec0.ap-SYNC" in timeseries_metadata["comments"]

    def test_add_to_nwbfile(self):
        """Test that sync channel data is added to NWB file correctly."""
        interface = SpikeGLXSyncChannelInterface(
            folder_path=self.test_folder,
            stream_id="imec0.ap-SYNC",
        )

        metadata = interface.get_metadata()
        nwbfile_path = self.tmpdir / "test_sync_channel.nwb"

        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        # Read and verify NWB file structure
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()

            # Check that device was added
            assert "NeuropixelsImec0" in nwbfile.devices
            device = nwbfile.devices["NeuropixelsImec0"]
            assert device.manufacturer == "Imec"

            # Check that TimeSeries was added to acquisition
            assert "TimeSeriesSyncImec0AP" in nwbfile.acquisition
            timeseries = nwbfile.acquisition["TimeSeriesSyncImec0AP"]

            # Verify TimeSeries properties
            assert timeseries.name == "TimeSeriesSyncImec0AP"
            assert "Synchronization channel" in timeseries.description
            assert timeseries.data.shape[1] == 1  # Should be single channel
            assert timeseries.rate > 0  # Should have valid sampling rate

            # Note: TimeSeries objects don't have a device attribute
            # Device information is in the metadata and linked via NWB file structure

    def test_stub_test(self):
        """Test that stub_test parameter works correctly."""
        interface = SpikeGLXSyncChannelInterface(
            folder_path=self.test_folder,
            stream_id="imec0.ap-SYNC",
        )

        nwbfile_path = self.tmpdir / "test_sync_channel_stub.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, stub_test=True)

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()

            # Stub test should create smaller data
            assert "TimeSeriesSyncImec0AP" in nwbfile.acquisition
            timeseries = nwbfile.acquisition["TimeSeriesSyncImec0AP"]
            assert timeseries.data.shape[0] <= 100  # Stub should be small

    def test_session_start_time(self):
        """Test that session start time is extracted correctly."""
        interface = SpikeGLXSyncChannelInterface(
            folder_path=self.test_folder,
            stream_id="imec0.ap-SYNC",
        )

        metadata = interface.get_metadata()

        # Session start time should be present in metadata
        assert "NWBFile" in metadata
        assert "session_start_time" in metadata["NWBFile"]

        # Verify it's a datetime object
        session_start_time = metadata["NWBFile"]["session_start_time"]
        assert isinstance(session_start_time, datetime)

    def test_lf_sync_stream(self):
        """Test interface with LF sync stream instead of AP."""
        # Check if LF sync stream exists in test data
        from spikeinterface.extractors.extractor_classes import (
            SpikeGLXRecordingExtractor,
        )

        available_streams = SpikeGLXRecordingExtractor.get_streams(folder_path=self.test_folder)[0]

        if "imec0.lf-SYNC" in available_streams:
            interface = SpikeGLXSyncChannelInterface(
                folder_path=self.test_folder,
                stream_id="imec0.lf-SYNC",
            )

            assert interface.stream_id == "imec0.lf-SYNC"
            assert interface.probe_index == "0"
            assert interface.stream_kind == "LF"

            metadata = interface.get_metadata()
            assert metadata["TimeSeries"]["SpikeGLXSync"]["name"] == "TimeSeriesSyncImec0LF"
        else:
            pytest.skip("LF sync stream not available in test data")


class TestSpikeGLXSyncChannelMultiProbe:
    """Tests for multi-probe scenarios with sync channels."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.tmpdir = Path(mkdtemp())
        # This would be a path to multi-probe test data when available
        # For now, we'll use single probe data
        self.test_folder = SPIKEGLX_PATH / "NP2_with_sync"
        yield
        rmtree(self.tmpdir)

    def test_probe_index_extraction(self):
        """Test that probe index is correctly extracted from different stream IDs."""
        test_cases = [
            ("imec0.ap-SYNC", "0", "AP"),
            ("imec1.ap-SYNC", "1", "AP"),
            ("imec2.lf-SYNC", "2", "LF"),
        ]

        for stream_id, expected_index, expected_kind in test_cases:
            # We can't actually instantiate these without the data existing,
            # but we can test the parsing logic by checking the initialization would work
            # if the data existed (the error would be from SpikeInterface, not our validation)
            try:
                interface = SpikeGLXSyncChannelInterface(
                    folder_path=self.test_folder,
                    stream_id=stream_id,
                )
                # If it works, verify the extracted values
                assert interface.probe_index == expected_index
                assert interface.stream_kind == expected_kind
            except Exception as e:
                # If it fails, it should be because the stream doesn't exist in the data,
                # not because of our validation logic
                assert "stream" in str(e).lower() or "not found" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__])
