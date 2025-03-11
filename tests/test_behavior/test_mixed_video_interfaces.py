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
from neuroconv.datainterfaces.behavior.video.internalvideointerface import (
    InternalVideoInterface,
)
from neuroconv.utils import dict_deep_update

try:
    import cv2

    skip_test = False
except ImportError:
    skip_test = True


@unittest.skipIf(skip_test, "cv2 not installed")
class TestMixedVideoInterfaces(TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.video_files = self.create_videos()
        self.nwb_converter = self.create_video_converter()
        self.metadata = self.nwb_converter.get_metadata()
        self.metadata["NWBFile"].update(session_start_time=datetime.now(tz=gettz(name="US/Pacific")))
        self.nwbfile_path = self.test_dir / "mixed_video_test.nwb"
        self.aligned_starting_time = 10.0
        self.aligned_segment_starting_times = [5.0, 15.0]

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir)
        del self.nwb_converter

    def create_videos(self):
        """Create test video files."""
        # Create 3 video files - 1 for internal and 2 for external
        video_file1 = str(self.test_dir / "internal_test.avi")
        video_file2 = str(self.test_dir / "external_test1.avi")
        video_file3 = str(self.test_dir / "external_test2.avi")

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
        """Create a converter with both internal and external video interfaces."""

        class MixedVideoTestNWBConverter(NWBConverter):
            data_interface_classes = dict(
                InternalVideo=InternalVideoInterface,
                ExternalVideo=ExternalVideoInterface,
            )

        source_data = dict(
            InternalVideo=dict(
                file_path=self.video_files[0],
                video_name="Internal Video",
            ),
            ExternalVideo=dict(
                file_paths=self.video_files[1:3],
                video_name="External Video",
            ),
        )
        return MixedVideoTestNWBConverter(source_data=source_data)

    def test_mixed_video_interfaces_basic(self):
        """Test that both internal and external video interfaces can be used together."""
        # Set up the external interface with timestamps
        external_interface = self.nwb_converter.data_interface_objects["ExternalVideo"]
        external_timestamps = [np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])]
        external_interface.set_aligned_timestamps(aligned_timestamps=external_timestamps)
        external_interface.set_aligned_segment_starting_times(
            aligned_segment_starting_times=self.aligned_segment_starting_times
        )

        # Set up the internal interface with a starting time
        internal_interface = self.nwb_converter.data_interface_objects["InternalVideo"]
        internal_interface.set_aligned_starting_time(aligned_starting_time=self.aligned_starting_time)

        # Run conversion with appropriate options
        conversion_options = dict(InternalVideo=dict(stub_test=True), ExternalVideo=dict(starting_frames=[0, 4]))

        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )

        # Verify the results
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()

            # Check that both videos exist in the file
            assert "Internal Video" in nwbfile.acquisition
            assert "External Video" in nwbfile.acquisition

            # Verify internal video properties
            assert nwbfile.acquisition["Internal Video"].starting_time == self.aligned_starting_time

            # Verify external video properties
            expected_timestamps = np.array([6.0, 7.0, 8.0, 19.0, 20.0, 21.0])
            np.testing.assert_array_equal(expected_timestamps, nwbfile.acquisition["External Video"].timestamps[:])
            self.assertListEqual(
                list1=list(nwbfile.acquisition["External Video"].external_file[:]), list2=self.video_files[1:3]
            )

    def test_mixed_video_interfaces_custom_module(self):
        """Test that both video types can be added to a custom module."""
        # Set up the external interface with timestamps
        external_interface = self.nwb_converter.data_interface_objects["ExternalVideo"]
        external_timestamps = [np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])]
        external_interface.set_aligned_timestamps(aligned_timestamps=external_timestamps)
        external_interface.set_aligned_segment_starting_times(
            aligned_segment_starting_times=self.aligned_segment_starting_times
        )

        # Set up the internal interface with a starting time
        internal_interface = self.nwb_converter.data_interface_objects["InternalVideo"]
        internal_interface.set_aligned_starting_time(aligned_starting_time=self.aligned_starting_time)

        # Define a custom module
        module_name = "MixedVideoModule"
        module_description = "Module containing both internal and external videos"

        # Run conversion with custom module
        conversion_options = dict(
            InternalVideo=dict(
                stub_test=True,
                module_name=module_name,
                module_description=module_description,
            ),
            ExternalVideo=dict(
                starting_frames=[0, 4],
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

        # Verify the results
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()

            # Check that the module exists
            assert module_name in nwbfile.processing
            assert module_description == nwbfile.processing[module_name].description

            # Check that both videos are in the module
            assert "Internal Video" in nwbfile.processing[module_name].data_interfaces
            assert "External Video" in nwbfile.processing[module_name].data_interfaces

    def test_mixed_video_interfaces_custom_metadata(self):
        """Test adding both video types with custom metadata."""
        # Set up the external interface with timestamps
        external_interface = self.nwb_converter.data_interface_objects["ExternalVideo"]
        external_timestamps = [np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])]
        external_interface.set_aligned_timestamps(aligned_timestamps=external_timestamps)
        external_interface.set_aligned_segment_starting_times(
            aligned_segment_starting_times=self.aligned_segment_starting_times
        )

        # Set up the internal interface with a starting time
        internal_interface = self.nwb_converter.data_interface_objects["InternalVideo"]
        internal_interface.set_aligned_starting_time(aligned_starting_time=self.aligned_starting_time)

        # Create custom metadata for both videos
        metadata = deepcopy(self.metadata)
        custom_metadata = {
            "Behavior": {
                "Video": [
                    {
                        "name": "Internal Video",
                        "description": "Internal video with custom description",
                        "unit": "InternalUnit",
                    },
                    {
                        "name": "External Video",
                        "description": "External video with custom description",
                        "unit": "ExternalUnit",
                    },
                ]
            }
        }
        metadata = dict_deep_update(metadata, custom_metadata)

        # Run conversion with custom metadata
        conversion_options = dict(InternalVideo=dict(stub_test=True), ExternalVideo=dict(starting_frames=[0, 4]))

        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=metadata,
        )

        # Verify the results
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()

            # Check internal video metadata
            assert nwbfile.acquisition["Internal Video"].description == "Internal video with custom description"
            assert nwbfile.acquisition["Internal Video"].unit == "InternalUnit"

            # Check external video metadata
            assert nwbfile.acquisition["External Video"].description == "External video with custom description"
            assert nwbfile.acquisition["External Video"].unit == "ExternalUnit"

    def test_mixed_video_interfaces_different_timing_types(self):
        """Test mixing videos with different timing types."""
        # Set up the external interface with segment starting times
        external_interface = self.nwb_converter.data_interface_objects["ExternalVideo"]
        external_interface.set_aligned_segment_starting_times(
            aligned_segment_starting_times=self.aligned_segment_starting_times
        )

        # Set up the internal interface with timestamps
        internal_interface = self.nwb_converter.data_interface_objects["InternalVideo"]
        internal_timestamps = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        internal_interface.set_aligned_timestamps(aligned_timestamps=internal_timestamps)

        # Run conversion
        conversion_options = dict(InternalVideo=dict(stub_test=True), ExternalVideo=dict(starting_frames=[0, 4]))

        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )

        # Verify the results
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()

            # Check internal video uses timestamps
            np.testing.assert_array_equal(internal_timestamps, nwbfile.acquisition["Internal Video"].timestamps[:])

            # Check external video uses starting_time and rate
            assert nwbfile.acquisition["External Video"].starting_time == self.aligned_segment_starting_times[0]
            assert nwbfile.acquisition["External Video"].rate is not None
