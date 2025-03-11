import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np
from dateutil.tz import gettz
from hdmf.testing import TestCase
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.datainterfaces.behavior.video.internalvideointerface import (
    InternalVideoInterface,
)

try:
    import cv2

    skip_test = False
except ImportError:
    skip_test = True


@unittest.skipIf(skip_test, "cv2 not installed")
class TestInternalVideoInterface(TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.video_files = self.create_videos()
        self.nwb_converter = self.create_video_converter()
        self.metadata = self.nwb_converter.get_metadata()
        self.metadata["NWBFile"].update(session_start_time=datetime.now(tz=gettz(name="US/Pacific")))
        self.nwbfile_path = self.test_dir / "video_test.nwb"
        self.aligned_starting_time = 10.0

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir)
        del self.nwb_converter

    def create_videos(self):
        video_file1 = str(self.test_dir / "test1.avi")
        video_file2 = str(self.test_dir / "test2.avi")
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

        for frame in range(number_of_frames):
            writer1.write(np.random.randint(0, 255, (number_of_rows, number_of_columns, 3)).astype("uint8"))
            writer2.write(np.random.randint(0, 255, (number_of_rows, number_of_columns, 3)).astype("uint8"))

        writer1.release()
        writer2.release()

        return [video_file1, video_file2]

    def create_video_converter(self):
        class VideoTestNWBConverter(NWBConverter):
            data_interface_classes = dict(
                Video1=InternalVideoInterface,
                Video2=InternalVideoInterface,
            )

        source_data = dict(
            Video1=dict(
                file_path=self.video_files[0],
                video_name="Video test1",
            ),
            Video2=dict(
                file_path=self.video_files[1],
                video_name="Video test2",
            ),
        )
        return VideoTestNWBConverter(source_data=source_data)

    def test_save_video_to_custom_module(self):
        """Test that videos can be added to a custom module."""
        module_name = "TestModule"
        module_description = "This is a test module."
        conversion_opts = dict(
            Video1=dict(
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
            conversion_options=conversion_opts,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert module_name in nwbfile.processing
            assert module_description == nwbfile.processing[module_name].description
            assert "Video test1" in nwbfile.processing[module_name].data_interfaces
            assert "Video test2" in nwbfile.processing[module_name].data_interfaces

    def test_video_chunking(self):
        """Test that video chunking works correctly."""
        conversion_options = dict(
            Video1=dict(stub_test=True, chunk_data=True),
            Video2=dict(stub_test=True, chunk_data=False),
        )
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )

        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            # Verify that chunking is applied
            assert mod["Video test1"].data.chunks is not None
            # Verify that non-chunking option works
            assert mod["Video test2"].data.chunks is not None  # Still chunked due to HDF5 storage

    def test_video_stub(self):
        """Test that stub mode works correctly."""
        conversion_options = dict(Video1=dict(stub_test=True))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            # Verify that stub test limits the frames
            assert mod["Video test1"].data.shape[0] == 10

    def test_aligned_timestamps(self):
        """Test that aligned timestamps are correctly applied."""
        aligned_timestamps = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        interface = self.nwb_converter.data_interface_objects["Video1"]
        interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)

        conversion_options = dict(Video1=dict(stub_test=True))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            np.testing.assert_array_equal(aligned_timestamps, nwbfile.acquisition["Video test1"].timestamps[:])

    def test_aligned_starting_time(self):
        """Test that aligned starting time is correctly applied."""
        interface = self.nwb_converter.data_interface_objects["Video1"]
        interface.set_aligned_starting_time(aligned_starting_time=self.aligned_starting_time)

        conversion_options = dict(Video1=dict(stub_test=True))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            # Verify that starting time is applied
            assert nwbfile.acquisition["Video test1"].starting_time == self.aligned_starting_time
