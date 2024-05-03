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

    def assertNWBFileStructure(self, nwbfile_path: FilePath):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            expected_session_start_time = datetime(2020, 11, 3, 10, 35, 10)
            assert nwbfile.session_start_time == expected_session_start_time

            assert "ElectricalSeriesAP" in nwbfile.acquisition
            assert "ElectricalSeriesLF" in nwbfile.acquisition
            assert "ElectricalSeriesNIDQ" in nwbfile.acquisition

            assert "Neuropixel-Imec" in nwbfile.devices

            assert "NIDQChannelGroup" in nwbfile.electrode_groups
            assert "s0" in nwbfile.electrode_groups

    def test_single_probe_spikeglx_converter(self):
        converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
        # import json
        metadata = converter.get_metadata()

        test_metadata = deepcopy(metadata)
        for exclude_field in ["session_start_time", "identifier"]:
            test_metadata["NWBFile"].pop(exclude_field)
        expected_metadata = load_dict_from_file(file_path=Path(__file__).parent / "single_probe_metadata.json")
        self.assertDictEqual(d1=test_metadata, d2=expected_metadata)

        nwbfile_path = self.tmpdir / "test_spikeglx_converter.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path)

    def test_in_converter_pipe(self):
        spikeglx_converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
        converter_pipe = ConverterPipe(data_interfaces=[spikeglx_converter])

        nwbfile_path = self.tmpdir / "test_spikeglx_converter_in_converter_pipe.nwb"
        converter_pipe.run_conversion(nwbfile_path=nwbfile_path)

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path)

    def test_in_nwbconverter(self):
        class TestConverter(NWBConverter):
            data_interface_classes = dict(SpikeGLX=SpikeGLXConverterPipe)

        source_data = dict(SpikeGLX=dict(folder_path=str(SPIKEGLX_PATH / "Noise4Sam_g0")))
        converter_pipe = TestConverter(source_data=source_data)

        nwbfile_path = self.tmpdir / "test_spikeglx_converter_in_nwbconverter.nwb"
        converter_pipe.run_conversion(nwbfile_path=nwbfile_path)

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path)


def test_electrode_table_writing(tmp_path):
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
    electrical_series = nwbfile.acquisition["ElectricalSeriesAP"]
    ap_electrodes_table_region = electrical_series.electrodes
    region_indices = ap_electrodes_table_region.data
    recording_extractor = converter.data_interface_objects["imec0.ap"].recording_extractor

    saved_channel_names = electrodes_table[region_indices]["channel_name"]
    expected_channel_names_ap = recording_extractor.get_property("channel_name")
    np.testing.assert_array_equal(saved_channel_names, expected_channel_names_ap)

    # Test LF
    electrical_series = nwbfile.acquisition["ElectricalSeriesLF"]
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
    from spikeinterface.extractors.nwbextractors import NwbRecordingExtractor

    recording_extractor_ap = NwbRecordingExtractor(
        file_path=nwbfile_path,
        electrical_series_name="ElectricalSeriesAP",
    )

    channel_ids = recording_extractor_ap.get_channel_ids()
    np.testing.assert_array_equal(channel_ids, expected_channel_names_ap)

    recording_extractor_lf = NwbRecordingExtractor(
        file_path=nwbfile_path,
        electrical_series_name="ElectricalSeriesLF",
    )

    channel_ids = recording_extractor_lf.get_channel_ids()
    np.testing.assert_array_equal(channel_ids, expected_channel_names_lf)

    recording_extractor_nidq = NwbRecordingExtractor(
        file_path=nwbfile_path,
        electrical_series_name="ElectricalSeriesNIDQ",
    )

    channel_ids = recording_extractor_nidq.get_channel_ids()
    np.testing.assert_array_equal(channel_ids, expected_channel_names_nidq)
