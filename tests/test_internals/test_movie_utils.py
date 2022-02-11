import os
import tempfile
import unittest
import numpy as np
from numpy.testing import assert_array_equal
from nwb_conversion_tools.datainterfaces.behavior.movie.movie_utils import VideoCaptureContext

try:
    import cv2

    CV2_INSTALLED = True
except:
    CV2_INSTALLED = False


@unittest.skipIf(not CV2_INSTALLED, "cv2 not installed")
class TestVideoContext(unittest.TestCase):

    frame_shape = (100, 200, 3)
    no_frames = 30
    fps = 25

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.movie_frames = np.random.randint(0, 255, size=[self.no_frames, *self.frame_shape], dtype="uint8")
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
        for k in range(self.no_frames):
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
        self.assertEqual(len(ts), self.no_frames)

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
            no_frames = vcc.get_movie_frame_count()
            for no in range(no_frames):
                frames.append(vcc.get_movie_frame(no))
        assert_array_equal(frames, self.movie_frames)

    def test_iterable(self):
        frames = []
        vcc = VideoCaptureContext(file_path=self.movie_loc)
        for frame in vcc:
            frames.append(frame)
        assert_array_equal(np.array(frames), self.movie_frames)
        self.assertFalse(vcc.vc.isOpened())
        vcc.release()

    def test_stub_iterable(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            vcc.frame_count = 3
            frames = []
            for frame in vcc:
                frames.append(frame)
        assert_array_equal(np.array(frames), self.movie_frames[:3, :, :])

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
