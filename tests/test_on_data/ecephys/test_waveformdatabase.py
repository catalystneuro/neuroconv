
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from neuroconv.datainterfaces.ecephys.waveformdatabase.waveformdatainterface import WFDBDataInterface

from pynwb import NWBFile

WFDB_PATH = Path("/Users/daphnedequatrebarbes/Documents/Catalystneuro/ephy_testing_data")

class TestWFDBDataInterface:
    """Test suite for WFDBDataInterface."""

    def test_interface_initialization(self):
        """Test interface initialization."""
        # Test successful initialization
        wfdb_data_path = WFDB_PATH / "wfdb" / "100"
 
        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        assert interface.file_path == str(wfdb_data_path)
        assert hasattr(interface, '_record')
        assert hasattr(interface, '_is_multisegment')
        assert hasattr(interface, '_segments')

    def test_load_record(self):
        """Test record loading and caching."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "100"
 
        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        # First call should load the record
        record1 = interface._load_record()
        assert record1 is not None
        assert hasattr(record1, 'p_signal')
    

    def test_get_channel_info(self):
        """Test channel information extraction."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "100"
 
        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        channel_info = interface.get_channel_info()
        
        assert isinstance(channel_info, dict)
        assert "channel_names" in channel_info
        assert "units" in channel_info
        assert "sampling_rates" in channel_info
        
        # Check specific values for MIT-BIH record 100
        assert len(channel_info["channel_names"]) == 2
        assert len(channel_info["units"]) == 2
        assert len(channel_info["sampling_rates"]) == 2
        
        # Check specific channel names
        assert "MLII" in channel_info["channel_names"]
        assert "V5" in channel_info["channel_names"]
        
        # Check specific units (both should be mV)
        assert all(unit == "mV" for unit in channel_info["units"])
        
        # Check specific sampling rates (both 360.0 Hz)
        assert all(rate == 360.0 for rate in channel_info["sampling_rates"])
        
        # Check data types
        assert all(isinstance(name, str) for name in channel_info["channel_names"])
        assert all(isinstance(unit, str) for unit in channel_info["units"])
        assert all(isinstance(rate, (float, type(None))) for rate in channel_info["sampling_rates"])

    def test_get_session_start_time(self):
        """Test session start time extraction."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "100"
 
        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        start_time = interface.get_session_start_time()
        
        # Should return None or datetime
        assert isinstance(start_time, datetime) or start_time is None

    def test_metadata_extraction(self):
        """Test metadata extraction."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "100"
 
        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        # Test full metadata
        metadata= interface.get_metadata()
        assert isinstance(metadata, dict)
        assert "NWBFile" in metadata
        
        # Check specific NWBFile metadata content for MIT-BIH 100
        nwb_meta = metadata["NWBFile"]
        
        # Should have session_id as record name
        assert nwb_meta.get("session_id") == "100"
        
        # Should have specific session description mentioning 2 channels and 360 Hz
        session_desc = nwb_meta.get("session_description", "")
        assert "2 channel recording" in session_desc
        assert "360.0 Hz" in session_desc
        assert "1805.56 seconds" in session_desc
        
        # Should have experiment description with format info
        exp_desc = nwb_meta.get("experiment_description", "")
        assert "212" in exp_desc  # Data format
        assert "100.dat" in exp_desc  # Source file
        
        # Should have notes with comments
        notes = nwb_meta.get("notes", "")
        assert "69 M 1085 1629 x1" in notes or "Aldomet, Inderal" in notes
        
        # Check required keys exist and have proper types
        required_keys = ["session_description", "experiment_description"]
        for key in required_keys:
            assert key in nwb_meta
            assert isinstance(nwb_meta[key], str)
            assert len(nwb_meta[key]) > 0

    def test_add_to_nwbfile_single_segment(self):
        """Test adding single-segment data to NWB file."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "100"
 
        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        metadata = interface.get_metadata()
        session_start_time = interface.get_session_start_time() or datetime.now()
        
        nwbfile = NWBFile(
            session_description="Test session",
            identifier="test_wfdb",
            session_start_time=session_start_time
        )
        
        # Add data to NWB file
        interface.add_to_nwbfile(nwbfile, metadata)
        
        # Check specific number of TimeSeries for MIT-BIH 100 (should be 2: MLII and V5)
        assert len(nwbfile.acquisition) == 2
        
        # Check for specific channel names
        assert "MLII" in nwbfile.acquisition
        assert "V5" in nwbfile.acquisition
        
        # Verify each TimeSeries has expected properties
        for name, ts in nwbfile.acquisition.items():
            assert hasattr(ts, 'data')
            assert hasattr(ts, 'rate')
            assert hasattr(ts, 'unit')
            
            # Check specific data shape (650000 samples for MIT-BIH 100)
            assert ts.data.shape[0] == 650000
            
            # Check specific sampling rate
            assert ts.rate == 360.0
            
            # Check specific unit
            assert ts.unit == "mV"

    def test_multisegment_detection(self):
        """Test multi-segment record detection."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "100"
 
        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        # For MIT-BIH record 100, this should specifically be False (single segment)
        assert interface._is_multisegment is False, "MIT-BIH 100 should be a single-segment record"
        
        # Since it's not multi-segment, segments list should be empty
        assert isinstance(interface._segments, list)
        assert len(interface._segments) == 0, "Single-segment record should have empty segments list"
