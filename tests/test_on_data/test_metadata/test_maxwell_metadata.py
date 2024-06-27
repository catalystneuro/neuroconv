import unittest
from datetime import datetime
from pathlib import Path
from platform import system
from shutil import rmtree
from tempfile import mkdtemp
from zoneinfo import ZoneInfo

import pytest
from hdmf.testing import TestCase

from neuroconv.datainterfaces import MaxOneRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH


@pytest.mark.skipif(system() == "Linux", reason="Specific tests for raising assertion on non-linux systems.")
class TestMaxOneAssertion(TestCase):
    def test_max_one_usage_assertion(self):
        with self.assertRaisesWith(
            exc_type=NotImplementedError,
            exc_msg="The MaxOneRecordingInterface has not yet been implemented for systems other than Linux.",
        ):
            file_path = ECEPHY_DATA_PATH / "maxwell" / "MaxOne_data" / "Record" / "000011" / "data.raw.h5"
            MaxOneRecordingInterface(file_path=file_path)


@pytest.mark.skip(reason="Stochastically fails to download compression library.")
# @pytest.mark.skipif(system() != "Linux", reason="MaxOne only works on Linux at the moment.")
class TestMaxOneMetadata(TestCase):
    @classmethod
    def setUpClass(cls):
        file_path = ECEPHY_DATA_PATH / "maxwell" / "MaxOne_data" / "Record" / "000011" / "data.raw.h5"
        cls.interface = MaxOneRecordingInterface(file_path=file_path)

        cls.tmpdir = Path(mkdtemp())
        cls.nwbfile_path = cls.tmpdir / "maxone_meadata_test.nwb"
        cls.metadata = cls.interface.get_metadata()
        cls.metadata["NWBFile"].update(
            session_start_time=datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
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
