"""Authors: Saksham Sharda, Cody Baker."""
from pathlib import Path
from typing import Union, Tuple

import numpy as np
from tqdm import tqdm

from ....utils.json_schema import FilePathType

try:
    import cv2

    HAVE_OPENCV = True
except ImportError:
    HAVE_OPENCV = False

PathType = Union[str, Path]


class VideoCaptureContext:
    """Retrieving video metadata and frames using a context manager"""

    def __init__(self, file_path: FilePathType):
        self.vc = cv2.VideoCapture(filename=file_path)
        self.file_path = file_path
        self._current_frame = 0
        self._frame_count = None
        self._movie_open_msg = "The Movie file is not open!"

    def get_movie_timestamps(self):
        """Return numpy array of the timestamps(s) for a movie file."""
        ts2 = []
        for no in tqdm(range(self.get_movie_frame_count()), desc="retrieving timestamps"):
            success, frame = self.vc.read()
            ts2.append(self.vc.get(cv2.CAP_PROP_POS_MSEC)/1000)
            if not success:
                break
        return np.array(ts2)

    def get_movie_fps(self):
        """Return the internal frames per second (fps) for a movie file"""
        assert self.isOpened(), self._movie_open_msg
        prop = self.get_cv_attribute("CAP_PROP_FPS")
        return self.vc.get(prop)

    def get_frame_shape(self) -> Tuple:
        """Return the shape of frames from a movie file."""
        frame = self.get_movie_frame(0)
        if frame is not None:
            return frame.shape

    @property
    def frame_count(self):
        if self._frame_count is None:
            self._frame_count = self._movie_frame_count()
        return self._frame_count

    @frame_count.setter
    def frame_count(self, val):
        self._frame_count = val

    def get_movie_frame_count(self):
        return self.frame_count

    @staticmethod
    def get_cv_attribute(attribute_name):
        if int(cv2.__version__.split(".")[0]) < 3:  # pragma: no cover
            return getattr(cv2.cv, "CV_" + attribute_name)
        return getattr(cv2, attribute_name)

    def _movie_frame_count(self):
        """Return the total number of frames for a movie file."""
        assert self.isOpened(), self._movie_open_msg
        prop = self.get_cv_attribute("CAP_PROP_FRAME_COUNT")
        return int(self.vc.get(prop))

    @property
    def current_frame(self):
        return self._current_frame

    @current_frame.setter
    def current_frame(self, frame_number):
        assert self.isOpened(), self._movie_open_msg
        set_arg = self.get_cv_attribute("CAP_PROP_POS_FRAMES")
        set_value = self.vc.set(set_arg, frame_number)
        if set_value:
            self._current_frame = frame_number
        else:
            raise ValueError(f"could not set frame no {frame_number}")

    def get_movie_frame(self, frame_number: int):
        """Return the specific frame from a movie."""
        assert self.isOpened(), self._movie_open_msg
        assert frame_number < self.get_movie_frame_count(), "frame number is greater than length of movie"
        self.current_frame = frame_number
        success, frame = self.vc.read()
        self.current_frame = 0
        return frame

    def get_movie_frame_dtype(self):
        """Return the dtype for frame in a movie file."""
        frame = self.get_movie_frame(0)
        if frame is not None:
            return frame.dtype

    def release(self):
        self.vc.release()

    def isOpened(self):
        return self.vc.isOpened()

    def __iter__(self):
        return self

    def __next__(self):
        assert self.isOpened(), self._movie_open_msg
        if self._current_frame < self.frame_count:
            self.current_frame = self._current_frame
            success, frame = self.vc.read()
            self._current_frame += 1
            if success:
                return frame
            else:
                raise StopIteration
        else:
            self.vc.release()
            raise StopIteration

    def __enter__(self):
        self.vc = cv2.VideoCapture(self.file_path)
        return self

    def __exit__(self, *args):
        self.vc.release()

    def __del__(self):
        self.vc.release()


def get_movie_timestamps(movie_file: PathType):
    """Return numpy array of the timestamps for a movie file.

    Parameters
    ----------
    movie_file : PathType
    """
    cap = cv2.VideoCapture(str(movie_file))
    timestamps = [cap.get(cv2.CAP_PROP_POS_MSEC)]
    success, frame = cap.read()
    while success:
        timestamps.append(cap.get(cv2.CAP_PROP_POS_MSEC))
        success, frame = cap.read()
    cap.release()
    return np.array(timestamps)


def get_movie_fps(movie_file: PathType):
    """Return the internal frames per second (fps) for a movie file.

    Parameters
    ----------
    movie_file : PathType
    """
    cap = cv2.VideoCapture(str(movie_file))
    if int((cv2.__version__).split(".")[0]) < 3:
        fps = cap.get(cv2.cv.CV_CAP_PROP_FPS)
    else:
        fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps


def get_frame_shape(movie_file: PathType):
    """Return the shape of frames from a movie file.

    Parameters
    ----------
    movie_file : PathType
    """
    cap = cv2.VideoCapture(str(movie_file))
    success, frame = cap.read()
    cap.release()
    return frame.shape
