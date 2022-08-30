"""Authors: Saksham Sharda, Cody Baker."""
from typing import Tuple, Iterable

import numpy as np
from tqdm import tqdm
from hdmf.data_utils import GenericDataChunkIterator

from ....tools import get_package
from ....utils import FilePathType


class VideoCaptureContext:
    """Retrieving video metadata and frames using a context manager."""

    def __init__(self, file_path: FilePathType):
        cv2 = get_package(package_name="cv2", installation_instructions="pip install opencv-python")

        self.vc = cv2.VideoCapture(filename=file_path)
        self.file_path = file_path
        self._current_frame = 0
        self._frame_count = None
        self._movie_open_msg = "The Movie file is not open!"

    def get_movie_timestamps(self):
        """Return numpy array of the timestamps(s) for a movie file."""
        cv2 = get_package(package_name="cv2", installation_instructions="pip install opencv-python")

        timestamps = []
        for _ in tqdm(range(self.get_movie_frame_count()), desc="retrieving timestamps"):
            success, _ = self.vc.read()
            if not success:
                break
            timestamps.append(self.vc.get(cv2.CAP_PROP_POS_MSEC))
        return np.array(timestamps) / 1000

    def get_movie_fps(self):
        """Return the internal frames per second (fps) for a movie file."""
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
    def frame_count(self, val: int):
        assert val > 0, "You must set a positive frame_count (received {val})."
        assert (
            val <= self._movie_frame_count()
        ), "Cannot set manual frame_count beyond length of video (received {val})."
        self._frame_count = val

    def get_movie_frame_count(self):
        return self.frame_count

    def _movie_frame_count(self):
        """Return the total number of frames for a movie file."""
        assert self.isOpened(), self._movie_open_msg
        prop = self.get_cv_attribute("CAP_PROP_FRAME_COUNT")
        return int(self.vc.get(prop))

    @staticmethod
    def get_cv_attribute(attribute_name: str):
        cv2 = get_package(package_name="cv2", installation_instructions="pip install opencv-python")

        if int(cv2.__version__.split(".")[0]) < 3:  # pragma: no cover
            return getattr(cv2.cv, "CV_" + attribute_name)
        return getattr(cv2, attribute_name)

    @property
    def current_frame(self):
        return self._current_frame

    @current_frame.setter
    def current_frame(self, frame_number: int):
        assert self.isOpened(), self._movie_open_msg
        set_arg = self.get_cv_attribute("CAP_PROP_POS_FRAMES")
        set_value = self.vc.set(set_arg, frame_number)
        if set_value:
            self._current_frame = frame_number
        else:
            raise ValueError(f"Could not set frame number (received {frame_number}).")

    def get_movie_frame(self, frame_number: int):
        """Return the specific frame from a movie as an RGB colorspace."""
        assert self.isOpened(), self._movie_open_msg
        assert frame_number < self.get_movie_frame_count(), "frame number is greater than length of movie"
        initial_frame_number = self.current_frame
        self.current_frame = frame_number
        success, frame = self.vc.read()
        self.current_frame = initial_frame_number
        return np.flip(frame, 2)  # np.flip to re-order color channels to RGB

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
            success, frame = self.vc.read()
            self._current_frame += 1
            if success:
                return np.flip(frame, 2)  # np.flip to re-order color channels to RGB
            else:
                raise StopIteration
        else:
            self.vc.release()
            raise StopIteration

    def __enter__(self):
        cv2 = get_package(package_name="cv2", installation_instructions="pip install opencv-python")

        self.vc = cv2.VideoCapture(self.file_path)
        return self

    def __exit__(self, *args):
        self.vc.release()

    def __del__(self):
        self.vc.release()


class MovieDataChunkIterator(GenericDataChunkIterator):
    """DataChunkIterator specifically for use on RecordingExtractor objects."""

    def __init__(
        self,
        movie_file: FilePathType,
        buffer_gb: float = None,
        chunk_shape: tuple = None,
        stub_test: bool = False,
    ):
        self.video_capture_ob = VideoCaptureContext(movie_file)
        self._full_frame_size_mb, self._full_frame_shape = self._get_frame_details()
        if stub_test:
            self.video_capture_ob.frame_count = 10
        super().__init__(
            buffer_gb=buffer_gb,
            chunk_shape=chunk_shape,
            display_progress=True,
        )

    def _get_default_chunk_shape(self, chunk_mb):
        """Shape is either one frame or a subset: scaled frame size but with all pixel colors"""
        return self._fit_frames_to_size(chunk_mb)

    def _get_default_buffer_shape(self, buffer_gb):
        """Buffer shape is a multiple of frame shape along the frame dimension."""
        assert buffer_gb >= self._full_frame_size_mb / 1e3, f"provide buffer size >= {self._full_frame_size_mb/1e3} GB"
        return self._fit_frames_to_size(buffer_gb * 1e3)

    def _fit_frames_to_size(self, size_mb):
        """Finds the number of frames which fit size_mb and returns the full frame shape."""
        frames_count = self._scale_shape_to_size(
            size_mb=size_mb,
            shape=self._full_frame_shape[:1],
            size=self._full_frame_size_mb,
            max_shape=self._maxshape[:1],
        )
        return frames_count + tuple(self._maxshape[1:])

    @staticmethod
    def _scale_shape_to_size(size_mb, shape, size, max_shape):
        """Given the shape and size of array, return shape that will fit size_mb."""
        k = np.floor((size_mb / size) ** (1 / len(shape)))
        return tuple([min(max(int(x), shape[j]), max_shape[j]) for j, x in enumerate(k * np.array(shape))])

    def _get_frame_details(self):
        """Get frame shape and size in MB"""
        frame_shape = (1, *self.video_capture_ob.get_frame_shape())
        min_frame_size_mb = (np.prod(frame_shape) * self._get_dtype().itemsize) / 1e6
        return min_frame_size_mb, frame_shape

    def _get_data(self, selection: Tuple[slice]) -> np.ndarray:
        start_frame = selection[0].start
        end_frame = selection[0].stop
        frames = np.empty(shape=[end_frame - start_frame, *self._maxshape[1:]])
        for frame_number in range(end_frame - start_frame):
            frames[frame_number] = next(self.video_capture_ob)
        return frames

    def _get_dtype(self):
        return self.video_capture_ob.get_movie_frame_dtype()

    def _get_maxshape(self):
        return (self.video_capture_ob.get_movie_frame_count(), *self.video_capture_ob.get_frame_shape())
