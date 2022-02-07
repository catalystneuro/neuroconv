"""Authors: Saksham Sharda, Cody Baker."""
from pathlib import Path
from typing import Union, Tuple
from ....utils.json_schema import FilePathType
import numpy as np

try:
    import cv2

    HAVE_OPENCV = True
except ImportError:
    HAVE_OPENCV = False

PathType = Union[str, Path]


class VideoCaptureContext:
    """Retrieving video metadata and frames using a context manager"""

    def __init__(self, file_path: FilePathType, stub=False):
        self.vc = cv2.VideoCapture(file_path)
        self.file_path = file_path
        self.stub = stub
        self._current_frame = 0
        self.frame_count = self.get_movie_frame_count()
        assert self.frame_count > 0, "movie contains no frames"
        self.fps = self.get_movie_fps()
        self.frame = self.get_movie_frame(0)
        assert self.frame is not None, "unable to read the movie file provided"
        self._movie_open_msg = "The Movie file is not open!"

    def get_movie_timestamps(self):
        """Return numpy array of the timestamps for a movie file."""
        return np.arange(self.get_movie_frame_count()) / self.get_movie_fps()

    def get_movie_fps(self):
        """Return the internal frames per second (fps) for a movie file"""
        assert self.vc.isOpened(), self._movie_open_msg
        if int(cv2.__version__.split(".")[0]) < 3:
            return self.vc.get(cv2.cv.CV_CAP_PROP_FPS)
        return self.vc.get(cv2.CAP_PROP_FPS)

    def get_frame_shape(self) -> Tuple:
        """Return the shape of frames from a movie file."""
        return self.frame.shape

    def get_movie_frame_count(self):
        """Return the total number of frames for a movie file."""
        assert self.vc.isOpened(), self._movie_open_msg
        if self.stub:
            # if stub the assume a max frame count of 10
            return 10
        if int(cv2.__version__.split(".")[0]) < 3:
            count = self.vc.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT)
        else:
            count = self.vc.get(cv2.CAP_PROP_FRAME_COUNT)
        return int(count)

    @property
    def current_frame(self):
        return self._current_frame

    @current_frame.setter
    def current_frame(self, frame_no):
        assert self.vc.isOpened(), self._movie_open_msg
        if int(cv2.__version__.split(".")[0]) < 3:
            set_arg = cv2.cv.CV_CAP_PROP_POS_FRAMES
        else:
            set_arg = cv2.CAP_PROP_POS_FRAMES
        set_value = self.vc.set(set_arg, frame_no)
        if set_value:
            self._current_frame = frame_no
        else:
            raise ValueError(f"could not set frame no {frame_no}")

    def get_movie_frame(self, frame_no: int):
        """Return the specific frame from a movie."""
        assert self.vc.isOpened(), self._movie_open_msg
        assert frame_no < self.get_movie_frame_count(), "frame number is greater than length of movie"
        self.current_frame = frame_no
        success, frame = self.vc.read()
        self.current_frame = 0
        if success:
            return frame
        elif frame_no > 0:
            return np.nan * np.ones(self.get_frame_shape())

    def get_movie_frame_dtype(self):
        """Return the dtype for frame in a movie file."""
        return self.frame.dtype

    def __iter__(self):
        return self

    def __next__(self):
        if not self.vc.isOpened():
            self.vc = cv2.VideoCapture(self.file_path)
        success, frame = self.vc.read()
        if success:
            self.current_frame = self._current_frame
            self._current_frame += 1
            self.vc.release()
            return frame
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
