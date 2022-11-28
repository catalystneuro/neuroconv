import os
import unittest
from tempfile import mkdtemp
from pathlib import Path
from shutil import rmtree
from dateutil import tz
from datetime import datetime

from pynwb import NWBHDF5IO
from neuroconv.datainterfaces import MaxOneRecordingInterface, MaxTwoRecordingInterface

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
        metadata = cls.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific")))
        cls.interface.run_conversion(nwbfile_path=cls.nwbfile_path, metadata=metadata)

    @classmethod
    def tearDownClass(cls):
        rmtree(cls.tmpdir)

    def test_neuroconv_metadata(self):
        neuroconv_metadata = self.interface.get_metadata()

        assert len(neuroconv_metadata["Ecephys"]["Device"]) == 1
        assert neuroconv_metadata["Ecephys"]["Device"][0]["name"] == "device"
        assert neuroconv_metadata["Ecephys"]["Device"][0]["description"] == "Recorded using Maxwell version '20190530'."


class TestMaxTwoMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        hdf5_plugin_path = str(HDF5_PLUGIN_PATH)
        MaxOneRecordingInterface.auto_install_maxwell_hdf5_compression_plugin(hdf5_plugin_path=hdf5_plugin_path)
        os.environ["HDF5_PLUGIN_PATH"] = hdf5_plugin_path

        cls.file_path = ECEPHY_DATA_PATH / "maxwell" / "MaxTwo_data" / "Activity_Scan" / "000021" / "data.raw.h5"
        cls.interface = MaxTwoRecordingInterface(
            file_path=cls.file_path, recording_name="rec0000", stream_name="well000"
        )

        cls.tmpdir = Path(mkdtemp())
        cls.nwbfile_path = cls.tmpdir / "maxtwo_meadata_test.nwb"
        metadata = cls.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific")))
        cls.interface.run_conversion(nwbfile_path=cls.nwbfile_path, metadata=metadata)

    @classmethod
    def tearDownClass(cls):
        rmtree(cls.tmpdir)

    def test_recording_names_retrieval(self):
        recording_names = MaxTwoRecordingInterface.get_recording_names(file_path=self.file_path)

        expected_recording_names = ["rec0000", "rec0001"]
        self.assertListEqual(list1=recording_names, list2=expected_recording_names)

    def test_stream_names_retrieval_rec_1(self):
        stream_names = MaxTwoRecordingInterface.get_stream_names(file_path=self.file_path, recording_name="rec0000")

        expected_stream_names = ["well000", "well001", "well002", "well003", "well004", "well005"]
        self.assertListEqual(list1=stream_names, list2=expected_stream_names)

    def test_stream_names_retrieval_rec_2(self):
        stream_names = MaxTwoRecordingInterface.get_stream_names(file_path=self.file_path, recording_name="rec0001")

        expected_stream_names = ["well000", "well001", "well002", "well003", "well004", "well005"]
        self.assertListEqual(list1=stream_names, list2=expected_stream_names)

    def test_neuroconv_metadata(self):
        neuroconv_metadata = self.interface.get_metadata()

        assert len(neuroconv_metadata["Ecephys"]["Device"]) == 1
        assert neuroconv_metadata["Ecephys"]["Device"][0]["name"] == "device"
        assert neuroconv_metadata["Ecephys"]["Device"][0]["description"] == "Recorded using Maxwell version '20190530'."


if __name__ == "__main__":
    unittest.main()
