import unittest
from datetime import datetime
from pathlib import Path
from platform import python_version as get_python_version
from sys import platform
from tempfile import mkdtemp

import numpy as np
import pytest
from hdmf.testing import TestCase
from packaging.version import Version
from pynwb import NWBHDF5IO
from spikeinterface.extractors import NumpySorting

from neuroconv import NWBConverter
from neuroconv.datainterfaces import CEDRecordingInterface
from neuroconv.datainterfaces.ecephys.basesortingextractorinterface import (
    BaseSortingExtractorInterface,
)
from neuroconv.datainterfaces.ecephys.generatorrecordinginterface import (
    GeneratorRecordingInterface,
)

python_version = Version(get_python_version())


class TestRecordingInterface(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.single_segment_recording_interface = GeneratorRecordingInterface(durations=[0.100])
        cls.multi_segment_recording_interface = GeneratorRecordingInterface(durations=[0.100, 0.100])

    def test_stub_single_segment(self):
        interface = self.single_segment_recording_interface
        metadata = interface.get_metadata()
        interface.run_conversion(stub_test=True, metadata=metadata)

    def test_stub_multi_segment(self):
        interface = self.multi_segment_recording_interface
        metadata = interface.get_metadata()
        # Test that assertion is risen when the next statement is run
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg="Stub test and channel subset only supported for single segment recordings.",
        ):
            interface.run_conversion(stub_test=True, metadata=metadata)


class TestAssertions(TestCase):
    @pytest.mark.skipif(
        platform != "darwin" or python_version >= Version("3.8"),
        reason="Only testing on MacOSX with Python 3.7!",
    )
    def test_ced_import_assertions_python_3_7(self):
        with self.assertRaisesWith(
            exc_type=ModuleNotFoundError,
            exc_msg="\nThe package 'sonpy' is not available on the darwin platform for Python version 3.7!",
        ):
            CEDRecordingInterface.get_all_channels_info(file_path="does_not_matter.smrx")

    @pytest.mark.skipif(python_version.minor != 10, reason="Only testing with Python 3.10!")
    def test_ced_import_assertions_3_10(self):
        with self.assertRaisesWith(
            exc_type=ModuleNotFoundError,
            exc_msg="\nThe package 'sonpy' is not available for Python version 3.10!",
        ):
            CEDRecordingInterface.get_all_channels_info(file_path="does_not_matter.smrx")

    @pytest.mark.skipif(python_version.minor != 11, reason="Only testing with Python 3.11!")
    def test_ced_import_assertions_3_11(self):
        with self.assertRaisesWith(
            exc_type=ModuleNotFoundError,
            exc_msg="\nThe package 'sonpy' is not available for Python version 3.11!",
        ):
            CEDRecordingInterface.get_all_channels_info(file_path="does_not_matter.smrx")


class TestSortingInterface(unittest.TestCase):
    def setUp(self) -> None:
        self.sorting_start_frames = [100, 200, 300]
        self.num_frames = 1000
        times = np.array([], dtype="int")
        labels = np.array([], dtype="int")
        for i, start_frame in enumerate(self.sorting_start_frames):
            times_i = np.arange(start_frame, self.num_frames, dtype="int")
            labels_i = (i + 1) * np.ones_like(times_i, dtype="int")
            times = np.concatenate((times, times_i))
            labels = np.concatenate((labels, labels_i))
        sorting = NumpySorting.from_times_labels(times, labels, sampling_frequency=3000.0)

        class TestSortingInterface(BaseSortingExtractorInterface):
            ExtractorName = "NumpySorting"

            def __init__(self, verbose: bool = True):
                self.sorting_extractor = sorting
                self.source_data = dict()
                self.verbose = verbose

        class TempConverter(NWBConverter):
            data_interface_classes = dict(TestSortingInterface=TestSortingInterface)

        source_data = dict(TestSortingInterface=dict())
        self.test_sorting_interface = TempConverter(source_data)

    def test_sorting_stub(self):
        test_dir = Path(mkdtemp())
        minimal_nwbfile = test_dir / "stub_temp.nwb"
        conversion_options = dict(TestSortingInterface=dict(stub_test=True))
        metadata = self.test_sorting_interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        self.test_sorting_interface.run_conversion(
            nwbfile_path=minimal_nwbfile, metadata=metadata, conversion_options=conversion_options
        )
        with NWBHDF5IO(minimal_nwbfile, "r") as io:
            nwbfile = io.read()
            start_frame_max = np.max(self.sorting_start_frames)
            for i, start_times in enumerate(self.sorting_start_frames):
                assert len(nwbfile.units["spike_times"][i]) == (start_frame_max * 1.1) - start_times

    def test_sorting_full(self):
        test_dir = Path(mkdtemp())
        minimal_nwbfile = test_dir / "temp.nwb"
        metadata = self.test_sorting_interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        self.test_sorting_interface.run_conversion(nwbfile_path=minimal_nwbfile, metadata=metadata)
        with NWBHDF5IO(minimal_nwbfile, "r") as io:
            nwbfile = io.read()
            for i, start_times in enumerate(self.sorting_start_frames):
                assert len(nwbfile.units["spike_times"][i]) == self.num_frames - start_times
