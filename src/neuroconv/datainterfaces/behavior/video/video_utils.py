import math
from typing import Optional, Tuple

import numpy as np
from pydantic import FilePath
from tqdm import tqdm

from neuroconv.tools.hdmf import GenericDataChunkIterator

from ....tools import get_package


def get_video_timestamps(file_path: FilePath, max_frames: Optional[int] = None, display_progress: bool = True) -> list:
    """Extract the timestamps of the video located in file_path

    Parameters
    ----------
    file_path : Path or str
        The path to a multimedia video file
    max_frames : Optional[int], optional
        If provided, extract the timestamps of the video only up to max_frames.
    display_progress : bool, default: True
        Whether to display a progress bar during timestamp extraction.

    Returns
    -------
    list
        The timestamps of the video.
    """

    with VideoCaptureContext(str(file_path)) as video_context:
        timestamps = video_context.get_video_timestamps(max_frames=max_frames, display_progress=display_progress)

    return timestamps


class VideoCaptureContext:
    """Retrieving video metadata and frames using a context manager."""

    def __init__(self, file_path: FilePath):
        cv2 = get_package(package_name="cv2", installation_instructions="pip install opencv-python-headless")

        self.vc = cv2.VideoCapture(filename=file_path)
        self.file_path = file_path
        self._current_frame = 0
        self._frame_count = None
        self._video_open_msg = "The video file is not open!"

    def get_video_timestamps(self, max_frames: Optional[int] = None, display_progress: bool = True):
        """
        Return numpy array of the timestamps(s) for a video file.

        Parameters
        ----------
        max_frames : Optional[int], optional
            If provided, extract the timestamps of the video only up to max_frames.
        display_progress : bool, default: True
            Whether to display a progress bar during timestamp extraction.

        Returns
        -------
        numpy.ndarray
            Array of timestamps in seconds, representing the time from the start
            of the video for each frame. Timestamps are extracted from the video's
            metadata using cv2.CAP_PROP_POS_MSEC and converted from milliseconds
            to seconds.
        """
        cv2 = get_package(package_name="cv2", installation_instructions="pip install opencv-python-headless")

        timestamps = []
        total_frames = self.get_video_frame_count()
        frames_to_extract = min(total_frames, max_frames) if max_frames else total_frames

        iterator = (
            tqdm(range(frames_to_extract), desc="retrieving timestamps")
            if display_progress
            else range(frames_to_extract)
        )
        for _ in iterator:
            success, _ = self.vc.read()
            if not success:
                break
            timestamps.append(self.vc.get(cv2.CAP_PROP_POS_MSEC))
        return np.array(timestamps) / 1000

    def get_video_fps(self) -> int:
        """
        Return the internal frames per second (fps) for a video file.

        Returns
        -------
        float
            The frames per second of the video.
        """
        assert self.isOpened(), self._video_open_msg
        prop = self.get_cv_attribute("CAP_PROP_FPS")
        return self.vc.get(prop)

    def get_frame_shape(self) -> Tuple:
        """
        Return the shape of frames from a video file.

        Returns
        -------
        Tuple
            The shape of the video frames (height, width, channels).
        """
        frame = self.get_video_frame(0)
        if frame is not None:
            return frame.shape

    @property
    def frame_count(self):
        if self._frame_count is None:
            self._frame_count = self._video_frame_count()
        return self._frame_count

    @frame_count.setter
    def frame_count(self, val: int):
        assert val > 0, "You must set a positive frame_count (received {val})."
        assert (
            val <= self._video_frame_count()
        ), "Cannot set manual frame_count beyond length of video (received {val})."
        self._frame_count = val

    def get_video_frame_count(self) -> int:
        """
        Get the total number of frames in the video.

        Returns
        -------
        int
            The total number of frames in the video.
        """
        return self.frame_count

    def _video_frame_count(self):
        """Return the total number of frames for a video file."""
        assert self.isOpened(), self._video_open_msg
        prop = self.get_cv_attribute("CAP_PROP_FRAME_COUNT")
        return int(self.vc.get(prop))

    @staticmethod
    def get_cv_attribute(attribute_name: str):
        """
        Get an OpenCV attribute by name.

        Parameters
        ----------
        attribute_name : str
            The name of the OpenCV attribute to get.

        Returns
        -------
        Any
            The OpenCV attribute value.
        """
        cv2 = get_package(package_name="cv2", installation_instructions="pip install opencv-python-headless")

        if int(cv2.__version__.split(".")[0]) < 3:  # pragma: no cover
            return getattr(cv2.cv, "CV_" + attribute_name)
        return getattr(cv2, attribute_name)

    @property
    def current_frame(self):
        return self._current_frame

    @current_frame.setter
    def current_frame(self, frame_number: int):
        assert self.isOpened(), self._video_open_msg
        set_arg = self.get_cv_attribute("CAP_PROP_POS_FRAMES")
        set_value = self.vc.set(set_arg, frame_number)
        if set_value:
            self._current_frame = frame_number
        else:
            raise ValueError(f"Could not set frame number (received {frame_number}).")

    def get_video_frame(self, frame_number: int):
        """
        Return the specific frame from a video as an RGB colorspace.

        Parameters
        ----------
        frame_number : int
            The index of the frame to retrieve.

        Returns
        -------
        numpy.ndarray
            The video frame in RGB colorspace with shape (height, width, 3).
        """
        assert self.isOpened(), self._video_open_msg
        assert frame_number < self.get_video_frame_count(), "frame number is greater than length of video"
        initial_frame_number = self.current_frame
        self.current_frame = frame_number
        success, frame = self.vc.read()
        self.current_frame = initial_frame_number
        return np.flip(frame, 2)  # np.flip to re-order color channels to RGB

    def get_video_frame_dtype(self):
        """
        Return the dtype for frame in a video file.

        Returns
        -------
        numpy.dtype
            The data type of the video frames.
        """
        frame = self.get_video_frame(0)
        if frame is not None:
            return frame.dtype

    def release(self):
        self.vc.release()

    def isOpened(self):
        return self.vc.isOpened()

    def __iter__(self):
        return self

    def __next__(self):
        assert self.isOpened(), self._video_open_msg
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
        cv2 = get_package(package_name="cv2", installation_instructions="pip install opencv-python-headless")

        self.vc = cv2.VideoCapture(self.file_path)
        return self

    def __exit__(self, *args):
        self.vc.release()

    def __del__(self):
        self.vc.release()


class VideoDataChunkIterator(GenericDataChunkIterator):
    """DataChunkIterator specifically for use on Video objects."""

    def __init__(
        self,
        video_file: FilePath,
        buffer_gb: float = None,
        chunk_shape: tuple = None,
        stub_test: bool = False,
    ):
        self.video_capture_ob = VideoCaptureContext(video_file)
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
        k = math.floor((size_mb / size) ** (1 / len(shape)))
        return tuple([min(max(int(x), shape[j]), max_shape[j]) for j, x in enumerate(k * np.array(shape))])

    def _get_frame_details(self):
        """Get frame shape and size in MB"""
        frame_shape = (1, *self.video_capture_ob.get_frame_shape())
        min_frame_size_mb = (math.prod(frame_shape) * self._get_dtype().itemsize) / 1e6
        return min_frame_size_mb, frame_shape

    def _get_data(self, selection: tuple[slice]) -> np.ndarray:
        start_frame = selection[0].start
        end_frame = selection[0].stop
        frames = np.empty(shape=[end_frame - start_frame, *self._maxshape[1:]])
        for frame_number in range(end_frame - start_frame):
            frames[frame_number] = next(self.video_capture_ob)
        return frames

    def _get_dtype(self):
        return self.video_capture_ob.get_video_frame_dtype()

    def _get_maxshape(self):
        return (self.video_capture_ob.get_video_frame_count(), *self.video_capture_ob.get_frame_shape())
