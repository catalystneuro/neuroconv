from datetime import datetime

from pynwb import read_nwb

from neuroconv.datainterfaces import IntanStimInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class TestIntanStimInterfaceSingleFile:
    """Single .rhs file format."""

    file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"

    def test_conversion(self, tmp_path):
        interface = IntanStimInterface(file_path=self.file_path)

        channel_names = interface.get_channel_names()
        assert len(channel_names) == 128
        assert all(name.endswith("_STIM") for name in channel_names)

        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        nwbfile_path = tmp_path / "stim.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)
        ts = nwbfile.stimulus["TimeSeriesIntanStim"]
        assert ts.unit == "A"
        assert ts.data.shape == (18432, 128)

    def test_get_metadata(self):
        interface = IntanStimInterface(file_path=self.file_path)
        metadata = interface.get_metadata()
        ts_meta = metadata["TimeSeries"][interface.metadata_key]
        assert ts_meta["description"] == (
            "Electrical stimulation current channels (RHS Stim/Recording System). "
            "Data are in Amperes. Channels are ["
            "'A-000_STIM', 'A-001_STIM', 'A-002_STIM', 'A-003_STIM', "
            "'A-004_STIM', 'A-005_STIM', 'A-006_STIM', 'A-007_STIM', "
            "'A-008_STIM', 'A-009_STIM', 'A-010_STIM', 'A-011_STIM', "
            "'A-012_STIM', 'A-013_STIM', 'A-014_STIM', 'A-015_STIM', "
            "'A-016_STIM', 'A-017_STIM', 'A-018_STIM', 'A-019_STIM', "
            "'A-020_STIM', 'A-021_STIM', 'A-022_STIM', 'A-023_STIM', "
            "'A-024_STIM', 'A-025_STIM', 'A-026_STIM', 'A-027_STIM', "
            "'A-028_STIM', 'A-029_STIM', 'A-030_STIM', 'A-031_STIM', "
            "'B-000_STIM', 'B-001_STIM', 'B-002_STIM', 'B-003_STIM', "
            "'B-004_STIM', 'B-005_STIM', 'B-006_STIM', 'B-007_STIM', "
            "'B-008_STIM', 'B-009_STIM', 'B-010_STIM', 'B-011_STIM', "
            "'B-012_STIM', 'B-013_STIM', 'B-014_STIM', 'B-015_STIM', "
            "'B-016_STIM', 'B-017_STIM', 'B-018_STIM', 'B-019_STIM', "
            "'B-020_STIM', 'B-021_STIM', 'B-022_STIM', 'B-023_STIM', "
            "'B-024_STIM', 'B-025_STIM', 'B-026_STIM', 'B-027_STIM', "
            "'B-028_STIM', 'B-029_STIM', 'B-030_STIM', 'B-031_STIM', "
            "'C-000_STIM', 'C-001_STIM', 'C-002_STIM', 'C-003_STIM', "
            "'C-004_STIM', 'C-005_STIM', 'C-006_STIM', 'C-007_STIM', "
            "'C-008_STIM', 'C-009_STIM', 'C-010_STIM', 'C-011_STIM', "
            "'C-012_STIM', 'C-013_STIM', 'C-014_STIM', 'C-015_STIM', "
            "'C-016_STIM', 'C-017_STIM', 'C-018_STIM', 'C-019_STIM', "
            "'C-020_STIM', 'C-021_STIM', 'C-022_STIM', 'C-023_STIM', "
            "'C-024_STIM', 'C-025_STIM', 'C-026_STIM', 'C-027_STIM', "
            "'C-028_STIM', 'C-029_STIM', 'C-030_STIM', 'C-031_STIM', "
            "'D-000_STIM', 'D-001_STIM', 'D-002_STIM', 'D-003_STIM', "
            "'D-004_STIM', 'D-005_STIM', 'D-006_STIM', 'D-007_STIM', "
            "'D-008_STIM', 'D-009_STIM', 'D-010_STIM', 'D-011_STIM', "
            "'D-012_STIM', 'D-013_STIM', 'D-014_STIM', 'D-015_STIM', "
            "'D-016_STIM', 'D-017_STIM', 'D-018_STIM', 'D-019_STIM', "
            "'D-020_STIM', 'D-021_STIM', 'D-022_STIM', 'D-023_STIM', "
            "'D-024_STIM', 'D-025_STIM', 'D-026_STIM', 'D-027_STIM', "
            "'D-028_STIM', 'D-029_STIM', 'D-030_STIM', 'D-031_STIM'] in that order. "
            "Stim step size: 4.999999987376214e-07 A, "
            "charge recovery mode: 0, "
            "amplifier settle mode: 0, "
            "recovery current limit: 9.99999993922529e-09 A, "
            "recovery target voltage: 0.0 V."
        )


class TestIntanStimInterfaceFilePerChannel:
    """File-per-channel format."""

    file_path = ECEPHY_DATA_PATH / "intan" / "test_fpc_stim_250327_151617" / "info.rhs"

    def test_conversion(self, tmp_path):
        interface = IntanStimInterface(file_path=self.file_path)

        channel_names = interface.get_channel_names()
        assert channel_names == ["A-000_STIM", "A-001_STIM", "A-002_STIM", "A-003_STIM"]

        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        nwbfile_path = tmp_path / "stim.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)
        ts = nwbfile.stimulus["TimeSeriesIntanStim"]
        assert ts.unit == "A"
        assert ts.data.shape == (68352, 4)

    def test_get_metadata(self):
        interface = IntanStimInterface(file_path=self.file_path)
        metadata = interface.get_metadata()

        device = metadata["Devices"][0]
        assert device["name"] == "Intan"
        assert device["manufacturer"] == "Intan"
        assert device["description"] == "RHS Stim/Recording System"

        ts_meta = metadata["TimeSeries"][interface.metadata_key]
        assert ts_meta["name"] == "TimeSeriesIntanStim"
        assert ts_meta["description"] == (
            "Electrical stimulation current channels (RHS Stim/Recording System). "
            "Data are in Amperes. Channels are ['A-000_STIM', 'A-001_STIM', 'A-002_STIM', 'A-003_STIM'] in that order. "
            "Stim step size: 4.999999987376214e-07 A, "
            "charge recovery mode: 0, "
            "amplifier settle mode: 0, "
            "recovery current limit: 9.99999993922529e-09 A, "
            "recovery target voltage: 0.0 V."
        )


class TestIntanStimInterfaceFilePerSignal:
    """File-per-signal format."""

    file_path = ECEPHY_DATA_PATH / "intan" / "rhs_fpc_multistim_240514_082243" / "rhs_fpc_multistim_240514_082243.rhs"

    def test_conversion(self, tmp_path):
        interface = IntanStimInterface(file_path=self.file_path)

        channel_names = interface.get_channel_names()
        assert len(channel_names) == 8
        assert all(name.endswith("_STIM") for name in channel_names)

        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        nwbfile_path = tmp_path / "stim.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)
        ts = nwbfile.stimulus["TimeSeriesIntanStim"]
        assert ts.unit == "A"
        assert ts.data.shape == (92928, 8)

    def test_get_metadata(self):
        interface = IntanStimInterface(file_path=self.file_path)
        metadata = interface.get_metadata()
        ts_meta = metadata["TimeSeries"][interface.metadata_key]
        assert ts_meta["description"] == (
            "Electrical stimulation current channels (RHS Stim/Recording System). "
            "Data are in Amperes. Channels are "
            "['A-000_STIM', 'A-001_STIM', 'A-002_STIM', 'A-003_STIM', "
            "'B-000_STIM', 'B-001_STIM', 'B-002_STIM', 'B-003_STIM'] in that order. "
            "Stim step size: 4.999999987376214e-07 A, "
            "charge recovery mode: 0, "
            "amplifier settle mode: 0, "
            "recovery current limit: 9.99999993922529e-09 A, "
            "recovery target voltage: 0.0 V."
        )


def test_custom_metadata_key():
    """Custom metadata_key propagates to the metadata dict."""
    file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
    interface = IntanStimInterface(file_path=file_path, metadata_key="MyStimTimeSeries")

    assert interface.metadata_key == "MyStimTimeSeries"
    assert "MyStimTimeSeries" in interface.get_metadata()["TimeSeries"]


def test_stub_conversion(tmp_path):
    """stub_test=True writes at most 100 samples."""
    file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
    interface = IntanStimInterface(file_path=file_path)

    metadata = interface.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
    nwbfile_path = tmp_path / "stim_stub.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True, stub_test=True)

    nwbfile = read_nwb(nwbfile_path)
    ts = nwbfile.stimulus["TimeSeriesIntanStim"]
    assert ts.data.shape[0] <= 100
    assert ts.data.shape[1] == 128
