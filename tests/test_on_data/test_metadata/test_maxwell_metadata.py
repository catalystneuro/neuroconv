import os
import unittest
from tempfile import mkdtemp
from pathlib import Path
from shutil import rmtree
from dateutil import tz
from datetime import datetime

import pytest
from pynwb import NWBHDF5IO
from neuroconv.datainterfaces import MaxOneRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH, HDF5_PLUGIN_PATH


class TestMaxOneMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        hdf5_plugin_path = str(HDF5_PLUGIN_PATH)
        MaxOneRecordingInterface.auto_install_maxwell_hdf5_compression_plugin(hdf5_plugin_path=hdf5_plugin_path)
        os.environ["HDF5_PLUGIN_PATH"] = hdf5_plugin_path

        file_path = ECEPHY_DATA_PATH / "maxwell" / "MaxOne_data" / "Record" / "000011" / "data.raw.h5"
        cls.interface = MaxOneRecordingInterface(file_path=file_path)

        cls.tmpdir = Path(mkdtemp())
        cls.nwbfile_path = cls.tmpdir / "maxone_meadata_test.nwb"
        cls.metadata = cls.interface.get_metadata()
        cls.metadata["NWBFile"].update(
            session_start_time=datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
        )
        cls.interface.run_conversion(nwbfile_path=cls.nwbfile_path, metadata=cls.metadata)

    @classmethod
    def tearDownClass(cls):
        rmtree(cls.tmpdir)

    def test_neuroconv_metadata(self):
        assert len(self.metadata["Ecephys"]["Device"]) == 1
        assert self.metadata["Ecephys"]["Device"][0]["name"] == "DeviceEcephys"
        assert self.metadata["Ecephys"]["Device"][0]["description"] == "Recorded using Maxwell version '20190530'."


if __name__ == "__main__":
    unittest.main()
