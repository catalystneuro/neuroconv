"""Authors: Saksham Sharda, Cody Baker."""
from pathlib import Path
from typing import Union, Tuple

import numpy as np
from tqdm import tqdm

try:
    import cv2

    HAVE_OPENCV = True
except ImportError:
    HAVE_OPENCV = False

PathType = Union[str, Path]


class VideoCaptureContext(cv2.VideoCapture):
    def __init__(self, *args, stub=False, **kwargs):
        self._args = args
        self._kwargs = kwargs
        super().__init__(*args, **kwargs)
        self.stub = stub
        self._current_frame = 0
        self.frame_count = self.get_movie_frame_count()
        self.fps = self.get_movie_fps()
        self.frame = self.get_movie_frame(0)
        assert self.frame is not None, "unable to read the movie file provided"

    def get_movie_timestamps(self):
        """
        Return numpy array of the timestamps for a movie file.

        """
        if not self.isOpened():
            raise ValueError("movie file is not open")
        ts = [self.get(cv2.CAP_PROP_POS_MSEC)]
        for i in tqdm(range(1, self.get_movie_frame_count()), desc="retrieving video timestamps"):
            self.current_frame = i
            ts.append(self.get(cv2.CAP_PROP_POS_MSEC))
        self.current_frame = 0
        return np.array(ts)

    def get_movie_fps(self):
        """
        Return the internal frames per second (fps) for a movie file.

        """
        if int(cv2.__version__.split(".")[0]) < 3:
            return self.get(cv2.cv.CV_CAP_PROP_FPS)
        return self.get(cv2.CAP_PROP_FPS)

    def get_frame_shape(self) -> Tuple:
        """
        Return the shape of frames from a movie file.
        """
        return self.frame.shape

    def get_movie_frame_count(self):
        """
        Return the total number of frames for a movie file.

        """
        if self.stub:
            # if stub the assume a max frame count of 10
            return 10
        if int(cv2.__version__.split(".")[0]) < 3:
            count = self.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT)
        else:
            count = self.get(cv2.CAP_PROP_FRAME_COUNT)
        return int(count)

    @property
    def current_frame(self):
        return self._current_frame

    @current_frame.setter
    def current_frame(self, frame_no):
        if int(cv2.__version__.split(".")[0]) < 3:
            set_arg = cv2.cv.CV_CAP_PROP_POS_FRAMES
        else:
            set_arg = cv2.CAP_PROP_POS_FRAMES
        set_value = self.set(set_arg, frame_no)
        if set_value:
            self._current_frame = frame_no
        else:
            raise ValueError(f"could not set frame no {frame_no}")

    def get_movie_frame(self, frame_no: int):
        """
        Return the specific frame from a movie.
        """
        if not self.isOpened():
            raise ValueError("movie file is not open")
        assert frame_no < self.get_movie_frame_count(), "frame number is greater than length of movie"
        self.current_frame = frame_no
        success, frame = self.read()
        self.current_frame = 0
        if success:
            return frame
        elif frame_no > 0:
            return np.nan*np.ones(self.get_frame_shape())

    def get_movie_frame_dtype(self):
        """
        Return the dtype for frame in a movie file.
        """
        return self.frame.dtype

    def __iter__(self):
        return self

    def __next__(self):
        if not self.isOpened():
            raise StopIteration
        try:
            if self.current_frame < self.frame_count:
                success, frame = self.read()
                self.current_frame += 1
                if success:
                    return frame
                else:
                    return np.nan*np.ones(self.get_frame_shape())
            else:
                self.current_frame = 0
                raise StopIteration
        except Exception:
            raise StopIteration

    def __enter__(self):
        if not self.isOpened():
            super().__init__(*self._args, **self._kwargs)
        return self

    def __exit__(self, *args):
        self.release()

    def __del__(self):
        self.release()
