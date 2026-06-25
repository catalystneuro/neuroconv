"""Tests for IntanConverter — auto-discovery and routing of Intan streams."""

from datetime import datetime

import pytest
from pynwb import read_nwb

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


class TestStreamDiscoveryAndRouting:
    """`get_streams` enumerates header streams; `__init__` routes the present ones to sub-interfaces."""

    def test_rhs_traditional_streams(self):
        streams = IntanConverter.get_streams(file_path=RHS_TRADITIONAL)
        assert "RHS2000 amplifier channel" in streams
        assert "USB board ADC input channel" in streams
        assert "Stim channel" in streams
        # Digital streams are present in the header but unrouted.
        assert "USB board digital input channel" in streams

    @pytest.mark.parametrize(
        "file_path, expected_keys",
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
    def test_routing(self, file_path, expected_keys):
        converter = IntanConverter(file_path=file_path)
        assert set(converter.data_interface_objects.keys()) == expected_keys

    def test_exclude_stim_stream(self):
        converter = IntanConverter(file_path=RHS_TRADITIONAL, exclude_streams=["Stim channel"])
        keys = set(converter.data_interface_objects.keys())
        assert "Stim" not in keys
        assert "Recording" in keys

    def test_exclude_unknown_stream_raises(self):
        with pytest.raises(ValueError, match="not present"):
            IntanConverter(file_path=RHS_TRADITIONAL, exclude_streams=["bogus stream"])


class TestMetadataMerging:
    """The converter merges the sub-interface metadata into one dict: duplicate devices
    collapse to one, and each sub-interface's entry lands under its converter-assigned key."""

    def test_device_deduplicated(self):
        # Every sub-interface emits the same Intan device; the merge must collapse them to one.
        converter = IntanConverter(file_path=RHS_TRADITIONAL)
        metadata = converter.get_metadata()
        assert len(metadata["Devices"]) == 1
        assert metadata["Devices"][0]["name"] == "Intan"
        assert metadata["Ecephys"]["Device"] == metadata["Devices"]

    def test_metadata_keys_present(self):
        # Each routed stream lands under the metadata_key the converter assigned in _STREAM_TO_INTERFACE.
        converter = IntanConverter(file_path=RHS_TRADITIONAL)
        metadata = converter.get_metadata()
        assert set(metadata["TimeSeries"].keys()) == {
            "time_series_intan_adc_input",
            "time_series_intan_adc_output",
            "time_series_intan_stim",
        }
        assert "intan_amplifier" in metadata["Ecephys"]


class TestFullConversion:
    """End-to-end: discover, convert, read back, verify all expected NWB objects exist."""

    def test_rhs_traditional_roundtrip(self, tmp_path):
        converter = IntanConverter(file_path=RHS_TRADITIONAL)

        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        nwbfile_path = tmp_path / "intan_converter.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)

        # Amplifier traces in acquisition (name = es_key = "electrical_series").
        assert "ElectricalSeries" in nwbfile.acquisition
        # ADC in/out as TimeSeries in acquisition (name from stream_info, PascalCase).
        assert "TimeSeriesIntanADCInput" in nwbfile.acquisition
        assert "TimeSeriesIntanADCOutput" in nwbfile.acquisition
        # Stim as TimeSeries in stimulus (name hardcoded in IntanStimInterface).
        assert "TimeSeriesIntanStim" in nwbfile.stimulus
        # Single Intan device.
        assert list(nwbfile.devices.keys()) == ["Intan"]

    def test_rhd_file_per_signal_roundtrip(self, tmp_path):
        """RHD2000 amplifier channel + auxiliary input channel are written correctly."""
        converter = IntanConverter(file_path=RHD_FILE_PER_SIGNAL)

        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        nwbfile_path = tmp_path / "intan_rhd_fps.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)

        assert "ElectricalSeries" in nwbfile.acquisition
        assert "TimeSeriesIntanAuxiliary" in nwbfile.acquisition
        assert "TimeSeriesIntanADCInput" in nwbfile.acquisition
        assert list(nwbfile.devices.keys()) == ["Intan"]

    def test_rhs_file_per_signal_roundtrip(self, tmp_path):
        """RHS file-per-signal is the only fixture that exercises the DC Amplifier channel stream."""
        converter = IntanConverter(file_path=RHS_FILE_PER_SIGNAL)

        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        nwbfile_path = tmp_path / "intan_rhs_fps.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)

        assert "ElectricalSeries" in nwbfile.acquisition
        assert "TimeSeriesIntanADCInput" in nwbfile.acquisition
        assert "TimeSeriesIntanADCOutput" in nwbfile.acquisition
        assert "TimeSeriesIntanDC" in nwbfile.acquisition
        assert "TimeSeriesIntanStim" in nwbfile.stimulus
        assert list(nwbfile.devices.keys()) == ["Intan"]

    def test_split_files_roundtrip(self, tmp_path):
        """saved_files_are_split=True end-to-end: chunks are concatenated and written as one recording."""
        first_file = sorted(SPLIT_FOLDER.glob("*.rhd"))[0]
        converter = IntanConverter(file_path=first_file, saved_files_are_split=True)

        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        nwbfile_path = tmp_path / "intan_split.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)

        assert "ElectricalSeries" in nwbfile.acquisition
        assert list(nwbfile.devices.keys()) == ["Intan"]
