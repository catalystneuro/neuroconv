import datetime
from unittest import TestCase
from shutil import rmtree
from tempfile import mkdtemp
from pathlib import Path
from datetime import datetime
from copy import deepcopy

from pynwb import NWBHDF5IO
from pydantic import FilePath

from neuroconv import ConverterPipe
from neuroconv.converters import SpikeGLXConverter
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

            expected_session_start_time = datetime(2020, 11, 3, 10, 35, 10).astimezone()
            assert nwbfile.session_start_time == expected_session_start_time

            assert "ElectricalSeriesAP" in nwbfile.acquisition
            assert "ElectricalSeriesLF" in nwbfile.acquisition
            assert "ElectricalSeriesNIDQ" in nwbfile.acquisition

            assert "Neuropixel-Imec" in nwbfile.devices

            assert "NIDQChannelGroup" in nwbfile.electrode_groups
            assert "s0" in nwbfile.electrode_groups

    def test_single_probe_spikeglx_converter(self):
        converter = SpikeGLXConverter(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
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
        spikeglx_converter = SpikeGLXConverter(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
        converter_pipe = ConverterPipe(data_interfaces=[spikeglx_converter])

        nwbfile_path = self.tmpdir / "test_spikeglx_converter_in_converter_pipe.nwb"
        converter_pipe.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path)
