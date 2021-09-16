"""Authors: Cody Baker."""
from pathlib import Path
import numpy as np
from typing import Union, Tuple, Iterable
from ....utils.genericdatachunkiterator import GenericDataChunkIterator

try:
    import cv2

    HAVE_OPENCV = True
except ImportError:
    HAVE_OPENCV = False

PathType = Union[str, Path]


def get_movie_timestamps(movie_file: PathType):
    """
    Return numpy array of the timestamps for a movie file.

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
    """
    Return the internal frames per second (fps) for a movie file.

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
    """
    Return the shape of frames from a movie file.

    Parameters
    ----------
    movie_file : PathType
    """
    cap = cv2.VideoCapture(str(movie_file))
    success, frame = cap.read()
    cap.release()
    return frame.shape

def get_movie_frame_count(movie_file: PathType):
    """
    Return the total number of frames for a movie file.

    Parameters
    ----------
    movie_file : PathType
    """
    cap = cv2.VideoCapture(str(movie_file))
    if int((cv2.__version__).split(".")[0]) < 3:
        count = cap.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT)
    else:
        count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return count

def get_movie_frame(movie_file: PathType, frame_no: int):
    """
    Return the specific frame from a movie.

    Parameters
    ----------
    movie_file : PathType
    """
    assert frame_no<=get_movie_frame_count(movie_file)
    cap = cv2.VideoCapture(str(movie_file))
    if int((cv2.__version__).split(".")[0]) < 3:
        success = cap.set(cv2.cv.CV_CAP_PROP_POS_FRAMES, frame_no)
    else:
        success = cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
    _, frame = cap.read()
    cap.release()
    return frame

def get_movie_frame_dtype(movie_file: PathType):
    """
    Return the dtype for frame in a movie file.

    Parameters
    ----------
    movie_file : PathType
    """
    cap = cv2.VideoCapture(str(movie_file))
    _, frame = cap.read()
    cap.release()
    return frame.dtype


class MovieDataChunkIterator(GenericDataChunkIterator):
    """DataChunkIterator specifically for use on RecordingExtractor objects."""

    def __init__(
        self,
        movie_file: PathType,
        buffer_gb: float = None,
        buffer_shape: tuple = None,
        chunk_mb: float = None,
        chunk_shape: tuple = None,
    ):
        self.movie_file = movie_file
        if chunk_shape is None:
            chunk_shape = (1, *get_frame_shape(self.movie_file))
        super().__init__(buffer_gb=buffer_gb, buffer_shape=buffer_shape, chunk_mb=chunk_mb, chunk_shape=chunk_shape)

    def _get_data(self, selection: Tuple[slice]) -> Iterable:
        frames_return = []
        for frame_no in range(selection[0].start, selection[0].stop, selection[0].step):
            frames_return.append(get_movie_frame(self.movie_file, frame_no))
        return np.concatenate(frames_return,axis=0)

    def _get_dtype(self):
        return get_movie_frame_dtype(self.movie_file)

    def _get_maxshape(self):
        return (get_movie_frame_count(self.movie_file), *get_frame_shape(self.movie_file))