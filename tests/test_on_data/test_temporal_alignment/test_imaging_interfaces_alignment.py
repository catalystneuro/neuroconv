from tempfile import mkdtemp
from shutil import rmtree
from pathlib import Path
from typing import Union, Dict
from datetime import datetime

import pytest
import numpy as np
from parameterized import parameterized, param
from numpy.testing import assert_array_equal, assert_array_almost_equal
from hdmf.testing import TestCase
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import (
    ScanImageImagingInterface,
    TiffImagingInterface,
    Hdf5ImagingInterface,
    SbxImagingInterface,
)

# enable to run locally in interactive mode
try:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH

if not OPHYS_DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {OPHYS_DATA_PATH}!")


class TestImagingInterfacesAlignment(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_folder = Path(mkdtemp())

    @classmethod
    def tearDownClass(cls):
        rmtree(cls.temporary_folder)

    imaging_interface_list = [
        param(
            data_interface=ScanImageImagingInterface,
            interface_kwargs=dict(
                file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "sample_scanimage.tiff")
            ),
        ),
    ]

    @parameterized.expand(imaging_interface_list)
    def test_get_timestamps(self, data_interface, interface_kwargs):
        """
        Just to ensure each interface can call .get_timestamps() without an error raising.

        Also, that it always returns non-empty.
        """
        interface = data_interface(**interface_kwargs)
        timestamps = interface.get_timestamps()

        assert len(timestamps) != 0

    @parameterized.expand(imaging_interface_list)
    def test_align_starting_time_internal(self, data_interface, interface_kwargs):
        interface = data_interface(**interface_kwargs)
        unaligned_timestamps = interface.get_timestamps()

        starting_time = 1.23
        interface.align_starting_time(starting_time=starting_time)

        aligned_timestamps = interface.get_timestamps()
        expected_timestamps = unaligned_timestamps + starting_time
        assert_array_equal(x=aligned_timestamps, y=expected_timestamps)

    @parameterized.expand(imaging_interface_list)
    def test_align_starting_time_external(self, data_interface, interface_kwargs):
        nwbfile_path = self.temporary_folder / f"{data_interface.__name__}_test_align_starting_time.nwb"

        interface = data_interface(**interface_kwargs)

        starting_time = 1.23
        interface.align_starting_time(starting_time=starting_time)

        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.acquisition["TwoPhotonSeries"].starting_time == starting_time
