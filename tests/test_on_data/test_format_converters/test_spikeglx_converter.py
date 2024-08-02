import datetime
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase

import numpy as np
from pydantic import FilePath
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import ConverterPipe, NWBConverter
from neuroconv.converters import SpikeGLXConverterPipe
from neuroconv.utils import load_dict_from_file

from ..setup_paths import ECEPHY_DATA_PATH

SPIKEGLX_PATH = ECEPHY_DATA_PATH / "spikeglx"


class TestSingleProbeSpikeGLXConverter(TestCase):
    maxDiff = None

    def setUp(self):
        self.tmpdir = Path(mkdtemp())

    def tearDown(self):
        rmtree(self.tmpdir)

    def assertNWBFileStructure(self, nwbfile_path: FilePath, expected_session_start_time: datetime):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.session_start_time == expected_session_start_time

            assert "ElectricalSeriesAPImec0" in nwbfile.acquisition
            assert "ElectricalSeriesLFImec0" in nwbfile.acquisition
            assert "ElectricalSeriesNIDQ" in nwbfile.acquisition
            assert len(nwbfile.acquisition) == 3

            assert "NeuropixelImec0" in nwbfile.devices
            assert "NIDQBoard" in nwbfile.devices
            assert len(nwbfile.devices) == 2

            assert "NIDQChannelGroup" in nwbfile.electrode_groups
            assert "Imec0Shank0" in nwbfile.electrode_groups
            assert len(nwbfile.electrode_groups) == 2

    def test_single_probe_spikeglx_converter(self):
        converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
        metadata = converter.get_metadata()

        test_metadata = deepcopy(metadata)
        for exclude_field in ["session_start_time", "identifier"]:
            test_metadata["NWBFile"].pop(exclude_field)
        expected_metadata = load_dict_from_file(file_path=Path(__file__).parent / "spikeglx_single_probe_metadata.json")

        # Exclude watermarks from testing assertions
        del test_metadata["NWBFile"]["source_script"]
        del test_metadata["NWBFile"]["source_script_file_name"]

        import json

        print(json.dumps(test_metadata, indent=2))

        assert test_metadata == expected_metadata

        nwbfile_path = self.tmpdir / "test_single_probe_spikeglx_converter.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        expected_session_start_time = datetime(2020, 11, 3, 10, 35, 10).astimezone()
        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, expected_session_start_time=expected_session_start_time)

    def test_in_converter_pipe(self):
        spikeglx_converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
        converter_pipe = ConverterPipe(data_interfaces=[spikeglx_converter])

        nwbfile_path = self.tmpdir / "test_spikeglx_converter_in_converter_pipe.nwb"
        converter_pipe.run_conversion(nwbfile_path=nwbfile_path)

        expected_session_start_time = datetime(2020, 11, 3, 10, 35, 10).astimezone()
        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, expected_session_start_time=expected_session_start_time)

    def test_in_nwbconverter(self):
        class TestConverter(NWBConverter):
            data_interface_classes = dict(SpikeGLX=SpikeGLXConverterPipe)

        source_data = dict(SpikeGLX=dict(folder_path=str(SPIKEGLX_PATH / "Noise4Sam_g0")))
        converter = TestConverter(source_data=source_data)

        # Relevant to https://github.com/catalystneuro/neuroconv/issues/919
        conversion_options_schema = converter.get_conversion_options_schema()
        assert len(conversion_options_schema["properties"]["SpikeGLX"]["properties"]) != 0

        nwbfile_path = self.tmpdir / "test_spikeglx_converter_in_nwbconverter.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path)

        expected_session_start_time = datetime(2020, 11, 3, 10, 35, 10).astimezone()
        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, expected_session_start_time=expected_session_start_time)


class TestMultiProbeSpikeGLXConverter(TestCase):
    maxDiff = None

    def setUp(self):
        self.tmpdir = Path(mkdtemp())

    def tearDown(self):
        rmtree(self.tmpdir)

    def assertNWBFileStructure(self, nwbfile_path: FilePath, expected_session_start_time: datetime):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        assert nwbfile.session_start_time == expected_session_start_time

        # TODO: improve name of segments using 'Segment{index}' for clarity
        assert "ElectricalSeriesAPImec00" in nwbfile.acquisition
        assert "ElectricalSeriesAPImec01" in nwbfile.acquisition
        assert "ElectricalSeriesAPImec10" in nwbfile.acquisition
        assert "ElectricalSeriesAPImec11" in nwbfile.acquisition
        assert "ElectricalSeriesLFImec00" in nwbfile.acquisition
        assert "ElectricalSeriesLFImec01" in nwbfile.acquisition
        assert "ElectricalSeriesLFImec10" in nwbfile.acquisition
        assert "ElectricalSeriesLFImec11" in nwbfile.acquisition
        assert len(nwbfile.acquisition) == 8

        assert "NeuropixelImec0" in nwbfile.devices
        assert "NeuropixelImec1" in nwbfile.devices
        assert len(nwbfile.devices) == 2

        assert "Imec0Shank0" in nwbfile.electrode_groups
        assert "Imec1Shank0" in nwbfile.electrode_groups
        assert len(nwbfile.electrode_groups) == 2

    def test_multi_probe_spikeglx_converter(self):
        converter = SpikeGLXConverterPipe(
            folder_path=SPIKEGLX_PATH / "multi_trigger_multi_gate" / "SpikeGLX" / "5-19-2022-CI0" / "5-19-2022-CI0_g0"
        )
        metadata = converter.get_metadata()

        test_metadata = deepcopy(metadata)
        for exclude_field in ["session_start_time", "identifier"]:
            test_metadata["NWBFile"].pop(exclude_field)
        expected_metadata = load_dict_from_file(file_path=Path(__file__).parent / "spikeglx_multi_probe_metadata.json")

        # Exclude watermarks from testing assertions
        del test_metadata["NWBFile"]["source_script"]
        del test_metadata["NWBFile"]["source_script_file_name"]

        assert test_metadata == expected_metadata

        nwbfile_path = self.tmpdir / "test_multi_probe_spikeglx_converter.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        expected_session_start_time = datetime(2022, 5, 19, 17, 37, 47).astimezone()
        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, expected_session_start_time=expected_session_start_time)


def test_electrode_table_writing(tmp_path):
    from spikeinterface.extractors.nwbextractors import NwbRecordingExtractor

    converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
    metadata = converter.get_metadata()

    nwbfile = mock_NWBFile()
    converter.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    electrodes_table = nwbfile.electrodes

    # Test NIDQ
    electrical_series = nwbfile.acquisition["ElectricalSeriesNIDQ"]
    nidq_electrodes_table_region = electrical_series.electrodes
    region_indices = nidq_electrodes_table_region.data
    recording_extractor = converter.data_interface_objects["nidq"].recording_extractor

    saved_channel_names = electrodes_table[region_indices]["channel_name"]
    expected_channel_names_nidq = recording_extractor.get_property("channel_name")
    np.testing.assert_array_equal(saved_channel_names, expected_channel_names_nidq)

    # Test AP
    electrical_series = nwbfile.acquisition["ElectricalSeriesAPImec0"]
    ap_electrodes_table_region = electrical_series.electrodes
    region_indices = ap_electrodes_table_region.data
    recording_extractor = converter.data_interface_objects["imec0.ap"].recording_extractor

    saved_channel_names = electrodes_table[region_indices]["channel_name"]
    expected_channel_names_ap = recording_extractor.get_property("channel_name")
    np.testing.assert_array_equal(saved_channel_names, expected_channel_names_ap)

    # Test LF
    electrical_series = nwbfile.acquisition["ElectricalSeriesLFImec0"]
    lf_electrodes_table_region = electrical_series.electrodes
    region_indices = lf_electrodes_table_region.data
    recording_extractor = converter.data_interface_objects["imec0.lf"].recording_extractor

    saved_channel_names = electrodes_table[region_indices]["channel_name"]
    expected_channel_names_lf = recording_extractor.get_property("channel_name")
    np.testing.assert_array_equal(saved_channel_names, expected_channel_names_lf)

    # Write to file and read back in
    temporary_folder = tmp_path / "test_folder"
    temporary_folder.mkdir()
    nwbfile_path = temporary_folder / "test_spikeglx_converter_electrode_table.nwb"
    with NWBHDF5IO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    # Test round trip with spikeinterface
    recording_extractor_ap = NwbRecordingExtractor(
        file_path=nwbfile_path,
        electrical_series_name="ElectricalSeriesAPImec0",
    )

    channel_ids = recording_extractor_ap.get_channel_ids()
    np.testing.assert_array_equal(channel_ids, expected_channel_names_ap)

    recording_extractor_lf = NwbRecordingExtractor(
        file_path=nwbfile_path,
        electrical_series_name="ElectricalSeriesLFImec0",
    )

    channel_ids = recording_extractor_lf.get_channel_ids()
    np.testing.assert_array_equal(channel_ids, expected_channel_names_lf)

    recording_extractor_nidq = NwbRecordingExtractor(
        file_path=nwbfile_path,
        electrical_series_name="ElectricalSeriesNIDQ",
    )

    channel_ids = recording_extractor_nidq.get_channel_ids()
    np.testing.assert_array_equal(channel_ids, expected_channel_names_nidq)
