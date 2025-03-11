import shutil
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import numpy as np
from dateutil.tz import gettz
from hdmf.testing import TestCase
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.datainterfaces.behavior.video.externalvideointerface import (
    ExternalVideoInterface,
)
from neuroconv.utils import dict_deep_update

try:
    import cv2

    skip_test = False
except ImportError:
    skip_test = True


@unittest.skipIf(skip_test, "cv2 not installed")
class TestExternalVideoInterface(TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.video_files = self.create_videos()
        self.nwb_converter = self.create_video_converter()
        self.metadata = self.nwb_converter.get_metadata()
        self.metadata["NWBFile"].update(session_start_time=datetime.now(tz=gettz(name="US/Pacific")))
        self.nwbfile_path = self.test_dir / "video_test.nwb"
        self.aligned_segment_starting_times = [0.0, 50.0]

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir)
        del self.nwb_converter

    def create_videos(self):
        video_file1 = str(self.test_dir / "test1.avi")
        video_file2 = str(self.test_dir / "test2.avi")
        video_file3 = str(self.test_dir / "test3.avi")
        number_of_frames = 30
        number_of_rows = 64
        number_of_columns = 48
        frameSize = (number_of_columns, number_of_rows)  # This is give in x,y images coordinates (x is columns)
        fps = 25
        # Standard code for specifying image formats
        fourcc_specification = ("M", "J", "P", "G")
        # Utility to transform the four code specification to OpenCV specification
        fourcc = cv2.VideoWriter_fourcc(*fourcc_specification)

        writer1 = cv2.VideoWriter(
            filename=video_file1,
            fourcc=fourcc,
            fps=fps,
            frameSize=frameSize,
        )
        writer2 = cv2.VideoWriter(
            filename=video_file2,
            fourcc=fourcc,
            fps=fps,
            frameSize=frameSize,
        )
        writer3 = cv2.VideoWriter(
            filename=video_file3,
            fourcc=fourcc,
            fps=fps,
            frameSize=frameSize,
        )

        for frame in range(number_of_frames):
            writer1.write(np.random.randint(0, 255, (number_of_rows, number_of_columns, 3)).astype("uint8"))
            writer2.write(np.random.randint(0, 255, (number_of_rows, number_of_columns, 3)).astype("uint8"))
            writer3.write(np.random.randint(0, 255, (number_of_rows, number_of_columns, 3)).astype("uint8"))

        writer1.release()
        writer2.release()
        writer3.release()

        return [video_file1, video_file2, video_file3]

    def create_video_converter(self):
        class VideoTestNWBConverter(NWBConverter):
            data_interface_classes = dict(
                Video1=ExternalVideoInterface,
                Video2=ExternalVideoInterface,
            )

        source_data = dict(
            Video1=dict(
                file_paths=self.video_files[0:2],
                video_name="Video test1",
            ),
            Video2=dict(
                file_paths=[self.video_files[2]],
                video_name="Video test3",
            ),
        )
        return VideoTestNWBConverter(source_data=source_data)

    def test_multiple_file_paths_error(self):
        """Test that an error is raised when multiple file paths are provided without timing information."""
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg=(
                "No timing information is specified and there are 2 total video files! "
                "Please specify the temporal alignment of each video."
            ),
        ):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                overwrite=True,
                metadata=self.metadata,
            )

    def test_external_mode_with_timestamps(self):
        """Test that external mode works correctly with timestamps."""
        timestamps = [np.array([2.2, 2.4, 2.6]), np.array([3.2, 3.4, 3.6])]
        interface = self.nwb_converter.data_interface_objects["Video1"]
        interface.set_aligned_timestamps(aligned_timestamps=timestamps)
        interface.set_aligned_segment_starting_times(aligned_segment_starting_times=self.aligned_segment_starting_times)

        conversion_options = dict(Video1=dict(starting_frames=[0, 4]))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            module = nwbfile.acquisition
            self.assertListEqual(list1=list(module["Video test1"].external_file[:]), list2=self.video_files[0:2])
            self.assertListEqual(list1=list(module["Video test3"].external_file[:]), list2=[self.video_files[2]])

    def test_irregular_timestamps(self):
        """Test that irregular timestamps are handled correctly."""
        aligned_timestamps = [np.array([1.0, 2.0, 4.0]), np.array([5.0, 6.0, 7.0])]
        interface = self.nwb_converter.data_interface_objects["Video1"]
        interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)
        interface.set_aligned_segment_starting_times(aligned_segment_starting_times=self.aligned_segment_starting_times)

        conversion_options = dict(Video1=dict(starting_frames=[0, 4]))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )

        expected_timestamps = np.array([1.0, 2.0, 4.0, 55.0, 56.0, 57.0])
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            np.testing.assert_array_equal(expected_timestamps, nwbfile.acquisition["Video test1"].timestamps[:])

    def test_starting_frames_type_error(self):
        """Test that an error is raised when starting_frames is not provided for multiple file paths."""
        timestamps = [np.array([2.2, 2.4, 2.6]), np.array([3.2, 3.4, 3.6])]
        interface = self.nwb_converter.data_interface_objects["Video1"]
        interface.set_aligned_timestamps(aligned_timestamps=timestamps)

        with self.assertRaisesWith(
            exc_type=TypeError,
            exc_msg="Multiple paths were specified for the ImageSeries, but no starting_frames were specified!",
        ):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                overwrite=True,
                metadata=self.metadata,
            )

    def test_starting_frames_value_error(self):
        """Test that an error is raised when the length of starting_frames doesn't match the number of file paths."""
        timestamps = [np.array([2.2, 2.4, 2.6]), np.array([3.2, 3.4, 3.6])]
        interface = self.nwb_converter.data_interface_objects["Video1"]
        interface.set_aligned_timestamps(aligned_timestamps=timestamps)

        conversion_options = dict(Video1=dict(starting_frames=[0]))
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg="Multiple paths (2) were specified for the ImageSeries, but the length of starting_frames (1) did not match the number of paths!",
        ):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                overwrite=True,
                conversion_options=conversion_options,
                metadata=self.metadata,
            )

    def test_custom_module(self):
        """Test that videos can be added to a custom module."""
        timestamps = [np.array([2.2, 2.4, 2.6]), np.array([3.2, 3.4, 3.6])]
        interface = self.nwb_converter.data_interface_objects["Video1"]
        interface.set_aligned_timestamps(aligned_timestamps=timestamps)
        interface.set_aligned_segment_starting_times(aligned_segment_starting_times=self.aligned_segment_starting_times)

        module_name = "TestModule"
        module_description = "This is a test module."
        conversion_options = dict(
            Video1=dict(
                starting_frames=[0, 4],
                module_name=module_name,
                module_description=module_description,
            ),
            Video2=dict(
                module_name=module_name,
                module_description=module_description,
            ),
        )
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert module_name in nwbfile.processing
            assert module_description == nwbfile.processing[module_name].description
            assert "Video test1" in nwbfile.processing[module_name].data_interfaces
            assert "Video test3" in nwbfile.processing[module_name].data_interfaces

    def test_get_timing_type_with_timestamps(self):
        """Test that get_timing_type returns 'timestamps' when timestamps are set."""
        interface = self.nwb_converter.data_interface_objects["Video1"]
        interface.set_aligned_timestamps(aligned_timestamps=[np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])])
        assert interface.get_timing_type() == "timestamps"

    def test_get_timing_type_with_segment_starting_times(self):
        """Test that get_timing_type returns 'starting_time and rate' when segment_starting_times are set."""
        interface = self.nwb_converter.data_interface_objects["Video1"]
        interface.set_aligned_segment_starting_times(aligned_segment_starting_times=[10.0, 20.0])
        assert interface.get_timing_type() == "starting_time and rate"

    def test_get_timing_type_single_file_default(self):
        """Test that get_timing_type returns 'starting_time and rate' by default for a single file."""
        # Create a new interface with a single file
        interface = ExternalVideoInterface(file_paths=[self.video_files[0]], video_name="SingleVideo")
        assert interface.get_timing_type() == "starting_time and rate"

    def test_set_aligned_timestamps_after_segment_starting_times_error(self):
        """Test that setting timestamps after segment_starting_times raises an error."""
        interface = self.nwb_converter.data_interface_objects["Video1"]

        # First set segment_starting_times
        interface.set_aligned_segment_starting_times(aligned_segment_starting_times=[10.0, 20.0])

        # Now try to set timestamps - should raise an assertion error
        with self.assertRaises(AssertionError):
            interface.set_aligned_timestamps(aligned_timestamps=[np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])])

    def test_set_aligned_starting_time_no_timing_info_error(self):
        """Test that set_aligned_starting_time raises an error when no timing info exists."""
        interface = self.nwb_converter.data_interface_objects["Video1"]

        # Mock _timestamps and _segment_starting_times to be None
        interface._timestamps = None
        interface._segment_starting_times = None

        with self.assertRaises(ValueError):
            interface.set_aligned_starting_time(aligned_starting_time=10.0)

    def test_get_original_timestamps_stub(self):
        """Test that get_original_timestamps respects stub_test parameter."""
        interface = self.nwb_converter.data_interface_objects["Video2"]  # Using Video2 which has a single file

        # Get stub timestamps
        stub_timestamps = interface.get_original_timestamps(stub_test=True)

        # Stub should have exactly 10 timestamps in the first array
        assert len(stub_timestamps[0]) == 10

        # Get full timestamps
        full_timestamps = interface.get_original_timestamps(stub_test=False)

        # Full should have more timestamps
        assert len(full_timestamps[0]) > len(stub_timestamps[0])

    def test_add_to_nwbfile_with_custom_metadata(self):
        """Test adding to NWBFile with custom metadata."""
        metadata = deepcopy(self.metadata)
        custom_metadata = {
            "Behavior": {"Video": [{"name": "Video test1", "description": "Custom description", "unit": "CustomUnit"}]}
        }
        metadata = dict_deep_update(metadata, custom_metadata)

        # Set up the interface for conversion
        interface = self.nwb_converter.data_interface_objects["Video1"]
        interface.set_aligned_timestamps(aligned_timestamps=[np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])])

        conversion_options = dict(Video1=dict(starting_frames=[0, 4]))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=metadata,
        )

        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.acquisition["Video test1"].description == "Custom description"
            assert nwbfile.acquisition["Video test1"].unit == "CustomUnit"
