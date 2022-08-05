import unittest
from platform import python_version
from sys import platform
from packaging import version
from tempfile import mkdtemp
from pathlib import Path
from datetime import datetime

import numpy as np
import pytest
import spikeextractors as se
from spikeextractors.testing import check_recordings_equal, check_sortings_equal
from hdmf.testing import TestCase
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.datainterfaces.ecephys.ced import CEDRecordingInterface
from neuroconv.datainterfaces.ecephys.spikeinterface.sipickledatainterfaces import SIPickleRecordingExtractorInterface, \
    SIPickleSortingExtractorInterface
from neuroconv.datainterfaces.ecephys.tutorial import RecordingTutorialInterface, SortingTutorialInterface
from neuroconv.datainterfaces.ecephys.basesortingextractorinterface import BaseSortingExtractorInterface


class TestAssertions(TestCase):
    def test_import_assertions(self):
        if platform == "darwin" and version.parse(python_version()) < version.parse("3.8"):
            with self.assertRaisesWith(
                exc_type=AssertionError,
                exc_msg="The sonpy package (CED dependency) is not available on Mac for Python versions below 3.8!",
            ):
                CEDRecordingInterface.get_all_channels_info(file_path="does_not_matter.smrx")
        else:
            pytest.skip("Not testing on MacOSX with Python<3.8!")


def test_tutorials():
    class TutorialNWBConverter(NWBConverter):
        data_interface_classes = dict(
            RecordingTutorial=RecordingTutorialInterface, SortingTutorial=SortingTutorialInterface
        )

    duration = 10.0  # Seconds
    num_channels = 4
    num_units = 10
    sampling_frequency = 30000.0  # Hz
    stub_test = False
    test_dir = Path(mkdtemp())
    nwbfile_path = str(test_dir / "TestTutorial.nwb")
    source_data = dict(
        RecordingTutorial=dict(duration=duration, num_channels=num_channels, sampling_frequency=sampling_frequency),
        SortingTutorial=dict(duration=duration, num_units=num_units, sampling_frequency=sampling_frequency),
    )
    converter = TutorialNWBConverter(source_data=source_data)
    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_description"] = "NWB Conversion Tools tutorial."
    metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
    metadata["NWBFile"]["experimenter"] = ["My name"]
    metadata["Subject"] = dict(subject_id="Name of imaginary testing subject (required for DANDI upload)")
    conversion_options = dict(RecordingTutorial=dict(stub_test=stub_test), SortingTutorial=dict())
    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        overwrite=True,
        conversion_options=conversion_options,
    )


def test_tutorial_interfaces():
    class TutorialNWBConverter(NWBConverter):
        data_interface_classes = dict(
            RecordingTutorial=RecordingTutorialInterface, SortingTutorial=SortingTutorialInterface
        )

    test_dir = Path(mkdtemp())
    nwbfile_path = str(test_dir / "TestTutorial.nwb")
    source_data = dict(
        RecordingTutorial=dict(),
        SortingTutorial=dict(),
    )
    converter = TutorialNWBConverter(source_data=source_data)
    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
    converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)


def test_pkl_interface():
    toy_data = se.example_datasets.toy_example()
    test_dir = Path(mkdtemp())
    output_folder = test_dir / "test_pkl"
    nwbfile_path = str(test_dir / "test_pkl_files.nwb")

    se.save_si_object(object_name="test_recording", si_object=toy_data[0], output_folder=output_folder)
    se.save_si_object(object_name="test_sorting", si_object=toy_data[1], output_folder=output_folder)

    class SpikeInterfaceTestNWBConverter(NWBConverter):
        data_interface_classes = dict(
            Recording=SIPickleRecordingExtractorInterface, Sorting=SIPickleSortingExtractorInterface
        )

    source_data = dict(
        Recording=dict(file_path=str(test_dir / "test_pkl" / "test_recording.pkl")),
        Sorting=dict(file_path=str(test_dir / "test_pkl" / "test_sorting.pkl")),
    )
    converter = SpikeInterfaceTestNWBConverter(source_data=source_data)
    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
    converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

    nwb_recording = se.NwbRecordingExtractor(file_path=nwbfile_path)
    nwb_sorting = se.NwbSortingExtractor(file_path=nwbfile_path)
    check_recordings_equal(RX1=toy_data[0], RX2=nwb_recording)
    check_recordings_equal(RX1=toy_data[0], RX2=nwb_recording, return_scaled=False)
    check_sortings_equal(SX1=toy_data[1], SX2=nwb_sorting)


class TestSortingInterface(unittest.TestCase):
    def setUp(self) -> None:
        self.sorting_start_frames = [100, 200, 300]
        self.num_frames = 1000
        sorting = se.NumpySortingExtractor()
        sorting.set_sampling_frequency(3000)
        sorting.add_unit(unit_id=1, times=np.arange(self.sorting_start_frames[0], self.num_frames))
        sorting.add_unit(unit_id=2, times=np.arange(self.sorting_start_frames[1], self.num_frames))
        sorting.add_unit(unit_id=3, times=np.arange(self.sorting_start_frames[2], self.num_frames))

        class TestSortingInterface(BaseSortingExtractorInterface):
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
