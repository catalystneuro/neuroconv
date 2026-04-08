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


def test_get_metadata():
    """Device info, TimeSeries structure, and description content."""
    file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
    interface = IntanStimInterface(file_path=file_path)
    metadata = interface.get_metadata()

    device = metadata["Devices"][0]
    assert device["name"] == "Intan"
    assert device["manufacturer"] == "Intan"
    assert device["description"] == "RHS Stim/Recording System"

    ts_meta = metadata["TimeSeries"][interface.metadata_key]
    assert ts_meta["name"] == "TimeSeriesIntanStim"
    assert ts_meta["description"].startswith("Electrical stimulation current channels")


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
