from datetime import datetime

import pytest
from pynwb import read_nwb

from neuroconv.converters import OpenEphysBinaryConverter

from ..setup_paths import ECEPHY_DATA_PATH

OPENEPHYSBINARY_PATH = ECEPHY_DATA_PATH / "openephysbinary"


class TestNeuralAndAnalogMixed:
    """Test with a single neural stream and a single ADC stream."""

    folder_path = OPENEPHYSBINARY_PATH / "neural_and_non_neural_data_mixed"

    def test_metadata(self):
        converter = OpenEphysBinaryConverter(folder_path=self.folder_path)
        metadata = converter.get_metadata()

        assert metadata["NWBFile"]["session_start_time"] == datetime(2022, 7, 25, 15, 30, 0)

    def test_conversion(self, tmp_path):
        converter = OpenEphysBinaryConverter(folder_path=self.folder_path)

        assert len(converter.data_interface_objects) == 2

        nwbfile_path = tmp_path / "test_neural_and_analog_mixed.nwb"
        conversion_options = {name: dict(stub_test=True) for name in converter.data_interface_objects}
        converter.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        nwbfile = read_nwb(path=nwbfile_path)

        assert "ElectricalSeries0" in nwbfile.acquisition
        assert "TimeSeries0_ADC" in nwbfile.acquisition
        assert len(nwbfile.acquisition) == 2


class TestMultiStreamWithAnalog:
    """Test with NI-DAQ analog + Neuropixels AP/LFP streams."""

    folder_path = OPENEPHYSBINARY_PATH / "v0.6.x_neuropixels_with_sync"

    def test_metadata(self):
        converter = OpenEphysBinaryConverter(folder_path=self.folder_path)
        metadata = converter.get_metadata()

        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 8, 30, 23, 41, 36)

    def test_dict_metadata_keys_and_names_per_neural_stream(self):
        # Each stream needs a distinct entry and a distinct name. The interface supplies neither on its own:
        # it keys by a constant metadata_key and names every series "ElectricalSeries". The converter keys the
        # entries when it builds the interfaces and names the series in get_metadata.
        converter = OpenEphysBinaryConverter(folder_path=self.folder_path)

        expected_names_by_key = {
            "record_node_104_neuropix_pxi_100_probea_ap": "ElectricalSeriesProbeAAP",
            "record_node_104_neuropix_pxi_100_probea_lfp": "ElectricalSeriesProbeALFP",
            "record_node_104_neuropix_pxi_100_probea_apsync": "ElectricalSeriesProbeAAPSYNC",
            "record_node_104_neuropix_pxi_100_probea_lfpsync": "ElectricalSeriesProbeALFPSYNC",
        }

        metadata = converter.get_metadata(use_new_metadata_format=True)
        electrical_series_metadata = metadata["Ecephys"]["ElectricalSeries"]
        assert {key: entry["name"] for key, entry in electrical_series_metadata.items()} == expected_names_by_key

    def test_dict_metadata_conversion(self):
        # Writing every stream from one converter is what the naming above exists for: without it the streams
        # collide on a single "ElectricalSeries" name. This goes through create_nwbfile rather than
        # run_conversion because get_metadata_schema still describes the old list-based format, so dict-based
        # metadata does not pass validation yet (true of a lone interface as well, not just the converter).
        converter = OpenEphysBinaryConverter(folder_path=self.folder_path)
        metadata = converter.get_metadata(use_new_metadata_format=True)

        conversion_options = {name: dict(stub_test=True) for name in converter.data_interface_objects}
        nwbfile = converter.create_nwbfile(metadata=metadata, conversion_options=conversion_options)

        assert sorted(nwbfile.acquisition) == [
            "ElectricalSeriesProbeAAP",
            "ElectricalSeriesProbeAAPSYNC",
            "ElectricalSeriesProbeALFP",
            "ElectricalSeriesProbeALFPSYNC",
            "TimeSeriesPXIe6341",
        ]

    def test_conversion(self, tmp_path):
        converter = OpenEphysBinaryConverter(folder_path=self.folder_path)

        # NI-DAQ + ProbeA-AP + ProbeA-LFP + ProbeA-APSYNC + ProbeA-LFPSYNC
        assert len(converter.data_interface_objects) == 5

        nwbfile_path = tmp_path / "test_multi_stream_with_analog.nwb"
        conversion_options = {name: dict(stub_test=True) for name in converter.data_interface_objects}
        converter.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        nwbfile = read_nwb(path=nwbfile_path)

        assert "ElectricalSeriesProbeAAP" in nwbfile.acquisition
        assert "ElectricalSeriesProbeALFP" in nwbfile.acquisition
        assert "ElectricalSeriesProbeAAPSYNC" in nwbfile.acquisition
        assert "ElectricalSeriesProbeALFPSYNC" in nwbfile.acquisition
        assert "TimeSeriesPXIe6341" in nwbfile.acquisition
        assert len(nwbfile.acquisition) == 5

        # Both AP and LFP come from the same probe so they share electrode rows.
        # 384 probe channels + 2 SYNC channels = 386 electrodes
        assert len(nwbfile.electrodes) == 386
        ap_electrode_indices = list(nwbfile.acquisition["ElectricalSeriesProbeAAP"].electrodes.data)
        lfp_electrode_indices = list(nwbfile.acquisition["ElectricalSeriesProbeALFP"].electrodes.data)
        assert len(ap_electrode_indices) == 384
        assert len(lfp_electrode_indices) == 384
        assert ap_electrode_indices == lfp_electrode_indices

    def test_exclude_streams_filters_data(self):
        all_streams = OpenEphysBinaryConverter.get_streams(folder_path=self.folder_path)
        analog_streams = [s for s in all_streams if "NI-DAQ" in s]

        converter = OpenEphysBinaryConverter(folder_path=self.folder_path, exclude_streams=analog_streams)
        conversion_options = {name: dict(stub_test=True) for name in converter.data_interface_objects}
        nwbfile = converter.create_nwbfile(conversion_options=conversion_options)

        assert "ElectricalSeriesProbeAAP" in nwbfile.acquisition
        assert "ElectricalSeriesProbeALFP" in nwbfile.acquisition
        assert "TimeSeriesPXIe6341" not in nwbfile.acquisition
        assert len(nwbfile.acquisition) == 4

    def test_exclude_unknown_stream_raises(self):
        with pytest.raises(ValueError, match="not present"):
            OpenEphysBinaryConverter(folder_path=self.folder_path, exclude_streams=["bogus stream"])
