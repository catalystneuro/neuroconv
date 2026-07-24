"""Tests for IntanConverter — auto-discovery and routing of Intan streams."""

import pytest
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
    the right group. Assertions are made in memory via `add_to_nwbfile` (serialization is pynwb's
    responsibility, tested there and in each sub-interface's own roundtrip)."""

    def test_rhs_traditional_add_to_nwbfile(self):
        converter = IntanConverter(file_path=RHS_TRADITIONAL)
        nwbfile = mock_NWBFile()
        converter.add_to_nwbfile(nwbfile)

        # Amplifier traces (name = es_key) and ADC in/out TimeSeries (PascalCase from stream_info).
        expected_series_in_acquisition = [
            "ElectricalSeries",
            "TimeSeriesIntanADCInput",
            "TimeSeriesIntanADCOutput",
        ]
        for container_name in expected_series_in_acquisition:
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

        expected_series_in_acquisition = [
            "ElectricalSeries",
            "TimeSeriesIntanAuxiliary",
            "TimeSeriesIntanADCInput",
        ]
        for container_name in expected_series_in_acquisition:
            assert container_name in nwbfile.acquisition
        assert list(nwbfile.devices.keys()) == ["Intan"]

    def test_rhs_file_per_signal_add_to_nwbfile(self):
        """RHS file-per-signal is the only fixture that exercises the DC Amplifier channel stream."""
        converter = IntanConverter(file_path=RHS_FILE_PER_SIGNAL)
        nwbfile = mock_NWBFile()
        converter.add_to_nwbfile(nwbfile)

        expected_series_in_acquisition = [
            "ElectricalSeries",
            "TimeSeriesIntanADCInput",
            "TimeSeriesIntanADCOutput",
            "TimeSeriesIntanDC",
        ]
        for container_name in expected_series_in_acquisition:
            assert container_name in nwbfile.acquisition
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

    def test_get_streams(self):
        streams = IntanConverter.get_streams(file_path=RHS_TRADITIONAL)
        assert "RHS2000 amplifier channel" in streams
        assert "USB board ADC input channel" in streams
        assert "Stim channel" in streams
        # Digital streams are present in the header but unrouted.
        assert "USB board digital input channel" in streams

    @pytest.mark.parametrize(
        "file_path, expected_interface_names",
        [
            # RHS traditional: digital streams present in the header are skipped (no IntanDigitalInterface yet).
            (RHS_TRADITIONAL, {"Recording", "AnalogADCInput", "AnalogADCOutput", "Stim"}),
            # Only fixture exercising the auxiliary stream.
            (RHD_FILE_PER_SIGNAL, {"Recording", "AnalogAuxiliary", "AnalogADCInput"}),
            # Only fixture exercising the DC Amplifier stream.
            (RHS_FILE_PER_SIGNAL, {"Recording", "AnalogADCInput", "AnalogADCOutput", "AnalogDC", "Stim"}),
        ],
        ids=["rhs_traditional", "rhd_file_per_signal", "rhs_file_per_signal"],
    )
    def test_interface_discovery(self, file_path, expected_interface_names):
        converter = IntanConverter(file_path=file_path)
        interface_names = set(converter.data_interface_objects.keys())
        assert interface_names == expected_interface_names

    def test_exclude_streams(self):
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
