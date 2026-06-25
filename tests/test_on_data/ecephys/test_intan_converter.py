"""Tests for IntanConverter — auto-discovery and routing of Intan streams."""

from datetime import datetime

import pytest
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.converters import IntanConverter

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


INTAN_PATH = ECEPHY_DATA_PATH / "intan"

RHS_TRADITIONAL = INTAN_PATH / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
RHD_FILE_PER_SIGNAL = INTAN_PATH / "intan_fps_test_231117_052500" / "info.rhd"
RHS_FILE_PER_SIGNAL = INTAN_PATH / "intan_fps_rhs_test_240329_091536" / "info.rhs"
SPLIT_FOLDER = INTAN_PATH / "test_tetrode_240502_162925"


class TestIntanConverter:
    """What the converter adds to an NWBFile: each routed stream becomes the expected object in
    the right group. Assertions are made in memory via `add_to_nwbfile`; the one disk roundtrip
    below is an integration smoke test that the combined multi-stream file serializes and reopens."""

    def test_rhs_traditional_roundtrip(self, tmp_path):
        # Disk roundtrip: the only test that writes and reads back, guarding against write-time
        # collisions when several streams (amplifier, ADC in/out, stim) land in one file.
        converter = IntanConverter(file_path=RHS_TRADITIONAL)

        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        nwbfile_path = tmp_path / "intan_converter.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)

        # Amplifier traces (name = es_key) and ADC in/out TimeSeries (PascalCase from stream_info).
        expected_containers_in_acquisition = [
            "ElectricalSeries",
            "TimeSeriesIntanADCInput",
            "TimeSeriesIntanADCOutput",
        ]
        for container_name in expected_containers_in_acquisition:
            assert container_name in nwbfile.acquisition
        # Stim as TimeSeries in stimulus (name hardcoded in IntanStimInterface).
        assert "TimeSeriesIntanStim" in nwbfile.stimulus
        # Single Intan device.
        assert list(nwbfile.devices.keys()) == ["Intan"]

    def test_rhd_file_per_signal_add_to_nwbfile(self):
        """RHD2000 amplifier channel + auxiliary input channel land in acquisition."""
        converter = IntanConverter(file_path=RHD_FILE_PER_SIGNAL)
        nwbfile = mock_NWBFile()
        converter.add_to_nwbfile(nwbfile)

        assert "ElectricalSeries" in nwbfile.acquisition
        assert "TimeSeriesIntanAuxiliary" in nwbfile.acquisition
        assert "TimeSeriesIntanADCInput" in nwbfile.acquisition
        assert list(nwbfile.devices.keys()) == ["Intan"]

    def test_rhs_file_per_signal_add_to_nwbfile(self):
        """RHS file-per-signal is the only fixture that exercises the DC Amplifier channel stream."""
        converter = IntanConverter(file_path=RHS_FILE_PER_SIGNAL)
        nwbfile = mock_NWBFile()
        converter.add_to_nwbfile(nwbfile)

        assert "ElectricalSeries" in nwbfile.acquisition
        assert "TimeSeriesIntanADCInput" in nwbfile.acquisition
        assert "TimeSeriesIntanADCOutput" in nwbfile.acquisition
        assert "TimeSeriesIntanDC" in nwbfile.acquisition
        assert "TimeSeriesIntanStim" in nwbfile.stimulus
        assert list(nwbfile.devices.keys()) == ["Intan"]

    def test_split_files_add_to_nwbfile(self):
        """saved_files_are_split=True: sibling chunks are concatenated into one recording."""
        first_file = sorted(SPLIT_FOLDER.glob("*.rhd"))[0]
        converter = IntanConverter(file_path=first_file, saved_files_are_split=True)
        nwbfile = mock_NWBFile()
        converter.add_to_nwbfile(nwbfile)

        assert "ElectricalSeries" in nwbfile.acquisition
        assert list(nwbfile.devices.keys()) == ["Intan"]


class TestStreamDiscoveryAndRouting:
    """`get_streams` enumerates header streams; `__init__` routes the present ones to sub-interfaces."""

    def test_rhs_traditional_streams(self):
        streams = IntanConverter.get_streams(file_path=RHS_TRADITIONAL)
        assert "RHS2000 amplifier channel" in streams
        assert "USB board ADC input channel" in streams
        assert "Stim channel" in streams
        # Digital streams are present in the header but unrouted.
        assert "USB board digital input channel" in streams

    def test_rhs_traditional_routing(self):
        # Digital streams present in the header are skipped (no IntanDigitalInterface yet).
        converter = IntanConverter(file_path=RHS_TRADITIONAL)
        interface_names = set(converter.data_interface_objects.keys())
        assert interface_names == {"Recording", "AnalogADCInput", "AnalogADCOutput", "Stim"}

    def test_rhd_file_per_signal_routing(self):
        # Only fixture exercising the auxiliary stream.
        converter = IntanConverter(file_path=RHD_FILE_PER_SIGNAL)
        interface_names = set(converter.data_interface_objects.keys())
        assert interface_names == {"Recording", "AnalogAuxiliary", "AnalogADCInput"}

    def test_rhs_file_per_signal_routing(self):
        # Only fixture exercising the DC Amplifier stream.
        converter = IntanConverter(file_path=RHS_FILE_PER_SIGNAL)
        interface_names = set(converter.data_interface_objects.keys())
        assert interface_names == {"Recording", "AnalogADCInput", "AnalogADCOutput", "AnalogDC", "Stim"}

    def test_exclude_stim_stream(self):
        # exclude_streams takes a stream name ("Stim channel"); the dropped dict key is the
        # interface_name ("Stim") it routes to.
        converter = IntanConverter(file_path=RHS_TRADITIONAL, exclude_streams=["Stim channel"])
        interface_names = set(converter.data_interface_objects.keys())
        assert "Stim" not in interface_names
        assert "Recording" in interface_names

    def test_exclude_unknown_stream_raises(self):
        expected_message = "Cannot exclude streams ['bogus stream']: not present in intanTestFile.rhs."
        with pytest.raises(ValueError) as exception_info:
            IntanConverter(file_path=RHS_TRADITIONAL, exclude_streams=["bogus stream"])
        assert expected_message in str(exception_info.value)
