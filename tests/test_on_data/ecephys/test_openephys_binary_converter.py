from datetime import datetime

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

    def test_streams_argument_filters_data(self):
        all_streams = OpenEphysBinaryConverter.get_streams(folder_path=self.folder_path)
        neural_only = [s for s in all_streams if "NI-DAQ" not in s]

        converter = OpenEphysBinaryConverter(folder_path=self.folder_path, streams=neural_only)
        conversion_options = {name: dict(stub_test=True) for name in converter.data_interface_objects}
        nwbfile = converter.create_nwbfile(conversion_options=conversion_options)

        assert "ElectricalSeriesProbeAAP" in nwbfile.acquisition
        assert "ElectricalSeriesProbeALFP" in nwbfile.acquisition
        assert "TimeSeriesPXIe6341" not in nwbfile.acquisition
        assert len(nwbfile.acquisition) == 4
