import os
import tempfile
import unittest

import numpy as np
from numpy.testing import assert_array_equal
from pynwb.image import ImageSeries
from pynwb import NWBHDF5IO
from datetime import datetime
from hdmf.backends.hdf5.h5_utils import H5DataIO

from nwb_conversion_tools.datainterfaces.behavior.movie.movie_utils import VideoCaptureContext, MovieDataChunkIterator
from nwb_conversion_tools.tools.nwb_helpers import make_nwbfile_from_metadata

try:
    import cv2

    CV2_INSTALLED = True
except:
    CV2_INSTALLED = False


@unittest.skipIf(not CV2_INSTALLED, "cv2 not installed")
class TestVideoContext(unittest.TestCase):

    frame_shape = (100, 200, 3)
    number_of_frames = 30
    fps = 25

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.movie_frames = np.random.randint(0, 255, size=[self.number_of_frames, *self.frame_shape], dtype="uint8")
        self.movie_loc = self.create_movie()

    def create_movie(self):
        movie_file = os.path.join(self.test_dir, "test.avi")
        writer = cv2.VideoWriter(
            filename=movie_file,
            apiPreference=None,
            fourcc=cv2.VideoWriter_fourcc(*"HFYU"),
            fps=self.fps,
            frameSize=self.frame_shape[1::-1],
            params=None,
        )
        for k in range(self.number_of_frames):
            writer.write(self.movie_frames[k, :, :, :])
        writer.release()
        return movie_file

    def test_context(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            pass
        self.assertFalse(vcc.vc.isOpened())

    def test_timestamps(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            ts = vcc.get_movie_timestamps()
        self.assertEqual(len(ts), self.number_of_frames)

    def test_fps(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            fps = vcc.get_movie_fps()
        self.assertEqual(fps, self.fps)

    def test_frame_shape(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            frame_shape = vcc.get_frame_shape()
        assert_array_equal(frame_shape, self.frame_shape)

    def test_frame_value(self):
        frames = []
        with VideoCaptureContext(self.movie_loc) as vcc:
            number_of_frames = vcc.get_movie_frame_count()
            for no in range(number_of_frames):
                frames.append(vcc.get_movie_frame(no))
        assert_array_equal(frames, np.flip(self.movie_frames, 3))

    def test_iterable(self):
        frames = []
        vcc = VideoCaptureContext(file_path=self.movie_loc)
        for frame in vcc:
            frames.append(frame)
        assert_array_equal(np.array(frames), np.flip(self.movie_frames, 3))
        self.assertFalse(vcc.vc.isOpened())
        vcc.release()

    def test_stub_iterable(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            vcc.frame_count = 3
            frames = []
            for frame in vcc:
                frames.append(frame)
        assert_array_equal(np.array(frames), self.movie_frames[:3, :, :, [2, 1, 0]])

    def test_stub_frame(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            vcc.frame_count = 3
            with self.assertRaises(AssertionError):
                vcc.get_movie_frame(3)

    def test_stub_timestamps(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            vcc.frame_count = 3
            ts = vcc.get_movie_timestamps()
        self.assertEqual(len(ts), 3)

    def test_stub_framecount(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            vcc.frame_count = 4
        self.assertEqual(vcc.get_movie_frame_count(), 4)

    def test_isopened_assertions(self):
        vcc = VideoCaptureContext(file_path=self.movie_loc)
        vcc.release()
        self.assertRaises(AssertionError, vcc.get_movie_timestamps)
        self.assertRaises(AssertionError, vcc.get_movie_fps)
        self.assertRaises(AssertionError, vcc.get_movie_frame_count)
        self.assertRaises(AssertionError, vcc.get_movie_frame_dtype)
        self.assertRaises(AssertionError, vcc.__next__)


@unittest.skipIf(not CV2_INSTALLED, "cv2 not installed")
class TestMovieInterface(unittest.TestCase):

    frame_shape = (800, 600, 3)
    number_of_frames = 500
    fps = 25

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.nwbfile = make_nwbfile_from_metadata(dict(NWBFile=dict(session_start_time=datetime.now())))
        self.nwbfile_path = os.path.join(self.test_dir, "movie_test.nwb")

    def create_movie(self, fps, frame_shape, number_of_frames):
        movie_frames = np.random.randint(0, 255, size=[number_of_frames, *frame_shape], dtype="uint8")
        movie_file = os.path.join(self.test_dir, "test.avi")
        writer = cv2.VideoWriter(
            filename=movie_file,
            apiPreference=None,
            fourcc=cv2.VideoWriter_fourcc(*"HFYU"),
            fps=fps,
            frameSize=frame_shape[1::-1],
            params=None,
        )
        for k in range(number_of_frames):
            writer.write(movie_frames[k])
        writer.release()
        return movie_file

    def test_iterator_stub(self):
        movie_file = self.create_movie(self.fps, self.frame_shape, self.number_of_frames)
        it = H5DataIO(MovieDataChunkIterator(movie_file, stub_test=True), compression="gzip")
        img_srs = ImageSeries(name="imageseries", data=it, unit="na", starting_time=None, rate=1.0)
        self.nwbfile.add_acquisition(img_srs)
        with NWBHDF5IO(path=self.nwbfile_path, mode="w") as io:
            io.write(self.nwbfile)
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.acquisition["imageseries"].data.shape[0] == 10

    def test_frame_shape_big(self):
        frame_shape = (800, 600, 3)
        movie_file = self.create_movie(self.fps, frame_shape, self.number_of_frames)
        num_frames_chunk = int(1e6 // np.prod(frame_shape))
        num_frames_chunk = 1 if num_frames_chunk == 0 else num_frames_chunk
        it = H5DataIO(MovieDataChunkIterator(movie_file), compression="gzip")
        img_srs = ImageSeries(name="imageseries", data=it, unit="na", starting_time=None, rate=1.0)
        self.nwbfile.add_acquisition(img_srs)
        with NWBHDF5IO(path=self.nwbfile_path, mode="w") as io:
            io.write(self.nwbfile)
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            expected_chunk_shape = (num_frames_chunk,) + frame_shape
            assert all(
                [nwbfile.acquisition["imageseries"].data.chunks[i] == j for i, j in enumerate(expected_chunk_shape)]
            )

    def test_frame_shape_small(self):
        frame_shape = (400, 300, 3)
        movie_file = self.create_movie(self.fps, frame_shape, self.number_of_frames)
        num_frames_chunk = int(1e6 // np.prod(frame_shape))
        num_frames_chunk = 1 if num_frames_chunk == 0 else num_frames_chunk
        it = H5DataIO(MovieDataChunkIterator(movie_file), compression="gzip")
        img_srs = ImageSeries(name="imageseries", data=it, unit="na", starting_time=None, rate=1.0)
        self.nwbfile.add_acquisition(img_srs)
        with NWBHDF5IO(path=self.nwbfile_path, mode="w") as io:
            io.write(self.nwbfile)
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            expected_chunk_shape = (num_frames_chunk,) + frame_shape
            assert all(
                [nwbfile.acquisition["imageseries"].data.chunks[i] == j for i, j in enumerate(expected_chunk_shape)]
            )

    def test_custom_chunk_shape(self):
        custom_frame_shape = (1, 100, 100, 3)
        movie_file = self.create_movie(self.fps, self.frame_shape, self.number_of_frames)
        it = H5DataIO(MovieDataChunkIterator(movie_file, chunk_shape=custom_frame_shape), compression="gzip")
        img_srs = ImageSeries(name="imageseries", data=it, unit="na", starting_time=None, rate=1.0)
        self.nwbfile.add_acquisition(img_srs)
        with NWBHDF5IO(path=self.nwbfile_path, mode="w") as io:
            io.write(self.nwbfile)
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert all(
                [nwbfile.acquisition["imageseries"].data.chunks[i] == j for i, j in enumerate(custom_frame_shape)]
            )

    def test_small_buffer_size(self):
        frame_size_mb = np.prod(self.frame_shape) / 1e6
        buffer_size = frame_size_mb / 1e3 / 2
        movie_file = self.create_movie(self.fps, self.frame_shape, self.number_of_frames)
        with self.assertRaises(AssertionError):
            it = H5DataIO(MovieDataChunkIterator(movie_file, buffer_gb=buffer_size), compression="gzip")
