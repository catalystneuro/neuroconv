from datetime import datetime, time
from pathlib import Path

from pynwb import NWBFile

from neuroconv.datainterfaces.ecephys.waveformdatabase.waveformdatainterface import (
    WFDBDataInterface,
)

WFDB_PATH = Path("/Users/daphnedequatrebarbes/Documents/Catalystneuro/ephy_testing_data")


class TestWFDBDataInterface100:
    """Test suite for WFDBDataInterface."""

    def test_interface_initialization(self):
        """Test interface initialization."""
        # Test successful initialization
        wfdb_data_path = WFDB_PATH / "wfdb" / "100" / "100"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        assert interface.file_path == str(wfdb_data_path)
        assert hasattr(interface, "_record")
        assert hasattr(interface, "_is_multisegment")
        assert hasattr(interface, "_segments")

    def test_load_record(self):
        """Test record loading and caching."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "100" / "100"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        # First call should load the record
        record1 = interface._load_record()
        assert record1 is not None
        assert hasattr(record1, "p_signal")

    def test_get_channel_info(self):
        """Test channel information extraction."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "100" / "100"

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
        wfdb_data_path = WFDB_PATH / "wfdb" / "100" / "100"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        start_time = interface.get_session_start_time()

        # Should return None or datetime
        assert isinstance(start_time, datetime) or start_time is None

    def test_metadata_extraction(self):
        """Test metadata extraction."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "100" / "100"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        # Test full metadata
        metadata = interface.get_metadata()
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
        wfdb_data_path = WFDB_PATH / "wfdb" / "100" / "100"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        metadata = interface.get_metadata()
        session_start_time = interface.get_session_start_time() or datetime.now()

        nwbfile = NWBFile(
            session_description="Test session", identifier="test_wfdb", session_start_time=session_start_time
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
            assert hasattr(ts, "data")
            assert hasattr(ts, "rate")
            assert hasattr(ts, "unit")

            # Check specific data shape (650000 samples for MIT-BIH 100)
            assert ts.data.shape[0] == 650000

            # Check specific sampling rate
            assert ts.rate == 360.0

            # Check specific unit
            assert ts.unit == "mV"

    def test_multisegment_detection(self):
        """Test multi-segment record detection."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "100" / "100"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        # For MIT-BIH record 100, this should specifically be False (single segment)
        assert interface._is_multisegment is False, "MIT-BIH 100 should be a single-segment record"

        # Since it's not multi-segment, segments list should be empty
        assert isinstance(interface._segments, list)
        assert len(interface._segments) == 0, "Single-segment record should have empty segments list"


class TestWFDBDataInterface12726:
    """Test suite for WFDBDataInterface using record 12726."""

    def test_interface_initialization(self):
        """Test interface initialization."""
        # Test successful initialization
        wfdb_data_path = WFDB_PATH / "wfdb" / "12726" / "12726"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        assert interface.file_path == str(wfdb_data_path)
        assert hasattr(interface, "_record")
        assert hasattr(interface, "_is_multisegment")
        assert hasattr(interface, "_segments")

    def test_load_record(self):
        """Test record loading and caching."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "12726" / "12726"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        # First call should load the record
        record1 = interface._load_record()
        assert record1 is not None
        assert hasattr(record1, "p_signal")

    def test_get_channel_info(self):
        """Test channel information extraction."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "12726" / "12726"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        channel_info = interface.get_channel_info()

        assert isinstance(channel_info, dict)
        assert "channel_names" in channel_info
        assert "units" in channel_info
        assert "sampling_rates" in channel_info

        # Check specific values for record 12726
        assert len(channel_info["channel_names"]) == 3
        assert len(channel_info["units"]) == 3
        assert len(channel_info["sampling_rates"]) == 3

        # Check specific channel names
        assert "ABP" in channel_info["channel_names"]
        assert "ECG" in channel_info["channel_names"]
        assert "Angle" in channel_info["channel_names"]

        # Check specific units
        expected_units = ["mmHg", "mV", "degrees"]
        for unit in channel_info["units"]:
            assert unit in expected_units

        # Check specific sampling rates (all 250.0 Hz)
        assert all(rate == 250.0 for rate in channel_info["sampling_rates"])

        # Check data types
        assert all(isinstance(name, str) for name in channel_info["channel_names"])
        assert all(isinstance(unit, str) for unit in channel_info["units"])
        assert all(isinstance(rate, (float, type(None))) for rate in channel_info["sampling_rates"])

    def test_get_session_start_time(self):
        """Test session start time extraction."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "12726" / "12726"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        start_time = interface.get_session_start_time()

        # Should return None or datetime
        assert isinstance(start_time, datetime) or start_time is None

    def test_metadata_extraction(self):
        """Test metadata extraction."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "12726" / "12726"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        # Test metadata extraction (without the include_ecephys_metadata parameter)
        metadata = interface.get_metadata()
        assert isinstance(metadata, dict)
        assert "NWBFile" in metadata

        # Check specific NWBFile metadata content for record 12726
        nwb_meta = metadata["NWBFile"]

        # Should have session_id as record name
        assert nwb_meta.get("session_id") == "12726"

        # Should have specific session description mentioning 3 channels and 250 Hz
        session_desc = nwb_meta.get("session_description", "")
        assert "3 channel recording" in session_desc
        assert "250.0 Hz" in session_desc
        assert "3300.00 seconds" in session_desc

        # Should have experiment description with format info
        exp_desc = nwb_meta.get("experiment_description", "")
        assert "16" in exp_desc  # Data format
        assert "12726.dat" in exp_desc  # Source file

        # Should have notes with patient info
        notes = nwb_meta.get("notes", "")
        assert "28" in notes  # age
        assert "M" in notes  # sex
        assert "170" in notes  # height
        assert "64" in notes  # weight

        # Should have data collection info with ADC gains
        data_collection = nwb_meta.get("data_collection", "")
        assert "64.02" in data_collection  # ABP ADC gain
        assert "6554.0" in data_collection  # ECG ADC gain
        assert "174.83" in data_collection  # Angle ADC gain

        # Check required keys exist and have proper types
        required_keys = ["session_description", "experiment_description"]
        for key in required_keys:
            assert key in nwb_meta
            assert isinstance(nwb_meta[key], str)
            assert len(nwb_meta[key]) > 0

    def test_add_to_nwbfile_single_segment(self):
        """Test adding single-segment data to NWB file."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "12726" / "12726"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        metadata = interface.get_metadata()
        session_start_time = interface.get_session_start_time() or datetime.now()

        nwbfile = NWBFile(
            session_description="Test session", identifier="test_wfdb", session_start_time=session_start_time
        )

        # Add data to NWB file
        interface.add_to_nwbfile(nwbfile, metadata)

        # Check specific number of TimeSeries for record 12726 (should be 3: ABP, ECG, Angle)
        assert len(nwbfile.acquisition) == 3

        # Check for specific channel names
        assert "ABP" in nwbfile.acquisition
        assert "ECG" in nwbfile.acquisition
        assert "Angle" in nwbfile.acquisition

        # Verify each TimeSeries has expected properties
        expected_units = {"ABP": "mmHg", "ECG": "mV", "Angle": "degrees"}

        for name, ts in nwbfile.acquisition.items():
            assert hasattr(ts, "data")
            assert hasattr(ts, "rate")
            assert hasattr(ts, "unit")

            # Check specific data shape (825000 samples for record 12726)
            assert ts.data.shape[0] == 825000

            # Check specific sampling rate
            assert ts.rate == 250.0

            # Check specific unit matches expected for each channel
            assert ts.unit == expected_units[name]

    def test_multisegment_detection(self):
        """Test multi-segment record detection."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "12726" / "12726"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        # For record 12726, this should be False (single segment)
        assert interface._is_multisegment is False, "Record 12726 should be a single-segment record"

        # Since it's not multi-segment, segments list should be empty
        assert isinstance(interface._segments, list)
        assert len(interface._segments) == 0, "Single-segment record should have empty segments list"

    def test_signal_data_properties(self):
        """Test signal data properties specific to record 12726."""
        wfdb_data_path = WFDB_PATH / "wfdb" / "12726" / "12726"

        interface = WFDBDataInterface(file_path=str(wfdb_data_path))
        record = interface._load_record()

        # Test specific properties of record 12726
        assert record.record_name == "12726"
        assert record.n_sig == 3
        assert record.fs == 250.0
        assert record.sig_len == 825000

        # Test signal data exists and has correct shape
        assert hasattr(record, "p_signal")
        assert record.p_signal is not None
        assert record.p_signal.shape == (825000, 3)

        # Test data formats
        expected_formats = ["16", "16", "16"]
        assert record.fmt == expected_formats

        # Test base time
        assert record.base_time == time(15, 8, 24)

        # Test base date is None
        assert record.base_date is None

        # Test comments contain patient information
        comments = record.comments
        if comments:
            comments_str = str(comments[0]) if isinstance(comments, list) else str(comments)
            assert "28" in comments_str  # age
            assert "M" in comments_str  # sex
