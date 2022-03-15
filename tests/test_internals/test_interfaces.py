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
from nwb_conversion_tools import (
    NWBConverter,
    RecordingTutorialInterface,
    SortingTutorialInterface,
    SIPickleRecordingExtractorInterface,
    SIPickleSortingExtractorInterface,
    CEDRecordingInterface,
)
from nwb_conversion_tools.datainterfaces.ecephys.basesortingextractorinterface import BaseSortingExtractorInterface


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
    output_file = str(test_dir / "TestTutorial.nwb")
    source_data = dict(
        RecordingTutorial=dict(duration=duration, num_channels=num_channels, sampling_frequency=sampling_frequency),
        SortingTutorial=dict(duration=duration, num_units=num_units, sampling_frequency=sampling_frequency),
    )
    converter = TutorialNWBConverter(source_data=source_data)
    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_description"] = "NWB Conversion Tools tutorial."
    metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S")
    metadata["NWBFile"]["experimenter"] = ["My name"]
    metadata["Subject"] = dict(subject_id="Name of imaginary testing subject (required for DANDI upload)")
    conversion_options = dict(RecordingTutorial=dict(stub_test=stub_test), SortingTutorial=dict())
    converter.run_conversion(
        metadata=metadata,
        nwbfile_path=output_file,
        save_to_file=True,
        overwrite=True,
        conversion_options=conversion_options,
    )


def test_tutorial_interfaces():
    class TutorialNWBConverter(NWBConverter):
        data_interface_classes = dict(
            RecordingTutorial=RecordingTutorialInterface, SortingTutorial=SortingTutorialInterface
        )

    test_dir = Path(mkdtemp())
    output_file = str(test_dir / "TestTutorial.nwb")
    source_data = dict(
        RecordingTutorial=dict(),
        SortingTutorial=dict(),
    )
    converter = TutorialNWBConverter(source_data=source_data)
    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S")
    converter.run_conversion(nwbfile_path=output_file, overwrite=True, metadata=metadata)


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
    metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S")
    converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

    nwb_recording = se.NwbRecordingExtractor(file_path=nwbfile_path)
    nwb_sorting = se.NwbSortingExtractor(file_path=nwbfile_path)
    check_recordings_equal(RX1=toy_data[0], RX2=nwb_recording)
    check_recordings_equal(RX1=toy_data[0], RX2=nwb_recording, return_scaled=False)
    check_sortings_equal(SX1=toy_data[1], SX2=nwb_sorting)


def test_base_sorting_interface():
    test_dir = Path(mkdtemp())
    minimal_nwbfile = test_dir / "temp.nwb"

    def _make_sorting(seed):
        num_frames = 1000
        sampling_frequency = 30000
        sorting = se.NumpySortingExtractor()
        sorting.set_sampling_frequency(sampling_frequency)
        sorting.add_unit(unit_id=1, times=np.linspace(1, 100, num_frames))
        sorting.add_unit(unit_id=2, times=np.linspace(2, 100, num_frames))
        sorting.add_unit(unit_id=3, times=np.linspace(3, 100, num_frames))
        sorting.set_unit_property(unit_id=1, property_name="int_prop", value=80)
        sorting.set_unit_property(unit_id=1, property_name="float_prop", value=80.0)
        sorting.set_unit_property(unit_id=1, property_name="str_prop", value="test_val")
        return sorting

    class TestSortingInterface(BaseSortingExtractorInterface):
        def __init__(self, seed: int = 0):
            self.sorting_extractor = _make_sorting(seed)
            self.source_data = dict()

    class TempConverter(NWBConverter):
        data_interface_classes = dict(TestSortingInterface=TestSortingInterface)

    source_data = dict(TestSortingInterface=dict())
    conversion_options = dict(TestSortingInterface=dict(stub_test=True))
    test_interface = TempConverter(source_data)
    metadata = test_interface.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S")
    test_interface.run_conversion(
        nwbfile_path=minimal_nwbfile, metadata=metadata, conversion_options=conversion_options
    )
    with NWBHDF5IO(minimal_nwbfile, "r") as io:
        nwbfile = io.read()
        assert nwbfile.units["spike_times"][0][-1] < 1.1 * 3 * 1e-3
