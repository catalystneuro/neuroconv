import os
import tempfile
import unittest

import cv2
import numpy as np

from nwb_conversion_tools.datainterfaces.behavior.movie.movie_utils import \
    VideoCaptureContext


class TestVideoContext(unittest.TestCase):
    
    frame_shape = (640, 480, 3)
    no_frames = 20
    fps = 25
    
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.movie_frames = self.get_movie_frames()
        self.movie_loc = self.create_movie()

    def get_movie_frames(self):
        frames = []
        for no in range(self.no_frames):
            frames.append(np.random.randint(0, 255, self.frame_shape).astype("uint8"))
        return np.array(frames)

    def create_movie(self):
        movie_file = os.path.join(self.test_dir, "test.avi")
        writer = cv2.VideoWriter(
            filename=movie_file,
            apiPreference=None,
            fourcc=cv2.VideoWriter_fourcc("M", "J", "P", "G"),
            fps=self.fps,
            frameSize=self.frame_shape[:2],
            params=None,
        )
        for k in range(self.no_frames):
            writer.write(self.movie_frames[k,:,:,:])
        writer.release()
        return movie_file

    def test_context(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            pass
        self.assertFalse(vcc.vc.isOpen)

    def test_stub(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            frame_count = vcc.get_movie_frame_count()
        self.assertEqual(frame_count, 10)

    def test_timestamps(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            ts = vcc.get_movie_timestamps()
        self.assertEqual(len(ts), self.no_frames)
        with VideoCaptureContext(self.movie_loc, stub=True) as vcc:
            ts = vcc.get_movie_timestamps()
        self.assertEqual(len(ts), 10)
    
    def test_fps(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            fps = vcc.get_movie_fps()
        self.assertEqual(fps, self.fps)

    def test_frame_shape(self):
        with VideoCaptureContext(self.movie_loc) as vcc:
            frame_shape = vcc.get_frame_shape()
        self.assertEqual(frame_shape, self.frame_shape)

    def test_frame_value(self):
        frames = []
        with VideoCaptureContext(self.movie_loc) as vcc:
            for no in range(self.no_frames):
                frames.append(vcc.get_movie_frame(no))
        self.assertEqual(np.array(frames), self.movie_frames)

    def test_iterable(self):
        frames = []
        with VideoCaptureContext(self.movie_loc) as vcc:
            pass
        for frame in vcc:
            frames.append(frame)
        self.assertEqual(np.array(frames), self.movie_frames)
        self.assertFalse(vcc.vc.isOpen)
