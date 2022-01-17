from pathlib import Path
from platform import python_version
from sys import platform
from tempfile import mkdtemp

import pytest
import spikeextractors as se
from hdmf.testing import TestCase
from packaging import version
from spikeextractors.testing import check_recordings_equal, check_sortings_equal

from nwb_conversion_tools import (
    NWBConverter,
    RecordingTutorialInterface,
    SortingTutorialInterface,
    SIPickleRecordingExtractorInterface,
    SIPickleSortingExtractorInterface,
    CEDRecordingInterface,
)

try:
    import cv2

    HAVE_OPENCV = True
except ImportError:
    HAVE_OPENCV = False


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
    converter.run_conversion(nwbfile_path=output_file, overwrite=True)


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
    converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    nwb_recording = se.NwbRecordingExtractor(file_path=nwbfile_path)
    nwb_sorting = se.NwbSortingExtractor(file_path=nwbfile_path)
    check_recordings_equal(RX1=toy_data[0], RX2=nwb_recording)
    check_recordings_equal(RX1=toy_data[0], RX2=nwb_recording, return_scaled=False)
    check_sortings_equal(SX1=toy_data[1], SX2=nwb_sorting)
