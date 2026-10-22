import warnings
from copy import deepcopy
from pathlib import Path
from typing import Literal

import numpy as np
import psutil
from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.device import Device, DeviceModel
from pynwb.image import ImageSeries
from tqdm import tqdm

from .video_utils import VideoCaptureContext, VideoDataChunkIterator
from ...._temporal_alignment import _TemporalAlignment
from ....basedatainterface import BaseDataInterface
from ....tools import get_package
from ....tools.nwb_helpers import _add_device_to_nwbfile, get_module
from ....utils import (
    DeepDict,
    dict_deep_update,
    get_base_schema,
    get_schema_from_hdmf_class,
)
from ....utils.str_utils import human_readable_size


class InternalVideoInterface(BaseDataInterface):
    """Data interface for writing videos as internally represented ImageSeries."""

    display_name = "Video"
    keywords = ("video",)
    associated_suffixes = (".mp4", ".avi", ".wmv", ".mov", ".flv", ".mkv")
    # Other suffixes, while they can be opened by OpenCV, are not supported by DANDI so should probably not list here
    info = "Interface for handling standard video file formats and writing them as ImageSeries with internal data."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = False,
        *,
        metadata_key: str | None = None,
        video_name: str | None = None,
    ):
        """
        Initialize the interface.

        This interface handles a single video file and writes it as an internally represented ImageSeries. For writing
        videos as external files, use the ExternalVideoInterface.

        Parameters
        ----------
        file_path : FilePath
            The path to the video file.
        verbose : bool, optional
            If True, display verbose output. Defaults to False.
        metadata_key : str, optional
            Snake_case key that identifies this video's entry under
            ``metadata["Behavior"]["InternalVideos"]`` and is used for cross-component linking. Defaults
            to ``f"video_{file_path.stem}"`` if not provided. The ImageSeries name is the entry's
            ``name`` field (a human-readable name, defaulting to ``f"Video {file_path.stem}"``, kept
            distinct from the key), so multiple video streams in one experiment each get a unique entry:

            ```
            metadata["Behavior"]["InternalVideos"] = {
                # key is the metadata_key (address); "name" is the ImageSeries name (distinct)
                "back_camera": dict(name="BackCamera", description="description 1.", unit="Frames"),
                "side_camera": dict(name="SideCamera", description="description 2.", unit="Frames"),
                ...
            }
            ```

            Each entry corresponds to a separate InternalVideoInterface and ImageSeries. Note that
            metadata["Behavior"]["InternalVideos"] is specific to the InternalVideoInterface.
        video_name : str, optional
            Convenience for setting the ImageSeries ``name`` (the entry's ``name`` field) without
            editing the metadata dict. Defaults to ``f"Video {file_path.stem}"``. An explicit
            ``name`` in the metadata passed to ``add_to_nwbfile`` takes precedence over this.
        """
        get_package(package_name="cv2", installation_instructions="pip install opencv-python-headless")
        file_path = Path(file_path)
        self.verbose = verbose
        self._header_timing = None
        # metadata_key is the registry key (for cross-component linking); the ImageSeries name is
        # kept distinct and is never derived from the key. Name precedence: explicit video_name, else
        # a stem-based default. video_name is retained as a back-compat convenience.
        self.metadata_key = metadata_key if metadata_key else f"video_{Path(file_path).stem}"
        self._default_name = video_name if video_name else f"Video {Path(file_path).stem}"
        self._default_device_metadata_key = f"{self.metadata_key}_camera"
        self._default_device_name = f"{self._default_name} Camera Device"
        super().__init__(file_path=file_path)

        # Alignment by composition, the component `ExternalVideoInterface` holds, with the one video keyed by
        # `metadata_key`. See neuroconv/_temporal_alignment.py.
        # No sample count here, because the header can state it wrongly.
        self.temporal_alignment = _TemporalAlignment()
        self.temporal_alignment._register(
            key=self.metadata_key,
            get_native_times=self._get_default_times,
            default_start_time=lambda: self._get_header_timing()[2],
        )

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        image_series_metadata_schema = get_schema_from_hdmf_class(ImageSeries)
        # TODO: in future PR, add 'exclude' option to get_schema_from_hdmf_class to bypass this popping
        exclude = ["format", "conversion", "starting_time", "rate"]
        for key in exclude:
            image_series_metadata_schema["properties"].pop(key)
            if key in image_series_metadata_schema["required"]:
                image_series_metadata_schema["required"].remove(key)
        device_metadata_schema = get_schema_from_hdmf_class(Device)
        # A device entry may name its model, the same way the video entry names its device.
        device_metadata_schema["properties"]["device_model_metadata_key"] = {"type": "string"}
        device_model_metadata_schema = get_schema_from_hdmf_class(DeviceModel)
        # 'manufacturer' is required by NWB but is rarely recorded by an acquisition file, so it is
        # filled when the model is built rather than demanded of whoever writes the metadata.
        device_model_metadata_schema["required"].remove("manufacturer")
        # The camera Device lives at top-level metadata["Devices"], referenced from the video entry
        # by ``device_metadata_key``. A nested ``device`` dict is still accepted for back-compat.
        image_series_metadata_schema["properties"]["device_metadata_key"] = {"type": "string"}
        image_series_metadata_schema["properties"]["device"] = device_metadata_schema
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        metadata_schema["properties"]["Behavior"]["required"].append("InternalVideos")
        metadata_schema["properties"]["Behavior"]["properties"]["InternalVideos"] = {
            "type": "object",
            "properties": {self.metadata_key: image_series_metadata_schema},
            "required": [self.metadata_key],
            "additionalProperties": True,
        }
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        video_metadata = {
            "Devices": {
                self._default_device_metadata_key: dict(
                    name=self._default_device_name,
                    description="Video camera used for recording.",
                ),
            },
            "Behavior": {
                "InternalVideos": {
                    self.metadata_key: dict(
                        name=self._default_name,
                        description="Video recorded by camera.",
                        unit="Frames",
                        device_metadata_key=self._default_device_metadata_key,
                    )
                }
            },
        }
        return dict_deep_update(metadata, video_metadata)

    def get_original_timestamps(self, stub_test: bool = False) -> np.ndarray:
        """
        Retrieve the original unaltered timestamps for the data in this interface.

        This function should retrieve the data on-demand by re-initializing the IO.

        Parameters
        ----------
        stub_test : bool, default: False
            If True, limits the number of frames to scan through to 10.

        Returns
        -------
        timestamps : numpy.ndarray
            The timestamps for the data stream.
        """
        max_frames = 10 if stub_test else None
        file_path = self.source_data["file_path"]
        with VideoCaptureContext(file_path=str(file_path)) as video:
            # fps = video.get_video_fps()  # There is some debate about whether the OpenCV timestamp
            # method is simply returning range(length) / fps 100% of the time for any given format
            return video.get_video_timestamps(max_frames=max_frames)

    def _get_header_timing(self) -> tuple[int, float, float]:
        """
        Return the frame count and frame rate the container header states, and the time it stores for the first frame.

        The first frame time is the video's native start, zero for most files. Reading it decodes one frame.
        """
        if self._header_timing is None:
            with VideoCaptureContext(file_path=str(self.source_data["file_path"])) as video:
                frame_count = video.get_video_frame_count()
                frame_rate = video.get_video_fps()
                timestamps = video.get_video_timestamps(max_frames=1, display_progress=False)
            first_frame_time = float(timestamps[0]) if timestamps.size else 0.0
            self._header_timing = (frame_count, frame_rate, first_frame_time)
        return self._header_timing

    def _get_default_times(self) -> np.ndarray:
        """
        Return the times of the video as its header describes them: the first frame time spaced by the header rate.

        These are not the per-frame timestamps of :meth:`get_original_timestamps`, which reads every frame. The
        write path has always used the header rate for a video nothing had aligned, and these times collapse to
        that rate when written.
        """
        frame_count, frame_rate, first_frame_time = self._get_header_timing()
        return first_frame_time + np.arange(frame_count) / frame_rate

    def _get_container_times(self) -> np.ndarray:
        """Return the timestamps the container stores for every frame, for ``always_write_timestamps=True``."""
        return self.get_original_timestamps()

    def get_timestamps(self, stub_test: bool = False) -> np.ndarray:
        """
        Retrieve the timestamps for the data in this interface.

        .. deprecated::
            Use ``interface.temporal_alignment[key].get_times()``. Removed in v0.13.0.

        Parameters
        ----------
        stub_test : bool, default: False
            Where no timestamps were set they are read with `get_original_timestamps`, which reads every
            frame; `stub_test=True` reads only the first 10 frames.

        Returns
        -------
        timestamps : numpy.ndarray
            The timestamps set on the video or, where none were set, the timestamps stored in the video file.
        """
        warnings.warn(
            "`get_timestamps` is deprecated and will be removed in v0.13.0. "
            "Use `interface.temporal_alignment[key].get_times()` instead.",
            FutureWarning,
            stacklevel=2,
        )
        time_bearing_object = self.temporal_alignment[self.metadata_key]
        if time_bearing_object._times is not None:
            return time_bearing_object.get_times()
        return self.get_original_timestamps(stub_test=stub_test)

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        """
        Replace all timestamps for this interface with those aligned to the common session start time.

        .. deprecated::
            Use ``interface.temporal_alignment[key].set_times(times)``. Removed in v0.13.0.

        Parameters
        ----------
        aligned_timestamps : numpy.ndarray
            The synchronized timestamps for data in this interface.
        """
        warnings.warn(
            "`set_aligned_timestamps` is deprecated and will be removed in v0.13.0. "
            "Use `interface.temporal_alignment[key].set_times(times)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        self.temporal_alignment[self.metadata_key].set_times(aligned_timestamps)

    def set_aligned_starting_time(self, aligned_starting_time: float, stub_test: bool = False):
        """
        Set the starting time of the video, or shift the timestamps set on it by this amount.

        .. deprecated::
            Use ``interface.temporal_alignment[key].move_start_to(starting_time)`` to place the video, or
            ``interface.temporal_alignment.shift_times(delta)`` to move it. Removed in v0.13.0.

        Parameters
        ----------
        aligned_starting_time : float
            The starting time of the video relative to the common session start time.
        stub_test : bool, default: False
            Unused, kept for backward compatibility.
        """
        warnings.warn(
            "`set_aligned_starting_time` is deprecated and will be removed in v0.13.0. Use "
            "`interface.temporal_alignment[key].move_start_to(starting_time)` to place the video, or "
            "`interface.temporal_alignment.shift_times(delta)` to move it.",
            FutureWarning,
            stacklevel=2,
        )
        time_bearing_object = self.temporal_alignment[self.metadata_key]
        # As before the alignment surface: timestamps that were set are shifted, otherwise the video is placed
        if time_bearing_object._times is not None:
            time_bearing_object.shift_times(aligned_starting_time)
        else:
            time_bearing_object.move_start_to(aligned_starting_time)

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray):
        """
        Re-express the video's times on another clock by interpolating between paired timestamps.

        .. deprecated::
            Use ``interface.temporal_alignment.remap_times(local_sync_times=..., reference_sync_times=...)``.
            Removed in v0.13.0.
        """
        warnings.warn(
            "`align_by_interpolation` is deprecated and will be removed in v0.13.0. Use "
            "`interface.temporal_alignment.remap_times(local_sync_times=..., reference_sync_times=...)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        self.temporal_alignment.remap_times(
            local_sync_times=unaligned_timestamps, reference_sync_times=aligned_timestamps
        )

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        buffer_data: bool = True,
        iterator_options: dict | None = None,
        parent_container: Literal["acquisition", "processing/behavior"] = "acquisition",
        module_description: str = "processed behavioral data",
        always_write_timestamps: bool = False,
    ):
        """
        Convert the video data files to :py:class:`~pynwb.image.ImageSeries` and write them in the
        :py:class:`~pynwb.file.NWBFile`. Data is written in the :py:class:`~pynwb.image.ImageSeries` container as
        RGB. [times, x, y, 3-RGB].

        Parameters
        ----------
        nwbfile : NWBFile, optional
            nwb file to which the recording information is to be added
        metadata : dict, optional
            Dictionary of metadata information such as name and description of the video, as well as
            device information for the camera that captured the video. The keys must correspond to
            the metadata_key specified in the constructor.
            Should be organized as follows::

                metadata = dict(
                    Devices=dict(
                        internal_video_camera=dict(name="CameraName", description="Camera description", ...),
                    ),
                    Behavior=dict(
                        InternalVideos=dict(
                            internal_video=dict(
                                name="InternalVideo",
                                description="Description of the video..",
                                device_metadata_key="internal_video_camera",
                                ...,
                            )
                        )
                    ),
                )

            The InternalVideo section may contain most keywords normally accepted by an ImageSeries
            (https://pynwb.readthedocs.io/en/stable/pynwb.image.html#pynwb.image.ImageSeries).

            The camera is a top-level ``metadata["Devices"]`` entry (most keywords accepted by a Device,
            https://pynwb.readthedocs.io/en/stable/pynwb.device.html#pynwb.device.Device), referenced from
            the video entry by ``device_metadata_key``; it is created and linked to the ImageSeries,
            establishing a connection between the video data and the camera that captured it. Passing the
            camera nested under the video entry as ``device=dict(...)`` is still accepted but deprecated
            (removal in v0.12.0).
        stub_test : bool, default: False
            If ``True``, truncates the write operation for fast testing.
        buffer_data : bool, default: True
            If True, uses a DataChunkIterator to read and write the video, reducing overhead RAM usage at the cost of
            reduced conversion speed (compared to loading video entirely into RAM as an array). This will also force to
            True, even if manually set to False, whenever the video file size exceeds available system RAM by a factor
            of 70 (from compression experiments). Based on experiments for a ~30 FPS system of ~400 x ~600 color
            frames, the equivalent uncompressed RAM usage is around 2GB per minute of video. The default is True.
        iterator_options : dict, optional
            Options for controlling iterative write when buffer_data=True.
            See the `pynwb tutorial on iterative write
            <https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/plot_iterative_write.html#sphx-glr-tutorials-advanced-io-plot-iterative-write-py>`_
            for more information on chunked data writing.

            Available options:

            * buffer_gb : float, default: 1.0
                RAM to use for buffering data chunks in GB.
            * buffer_shape : tuple, optional
                Manual specification of buffer shape. Cannot be set with buffer_gb.
            * display_progress : bool, default: False
                Enable tqdm progress bar during video write.
            * progress_bar_options : dict, optional
                Additional options passed to tqdm progress bar.
                See https://github.com/tqdm/tqdm#parameters for all tqdm options.
                Common options: 'desc' (description), 'position' (for multiple bars),
                'leave' (keep bar after completion).

            Note: To configure chunk size and compression, use the backend configuration system
            via ``get_default_backend_configuration()`` and ``configure_backend()`` after calling
            this method. See the backend configuration documentation for details.
        parent_container: {'acquisition', 'processing/behavior'}
            The container where the ImageSeries is added, default is nwbfile.acquisition.
            When 'processing/behavior' is chosen, the ImageSeries is added to nwbfile.processing['behavior'].
        module_description: str, default: "processed behavioral data"
            If parent_container is 'processing/behavior', and the module does not exist, it will be
            created with this description. The default matches what every other interface writing to that
            module uses, so a conversion combining several of them does not warn about a description
            mismatch.
        always_write_timestamps: bool, default: False
            Set to True to always write timestamps.
            By default (False), the function checks if timestamps are available, and if not, uses starting_time and rate.
            If set to True, timestamps will be written explicitly, regardless of whether they were set directly or need
            to be retrieved from the video file.
        """
        if parent_container not in {"acquisition", "processing/behavior"}:
            raise ValueError(
                f"parent_container must be either 'acquisition' or 'processing/behavior', not {parent_container}."
            )
        metadata = metadata or dict()

        file_path = Path(self.source_data["file_path"])

        # Be sure to copy metadata at this step to avoid mutating in-place
        videos_metadata = deepcopy(metadata).get("Behavior", dict()).get("InternalVideos", None)
        # If no metadata is provided use the default metadata
        if videos_metadata is None or self.metadata_key not in videos_metadata:
            videos_metadata = deepcopy(self.get_metadata()["Behavior"]["InternalVideos"])
        image_series_kwargs = videos_metadata[self.metadata_key]
        image_series_kwargs.setdefault("name", self._default_name)

        # Resolve the camera Device: prefer the top-level Devices registry referenced by
        # device_metadata_key; fall back to a (deprecated) nested "device" dict for back-compat.
        device_metadata_key = image_series_kwargs.pop("device_metadata_key", None)
        legacy_device_kwargs = image_series_kwargs.pop("device", None)
        if device_metadata_key is not None:
            # The whole metadata goes to the helper, which resolves the key strictly and raises naming
            # the registry if it holds nothing. Only the registry is swapped, for the caller who passed
            # none and gets this interface's default camera; a device entry may also name its model by
            # 'device_model_metadata_key', which the helper resolves against the rest of the metadata.
            metadata_copy = deepcopy(metadata)
            metadata_copy["Devices"] = metadata_copy.get("Devices") or deepcopy(self.get_metadata()["Devices"])
            image_series_kwargs["device"] = _add_device_to_nwbfile(
                nwbfile=nwbfile, metadata=metadata_copy, metadata_key=device_metadata_key
            )
        elif legacy_device_kwargs is not None:
            warnings.warn(
                "Passing the camera device nested under the video metadata entry is deprecated and will be "
                "removed in v0.12.0. Use a top-level metadata['Devices'][key] entry referenced "
                "by 'device_metadata_key' instead.",
                FutureWarning,
                stacklevel=2,
            )
            # The deprecated nested form has no registry key, so it keeps the transitional call until
            # the December 2026 removal.
            image_series_kwargs["device"] = _add_device_to_nwbfile(
                nwbfile=nwbfile, device_metadata=legacy_device_kwargs
            )

        # The 70 size is an estimation of the total size of the video file in memory
        uncompressed_estimate = file_path.stat().st_size * 70
        available_memory = psutil.virtual_memory().available
        if not buffer_data and not stub_test and uncompressed_estimate >= available_memory:
            warnings.warn(
                f"Not enough memory (estimated {human_readable_size(uncompressed_estimate)}) to load video file"
                f"as array ({human_readable_size(available_memory)} available)! Forcing buffer_data to True."
            )
            buffer_data = True

        if buffer_data:
            iterator_options = iterator_options or dict()
            data_iterator = VideoDataChunkIterator(
                video_file=file_path,
                stub_test=stub_test,
                **iterator_options,
            )
            image_series_kwargs.update(data=data_iterator)

        else:
            # Load the video
            with VideoCaptureContext(file_path) as video_capture_ob:

                total_frames = video_capture_ob.get_video_frame_count()
                frame_shape = video_capture_ob.get_frame_shape()
                dtype = video_capture_ob.get_video_frame_dtype()

                maxshape = (total_frames, *frame_shape)
                tqdm_pos, tqdm_mininterval = (0, 10)
                video_array = np.zeros(shape=maxshape, dtype=dtype)

                if stub_test:
                    stub_frames = 10
                    video_capture_ob.frame_count = stub_frames
                with tqdm(
                    desc=f"Reading video data for {Path(file_path).name}",
                    position=tqdm_pos,
                    total=total_frames,
                    mininterval=tqdm_mininterval,
                ) as pbar:
                    for n, frame in enumerate(video_capture_ob):
                        video_array[n, :, :, :] = frame
                        pbar.update(1)

                image_series_kwargs.update(data=video_array)

        from ....utils import calculate_regular_series_rate

        time_bearing_object = self.temporal_alignment[self.metadata_key]
        if time_bearing_object._times is None and not always_write_timestamps:
            # Times nobody set run at the header rate, so the start is all the alignment changes
            _, rate, _ = self._get_header_timing()
            image_series_kwargs.update(starting_time=time_bearing_object._get_start_time(), rate=rate)
        else:
            if always_write_timestamps:
                timestamps = time_bearing_object._get_times(get_default_times=self._get_container_times)
            else:
                timestamps = time_bearing_object.get_times()
            rate = None if always_write_timestamps else calculate_regular_series_rate(series=timestamps)
            if rate is not None:
                image_series_kwargs.update(starting_time=timestamps[0], rate=rate)
            else:
                image_series_kwargs.update(timestamps=timestamps)

        # Attach image series
        image_series = ImageSeries(**image_series_kwargs)
        if parent_container == "acquisition":
            nwbfile.add_acquisition(image_series)
        elif parent_container == "processing/behavior":
            get_module(nwbfile=nwbfile, name="behavior", description=module_description).add(image_series)

        return nwbfile
