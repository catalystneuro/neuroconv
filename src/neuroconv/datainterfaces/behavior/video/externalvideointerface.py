import warnings
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.device import Device, DeviceModel
from pynwb.image import ImageSeries

from .video_utils import VideoCaptureContext
from ...._temporal_alignment import _TemporalAlignment
from ....basedatainterface import BaseDataInterface
from ....tools import get_package
from ....tools.nwb_helpers import _add_device_to_nwbfile, get_module
from ....utils import (
    DeepDict,
    calculate_regular_series_rate,
    dict_deep_update,
    get_base_schema,
    get_schema_from_hdmf_class,
)


def _compute_segment_keys(file_paths: list[Path]) -> list[str]:
    """
    Return one alignment key per file, in the order given, built from the file's stem and, only where needed,
    its parent folder names.

    A file whose stem is unique among ``file_paths`` keeps that stem as its key. Where two or more files'
    current keys collide, every one of those files has its key lengthened by one more parent folder name
    (closest first, joined with ``"_"``), repeated until the keys differ or a file has used every parent
    folder in its path (the filesystem root/anchor is never included). Raises :class:`ValueError` when a
    collision remains even after every file involved has used its full path, which happens only when two
    files are the same path, or when their full paths still cannot be told apart under this scheme.
    """
    ancestors = []
    stems = []
    for file_path in file_paths:
        parts = file_path.parts
        if file_path.anchor:
            parts = parts[len(Path(file_path.anchor).parts) :]
        ancestors.append(tuple(parts[:-1]))
        stems.append(file_path.stem)
    max_levels = [len(parent_parts) for parent_parts in ancestors]
    levels = [0] * len(file_paths)

    def _key_at(index: int) -> str:
        level = levels[index]
        parent_parts = ancestors[index]
        prefix = parent_parts[len(parent_parts) - level :] if level else ()
        return "_".join((*prefix, stems[index]))

    keys = [_key_at(index) for index in range(len(file_paths))]
    while True:
        groups: dict[str, list[int]] = {}
        for index, key in enumerate(keys):
            groups.setdefault(key, []).append(index)
        colliding_groups = [indices for indices in groups.values() if len(indices) > 1]
        if not colliding_groups:
            return keys
        grew = False
        for indices in colliding_groups:
            for index in indices:
                if levels[index] < max_levels[index]:
                    levels[index] += 1
                    keys[index] = _key_at(index)
                    grew = True
        if not grew:
            conflicting_paths = sorted({str(file_paths[index]) for indices in colliding_groups for index in indices})
            raise ValueError(
                "Each video file is addressed for alignment by a key built from its stem and, where needed, "
                "its parent folder names, but these files still collide even using their full paths: "
                f"{conflicting_paths}. Pass each file once, or rename it so its full path differs from the others."
            )


class ExternalVideoInterface(BaseDataInterface):
    """Data interface for writing videos as external_file ImageSeries."""

    display_name = "Video"
    keywords = ("video", "behavior")
    associated_suffixes = (".mp4", ".avi", ".wmv", ".mov", ".flv", ".mkv")
    # Other suffixes, while they can be opened by OpenCV, are not supported by DANDI so should probably not list here
    info = "Interface for handling standard video file formats and writing them as ImageSeries with external_files."

    @validate_call
    def __init__(
        self,
        file_paths: list[FilePath],
        verbose: bool = False,
        *,
        metadata_key: str | None = None,
        video_name: str | None = None,
    ):
        """
        Initialize the interface.

        This interface handles multiple video segments and writes them as an ImageSeries with a link to external_file.
        For writing videos internally with just an ImageSeries object, use the InternalVideoInterface.

        Parameters
        ----------
        file_paths : list of FilePaths
            Many video storage formats segment a sequence of videos over the course of the experiment.
            Pass the file paths for this videos as a list in sorted, consecutive order.

            Each file is separately addressable for alignment under a key derived from its path, so
            ``file_paths=["trial_01.avi", "trial_02.avi"]`` gives ``alignment["trial_01"]`` and
            ``alignment["trial_02"]``. The key is the file's stem where that stem is unique among
            ``file_paths``; where two or more files share a stem, e.g. ``file_paths=["day_1/video.avi",
            "day_2/video.avi"]``, each of those files' keys is lengthened with its parent folder names,
            closest first, until they differ, giving ``alignment["day_1_video"]`` and
            ``alignment["day_2_video"]`` here. Only a collision that survives even the files' full paths
            raises, which happens for the same path passed twice.
        verbose : bool, optional
            If True, display verbose output. Defaults to False.
        metadata_key : str, optional
            Snake_case key that identifies this video's entry under
            ``metadata["Behavior"]["ExternalVideos"]`` and is used for cross-component linking. Defaults
            to ``f"video_{file_paths[0].stem}"`` if not provided. The ImageSeries name is the entry's
            ``name`` field (a human-readable name, defaulting to ``f"Video {file_paths[0].stem}"``, kept
            distinct from the key), so multiple video streams in one experiment each get a unique entry:

            ```
            metadata["Behavior"]["ExternalVideos"] = {
                # key is the metadata_key (address); "name" is the ImageSeries name (distinct)
                "back_camera": dict(name="BackCamera", description="description 1.", unit="Frames"),
                "side_camera": dict(name="SideCamera", description="description 2.", unit="Frames"),
                ...
            }
            ```

            Each entry corresponds to a separate ExternalVideoInterface and ImageSeries. Note that
            metadata["Behavior"]["ExternalVideos"] is specific to the ExternalVideoInterface.
        video_name : str, optional
            Convenience for setting the ImageSeries ``name`` (the entry's ``name`` field) without
            editing the metadata dict. Defaults to ``f"Video {file_paths[0].stem}"``. An explicit
            ``name`` in the metadata passed to ``add_to_nwbfile`` takes precedence over this.
        """
        get_package(package_name="cv2", installation_instructions="pip install opencv-python-headless")
        file_paths = [Path(file_path) for file_path in file_paths]
        self.verbose = verbose
        self._number_of_files = len(file_paths)
        self._frame_counts = None
        self._frame_rates = None
        self._first_frame_times = None

        # Alignment by composition, the component the fiber photometry and events interfaces hold. Each
        # video file is triggered on its own, so each is separately addressable, keyed by its stem and, where
        # stems collide, by its parent folder names too: `alignment[key].move_start_to(t)` places one file,
        # `alignment[key].set_times(times)` re-times one file and `alignment.shift_times(delta)` moves them
        # all. See neuroconv/_temporal_alignment.py.
        self._segment_keys = _compute_segment_keys(file_paths)
        self.alignment = _TemporalAlignment()
        for file_index, segment_key in enumerate(self._segment_keys):
            # Callables, so registering the files reads none of them.
            # Every file starts where its container puts its first frame, usually zero, until it is placed:
            # several files record nothing about how they relate, so none is assumed, and files left unplaced
            # overlap and raise when written.
            self.alignment._register_series(
                key=segment_key,
                get_default_times=partial(self._get_default_times, file_index=file_index),
                default_start_time=partial(self._get_first_frame_time, file_index=file_index),
            )
        # metadata_key is the snake_case registry key (for cross-component linking); the ImageSeries
        # name is kept distinct and is never derived from the key. Name precedence: explicit
        # video_name, else a stem-based default. video_name is retained as a back-compat convenience.
        self.metadata_key = metadata_key if metadata_key else f"video_{file_paths[0].stem}"
        self._default_name = video_name if video_name else f"Video {file_paths[0].stem}"
        self._default_device_metadata_key = f"{self.metadata_key}_camera"
        self._default_device_name = f"{self._default_name} Camera Device"
        super().__init__(file_paths=file_paths)

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
        metadata_schema["properties"]["Behavior"]["required"].append("ExternalVideos")
        metadata_schema["properties"]["Behavior"]["properties"]["ExternalVideos"] = {
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
                "ExternalVideos": {
                    self.metadata_key: dict(
                        name=self._default_name,
                        description="Video recorded by camera.",
                        unit="Frames",
                        device_metadata_key=self._default_device_metadata_key,
                    )
                },
            },
        }
        return dict_deep_update(metadata, video_metadata)

    def get_header_frame_counts(self) -> list[int]:
        """
        Return the number of frames held by each video file.

        Named for where the number comes from, because a container header can be missing it or state it
        wrongly, which is what :meth:`_check_timestamps_number_matches_frames` has to allow for. Public
        because a conversion that measures its frame times from a pulse train wants to check the pulse
        count against it before setting anything, and a method so that an interface which knows the count
        without a file to open can supply it.

        Returns
        -------
        list of int
            The frame count of each file, in the order the files were passed.
        """
        if self._frame_counts is None:
            frame_counts = []
            for file_path in self.source_data["file_paths"]:
                with VideoCaptureContext(file_path=str(file_path)) as video:
                    frame_counts.append(video.get_video_frame_count())
            self._frame_counts = frame_counts
        return self._frame_counts

    def _check_timestamps_number_matches_frames(self, segment_timestamps: list[np.ndarray]) -> None:
        """
        Raise when the times about to be written for a video file do not number one per frame of that file.

        An external ``ImageSeries`` carries no data, so the length of its ``timestamps`` *is* its sample
        count, while ``external_file`` and ``starting_frame`` describe however many frames the files
        actually hold. A mismatch therefore writes a series that contradicts itself, and nothing downstream
        reports it, which is why it is caught here rather than left to a reader.

        Checked file by file rather than on the total: times given to the wrong file can leave the total
        right, and the error can then name the file.

        Only the array path is checked. Where the times come from the files themselves, nothing has been
        set and the count matches by construction.

        Parameters
        ----------
        segment_timestamps : list of numpy.ndarray
            The times of each file, in the order the files were passed, as they are about to be written.
        """
        # OpenCV reads this out of the container header rather than by counting, and returns 0 where the
        # header does not carry it, which happens with streams and with growing or truncated files. Zero
        # frames cannot contradict any number of timestamps, so an unreadable count disables the check
        # for that file rather than failing it. Negative is guarded against too, defensively rather than
        # from a known case.
        frame_counts = self.get_header_frame_counts()
        for segment_key, timestamps, frame_count in zip(self._segment_keys, segment_timestamps, frame_counts):
            if frame_count <= 0:
                continue
            if len(timestamps) != frame_count:
                raise ValueError(
                    f"{len(timestamps)} timestamps were set on '{segment_key}', a video file of {frame_count} "
                    "frames, and an external ImageSeries carries one time per frame. A few timestamps short of "
                    "the frame count usually means the camera dropped frames, and many more than it usually "
                    "means the signal you read them from was already running before the camera started."
                )

    def get_header_frame_rates(self) -> list[float]:
        """
        Return the frames per second each video file's container header states.

        Named for where the number comes from, because **the header can be wrong and the file will not say
        so.** Two documented cases, neither of them variable-frame-rate footage: an IBL Brain Wide Map
        camera whose container declares exactly 150 fps against a hardware-measured 150.4083, which is
        11.5 seconds of drift over a session on perfectly evenly spaced frames; and the UCLA Miniscope DAQ,
        which hardcodes 60 into its writer against a true rate nearer 28, deliberately, so that users do not
        timestamp frames from it. Only a signal recorded alongside the video settles the question, which is
        what :ref:`align_external_video` is about.

        Public alongside :meth:`get_header_frame_counts` because a caller placing files that run on from each other
        needs both, the length of a file being its frame count over its rate.

        Returns
        -------
        list of float
            The frame rate each file's header states, in the order the files were passed.
        """
        if self._frame_rates is None:
            frame_rates = []
            for file_path in self.source_data["file_paths"]:
                with VideoCaptureContext(file_path=str(file_path)) as video:
                    frame_rates.append(video.get_video_fps())
            self._frame_rates = frame_rates
        return self._frame_rates

    def _get_default_times(self, *, file_index: int) -> np.ndarray:
        """
        Return the times of one video file as the files themselves describe them.

        These are **not** the presentation timestamps the container carries per frame. Those come from
        :meth:`get_original_timestamps`, which reads every frame of every file to collect them, and the
        write path has never used them: before this interface held an alignment it wrote ``starting_time``
        plus ``get_video_fps()`` for a video nothing had aligned, which is what is reconstructed here. Two
        header reads rather than a full pass, and the result still collapses to a rate on the way out.

        Do not read that as accurate for evenly spaced footage. It is only as good as the header's frame
        rate, and :meth:`get_header_frame_rates` records how wrong that can be on video whose frames are
        perfectly regular. Decoding the presentation timestamps is usually no better, since they are
        commonly derived from the same declared rate. What settles it is a signal recorded alongside the
        video, handed to ``alignment[key].set_times(...)``; these times are what gets written when nobody
        has done that.

        Every file starts at the time its container stores for its first frame, which is zero for most
        files, and the header rate spaces the rest. Several files do not say among themselves how they
        relate: a recorder that rotated its output and a camera triggered once per trial produce the same
        files, one segment running on from the last and the other separated by gaps. So nothing is assumed,
        and each file is placed with ``alignment[key].move_start_to(...)``; files left unplaced overlap,
        which the write refuses.
        """
        frame_counts = self.get_header_frame_counts()
        frame_rates = self.get_header_frame_rates()
        first_frame_time = self._get_first_frame_time(file_index=file_index)
        return first_frame_time + np.arange(frame_counts[file_index]) / frame_rates[file_index]

    def _get_first_frame_time(self, *, file_index: int) -> float:
        """
        Return the time one video file's container stores for its first frame, reading only that frame.

        This is the file's native start. The header gives a count and a rate but no start, so the start is
        taken from the container, which keeps it wherever the source put it: zero for most files. It is also
        the first value of :meth:`_get_container_times`, so a placement computed against it holds whether a
        file is written with header-rate times or with the container's own.
        """
        if self._first_frame_times is None:
            first_frame_times = []
            for file_path in self.source_data["file_paths"]:
                with VideoCaptureContext(file_path=str(file_path)) as video:
                    timestamps = video.get_video_timestamps(max_frames=1, display_progress=False)
                first_frame_times.append(float(timestamps[0]) if timestamps.size else 0.0)
            self._first_frame_times = first_frame_times
        return self._first_frame_times[file_index]

    def _get_container_times(self, *, file_index: int) -> np.ndarray:
        """
        Return the timestamps one video file's container stores for its frames, reading every frame.

        These are the timestamps ``get_original_timestamps`` returns, not the header-rate default
        :meth:`_get_default_times` builds. Used only by :meth:`_get_aligned_timestamps` when
        ``always_write_timestamps=True`` and the file has no times set, in place of that default. Slow: it
        opens the file and reads every frame. They start at :meth:`_get_first_frame_time`, the start the
        default times share, so an offset stored by ``move_start_to`` places them the same way.
        """
        file_path = self.source_data["file_paths"][file_index]
        with VideoCaptureContext(file_path=str(file_path)) as video:
            return video.get_video_timestamps()

    def _get_compact_timing(self) -> tuple[float, float] | None:
        """
        Return ``(starting_time, rate)`` where the interface can state them exactly, and ``None`` otherwise.

        An ``ImageSeries`` whose frames are evenly spaced carries a starting time and a rate rather than an
        array, and while the write path recovers a rate from the times, recovering it is not the same as
        knowing it: a rate read off a container header comes back as 29.999999999999993 once it has been
        divided into an array and fitted again. So where the files still run at the rate they were recorded
        at, the answer is given rather than derived, which also means no array is built for the case that
        does not need one.
        """
        # Times that were set are the case an array exists for, and they may be irregular.
        if any(self.alignment[segment_key]._times is not None for segment_key in self._segment_keys):
            return None
        frame_rates = self.get_header_frame_rates()
        if len(set(frame_rates)) != 1:
            return None
        # Files placed independently generally leave gaps between them, and one rate cannot carry a gap. The
        # starts come from the headers, so nothing is built to find out.
        starting_times = np.array([self.alignment[segment_key]._get_start_time() for segment_key in self._segment_keys])
        durations = np.array(self.get_header_frame_counts()) / np.array(frame_rates)
        contiguous_starting_times = starting_times[0] + np.concatenate([[0.0], np.cumsum(durations[:-1])])
        if not np.allclose(starting_times, contiguous_starting_times, rtol=0.0, atol=1e-9):
            return None
        return float(starting_times[0]), frame_rates[0]

    def _get_aligned_timestamps(self, *, always_write_timestamps: bool = False) -> np.ndarray:
        """
        Return one timeline for the whole ``ImageSeries``, the files concatenated in the order given.

        The ``ImageSeries`` carries a single time coordinate across every ``external_file``, so in the order
        the files were passed, each file's first frame has to come strictly after the previous file's last
        frame. Files that overlap, or share an instant, describe no such timeline. The check is on the times
        themselves rather than on which alignment calls were made, so it holds whoever placed the files and
        at whatever scope: files nobody placed all start at their container's first frame time, usually
        zero, and fail it, and so do files corrected as a
        block but never placed one by one.

        With ``always_write_timestamps=True``, a file that has no times set (``set_times``, ``remap_times``,
        or a deprecated setter) is based on its container's own per-frame timestamps
        (:meth:`_get_container_times`) instead of the header-rate default, decoding every frame of
        that file; a file with times set is unaffected and keeps them. Either way the object's own offset and
        the interface's offset are added exactly as :meth:`_TimeBearingSeries.get_times` would.
        """
        segment_times = []
        for file_index, segment_key in enumerate(self._segment_keys):
            time_bearing_object = self.alignment[segment_key]
            if always_write_timestamps and time_bearing_object._times is None:
                base_times = self._get_container_times(file_index=file_index)
                times = base_times + time_bearing_object._object_offset + self.alignment.offset
            else:
                times = time_bearing_object.get_times()
            segment_times.append(times)
        # Before the overlap check, since times on the wrong file usually cause both and the count names it.
        self._check_timestamps_number_matches_frames(segment_timestamps=segment_times)
        self._check_files_do_not_overlap(segment_times=segment_times)
        return np.concatenate(segment_times)

    def _check_files_do_not_overlap(self, segment_times: list[np.ndarray]) -> None:
        """Raise when a file does not start strictly after the one before it ends, in the order given."""
        previous_segment_key, previous_end_time = None, None
        for segment_key, times in zip(self._segment_keys, segment_times):
            if len(times) == 0:
                continue
            if previous_end_time is not None and times[0] <= previous_end_time:
                raise ValueError(
                    f"The video file '{segment_key}' starts at {times[0]} s, which is not after the file before "
                    f"it, '{previous_segment_key}', ends at {previous_end_time} s. One ImageSeries carries a "
                    "single timeline, so each file has to begin after the previous one ends. Until it is "
                    "placed, every file starts where its container puts its first frame, usually zero: say "
                    "where each begins with "
                    "`alignment[key].move_start_to(starting_time)`, or give it the times a pulse recorded for "
                    "every frame with `alignment[key].set_times(times)`. For one recording split into several "
                    "files, place each where the one before it ended."
                )
            previous_segment_key, previous_end_time = segment_key, times[-1]

    def get_original_timestamps(self, stub_test: bool = False) -> list[np.ndarray]:
        """
        Retrieve the original unaltered timestamps for the data in this interface.

        This function should retrieve the data on-demand by re-initializing the IO.

        Returns
        -------
        timestamps : numpy.ndarray
            The timestamps for the data stream.
        stub_test : bool, default: False
            This method scans through each video; a process which can take some time to complete.

            To limit that scan to a small number of frames, set `stub_test=True`.
        """
        max_frames = 10 if stub_test else None
        timestamps = list()
        for j, file_path in enumerate(self.source_data["file_paths"]):
            with VideoCaptureContext(file_path=str(file_path)) as video:
                # fps = video.get_video_fps()  # There is some debate about whether the OpenCV timestamp
                # method is simply returning range(length) / fps 100% of the time for any given format
                timestamps.append(video.get_video_timestamps(max_frames=max_frames))
        return timestamps

    def get_timestamps(self, stub_test: bool = False) -> list[np.ndarray]:
        """
        Retrieve the timestamps for the data in this interface.

        .. deprecated::
            Use ``interface.alignment[key].get_times()``, which reads the file it names rather than
            handing back a list whose order the caller has to know. Removed in v0.12.0.

        Returns
        -------
        timestamps : list of numpy.ndarray
            The timestamps of each video file: the times set on it or, where none were set, the timestamps
            stored in the video file, as this method returned before the alignment surface.
        stub_test : bool, default: False
            Where no timestamps were set they are read with `get_original_timestamps`, which reads every
            frame; `stub_test=True` reads only the first 10 frames of each file.
        """
        warnings.warn(
            "`get_timestamps` is deprecated and will be removed in v0.12.0. "
            "Use `interface.alignment[key].get_times()` instead.",
            FutureWarning,
            stacklevel=2,
        )
        times_were_set = [self.alignment[segment_key]._times is not None for segment_key in self._segment_keys]
        if not all(times_were_set):
            original_timestamps = self.get_original_timestamps(stub_test=stub_test)
        return [
            self.alignment[segment_key].get_times() if times_were_set[file_index] else original_timestamps[file_index]
            for file_index, segment_key in enumerate(self._segment_keys)
        ]

    def set_aligned_timestamps(self, aligned_timestamps: list[np.ndarray]):
        """
        Replace all timestamps for this interface with those aligned to the common session start time.

        .. deprecated::
            Use ``interface.alignment[key].set_times(times)``, which names the file the times land on.
            Removed in v0.12.0.

        Parameters
        ----------
        aligned_timestamps : list of numpy.ndarray
            The synchronized timestamps for data in this interface, one array per video file.
        """
        warnings.warn(
            "`set_aligned_timestamps` is deprecated and will be removed in v0.12.0. "
            "Use `interface.alignment[key].set_times(times)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        self._set_aligned_timestamps(aligned_timestamps=aligned_timestamps)

    def _set_aligned_timestamps(self, aligned_timestamps: list[np.ndarray]):
        """Set one array of times per video file, the undeprecated body of ``set_aligned_timestamps``."""
        number_of_arrays = len(aligned_timestamps)
        if number_of_arrays != self._number_of_files:
            raise ValueError(
                f"There is one array of timestamps per video file, but {number_of_arrays} were given for "
                f"{self._number_of_files} files."
            )
        for segment_key, timestamps in zip(self._segment_keys, aligned_timestamps):
            self.alignment[segment_key].set_times(timestamps)

    def set_aligned_starting_time(self, aligned_starting_time: float):
        """
        Set the aligned starting time for the ImageSeries in this interface.

        With no times set on any file, the files are placed end to end with the first one starting at
        ``aligned_starting_time``, as this method has always done; otherwise every file is shifted by it.

        .. deprecated::
            Use ``interface.alignment[key].move_start_to(starting_time)`` to place each file, or
            ``interface.alignment.shift_times(delta)`` to move files already placed. Removed in v0.12.0.

        Parameters
        ----------
        aligned_starting_time : float
            The common starting time for all segments of temporal data in this interface.
        """
        warnings.warn(
            "`set_aligned_starting_time` is deprecated and will be removed in v0.12.0. Use "
            "`interface.alignment[key].move_start_to(starting_time)` to place each file, or "
            "`interface.alignment.shift_times(delta)` to move files already placed.",
            FutureWarning,
            stacklevel=2,
        )
        times_were_set = any(self.alignment[segment_key]._times is not None for segment_key in self._segment_keys)
        if times_were_set:
            self.alignment.shift_times(aligned_starting_time)
            return
        frame_counts = self.get_header_frame_counts()
        frame_rates = self.get_header_frame_rates()
        if len(set(frame_rates)) > 1:
            # As before the alignment surface: one starting time and the first file's rate for every frame of
            # every file. Wrong for the files at another rate, and kept until the method's removal.
            first_frame_indices = np.concatenate([[0], np.cumsum(frame_counts)[:-1]])
            for segment_key, first_frame_index, frame_count in zip(
                self._segment_keys, first_frame_indices, frame_counts
            ):
                frame_indices = first_frame_index + np.arange(frame_count)
                self.alignment[segment_key].set_times(aligned_starting_time + frame_indices / frame_rates[0])
            return
        durations = np.array(frame_counts) / np.array(frame_rates)
        starting_times = aligned_starting_time + np.concatenate([[0.0], np.cumsum(durations)[:-1]])
        for segment_key, starting_time in zip(self._segment_keys, starting_times):
            self.alignment[segment_key].move_start_to(starting_time)

    def set_aligned_segment_starting_times(self, aligned_segment_starting_times: list[float], stub_test: bool = False):
        """
        Align the individual starting time for each video (segment) in this interface relative to the common session start time.

        .. deprecated::
            Use ``interface.alignment[key].move_start_to(starting_time)`` per file, which states where the file
            begins instead of adding an offset to whatever it currently carries, so calling it twice does not
            shift twice. Removed in v0.12.0.

        Parameters
        ----------
        aligned_segment_starting_times : list of floats
            The relative starting times of each video.
        stub_test : bool, default: False
            If timestamps have not been set on this interface, they are read from the video files with
            `get_original_timestamps`, which reads every frame; `stub_test=True` reads only the first 10 frames
            of each file.
        """
        warnings.warn(
            "`set_aligned_segment_starting_times` is deprecated and will be removed in v0.12.0. "
            "Use `interface.alignment[key].move_start_to(starting_time)` instead, which is absolute rather than "
            "relative and so does not accumulate when called twice.",
            FutureWarning,
            stacklevel=2,
        )
        self._set_aligned_segment_starting_times(
            aligned_segment_starting_times=aligned_segment_starting_times, stub_test=stub_test
        )

    def _set_aligned_segment_starting_times(self, aligned_segment_starting_times: list[float], stub_test: bool = False):
        """
        The body of the deprecated setter, kept as it behaved before the alignment surface.

        Each file's times are its set times or, where none were set, the timestamps stored in the video file,
        read frame by frame; the file's starting time is added to them and the result is set as its times.
        """
        number_of_starting_times = len(aligned_segment_starting_times)
        if number_of_starting_times != self._number_of_files:
            raise ValueError(
                f"The length of the 'aligned_segment_starting_times' list ({number_of_starting_times}) does not "
                f"match the number of video files ({self._number_of_files})!"
            )
        times_were_set = [self.alignment[segment_key]._times is not None for segment_key in self._segment_keys]
        original_timestamps = None if all(times_were_set) else self.get_original_timestamps(stub_test=stub_test)
        for file_index, (segment_key, segment_starting_time) in enumerate(
            zip(self._segment_keys, aligned_segment_starting_times)
        ):
            time_bearing_object = self.alignment[segment_key]
            if times_were_set[file_index]:
                times = time_bearing_object.get_times()
            else:
                times = original_timestamps[file_index]
            time_bearing_object.set_times(times + segment_starting_time)

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray):
        """
        Re-time this interface against a reference clock through synchronization pulses.

        .. deprecated::
            Use ``interface.alignment.remap_times(local_sync_times=..., reference_sync_times=...)``, whose
            argument names say which clock each set of pulses came off. Removed in v0.12.0.
        """
        warnings.warn(
            "`align_by_interpolation` is deprecated and will be removed in v0.12.0. Use "
            "`interface.alignment.remap_times(local_sync_times=..., reference_sync_times=...)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        self.alignment.remap_times(local_sync_times=unaligned_timestamps, reference_sync_times=aligned_timestamps)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        starting_frames: list[int] | None = None,
        parent_container: Literal["acquisition", "processing/behavior"] = "acquisition",
        module_description: str = "processed behavioral data",
        always_write_timestamps: bool = False,
    ):
        """
        Convert the video data file(s) to :py:class:`~pynwb.image.ImageSeries` and write them in the
        :py:class:`~pynwb.file.NWBFile`. Data is written in a single :py:class:`~pynwb.image.ImageSeries` container with
        a path to each external file.

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
                        external_video_camera=dict(name="CameraName", description="Camera description", ...),
                    ),
                    Behavior=dict(
                        ExternalVideos=dict(
                            external_video=dict(
                                name="ExternalVideo",
                                description="Description of the video..",
                                device_metadata_key="external_video_camera",
                                ...,
                            )
                        )
                    ),
                )

            The ExternalVideo section may contain most keywords normally accepted by an ImageSeries
            (https://pynwb.readthedocs.io/en/stable/pynwb.image.html#pynwb.image.ImageSeries).

            The camera is a top-level ``metadata["Devices"]`` entry (most keywords accepted by a Device,
            https://pynwb.readthedocs.io/en/stable/pynwb.device.html#pynwb.device.Device), referenced from
            the video entry by ``device_metadata_key``; it is created and linked to the ImageSeries,
            establishing a connection between the video data and the camera that captured it. Passing the
            camera nested under the video entry as ``device=dict(...)`` is still accepted but deprecated
            (removal on or after February 2027).
        starting_frames : list, optional
            List of start frames for each video written using external mode.
            If not provided, it is computed from the frame count of each video file.
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
            to be retrieved from the video file. A file with no times set (via ``alignment[key].set_times(...)``,
            ``remap_times``, or a deprecated setter) is then written with the timestamps stored in its video
            container, read frame by frame (slow on long videos), with any placement (``move_start_to``) or
            shift (``shift_times``) applied; a file with times set is written with those times, unchanged.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "starting_frames",
                "parent_container",
                "module_description",
                "always_write_timestamps",
            ]
            num_positional_args_before_args = 2  # nwbfile, metadata
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"add_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                    f"{len(args) + num_positional_args_before_args} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to ExternalVideoInterface.add_to_nwbfile() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            starting_frames = positional_values.get("starting_frames", starting_frames)
            parent_container = positional_values.get("parent_container", parent_container)
            module_description = positional_values.get("module_description", module_description)
            always_write_timestamps = positional_values.get("always_write_timestamps", always_write_timestamps)
        if parent_container not in {"acquisition", "processing/behavior"}:
            raise ValueError(
                f"parent_container must be either 'acquisition' or 'processing/behavior', not {parent_container}."
            )
        metadata = metadata or dict()

        file_paths = self.source_data["file_paths"]

        # Be sure to copy metadata at this step to avoid mutating in-place
        videos_metadata = deepcopy(metadata).get("Behavior", dict()).get("ExternalVideos", None)
        # If no metadata is provided use the default metadata
        if videos_metadata is None or self.metadata_key not in videos_metadata:
            videos_metadata = deepcopy(self.get_metadata()["Behavior"]["ExternalVideos"])
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
                "removed on or after February 2027. Use a top-level metadata['Devices'][key] entry referenced "
                "by 'device_metadata_key' instead.",
                FutureWarning,
                stacklevel=2,
            )
            # The deprecated nested form has no registry key, so it keeps the transitional call until
            # the December 2026 removal.
            image_series_kwargs["device"] = _add_device_to_nwbfile(
                nwbfile=nwbfile, device_metadata=legacy_device_kwargs
            )

        # One timeline across every external file, whatever it was built from: the files' own frame rates,
        # a starting time per file, or times set on one of them.
        compact_timing = None if always_write_timestamps else self._get_compact_timing()
        if compact_timing is not None:
            starting_time, rate = compact_timing
            image_series_kwargs.update(starting_time=starting_time, rate=rate)
        else:
            timestamps = self._get_aligned_timestamps(always_write_timestamps=always_write_timestamps)
            rate = None if always_write_timestamps else calculate_regular_series_rate(series=timestamps)
            if rate is not None:
                image_series_kwargs.update(starting_time=timestamps[0], rate=rate)
            else:
                image_series_kwargs.update(timestamps=timestamps)

        # The frame count of each external file backs both `num_samples` and `starting_frame`, so read it once.
        compute_starting_frames = self._number_of_files > 1 and starting_frames is None
        if "rate" in image_series_kwargs or compute_starting_frames:
            frame_counts = self.get_header_frame_counts()

        # pynwb>=4 requires num_samples on an external ImageSeries when timing is rate-based, because the
        # empty data array cannot convey the frame count. Sum the frame count across the external video files.
        if "rate" in image_series_kwargs:
            image_series_kwargs.update(num_samples=sum(frame_counts))

        if compute_starting_frames:
            starting_frames = np.cumsum([0, *frame_counts[:-1]]).tolist()
        if starting_frames is not None:
            if len(starting_frames) != self._number_of_files:
                raise ValueError(
                    f"Multiple paths ({self._number_of_files}) were specified for the ImageSeries, "
                    f"but the length of starting_frames ({len(starting_frames)}) did not match the number of paths!"
                )
            image_series_kwargs.update(starting_frame=starting_frames)

        image_series_kwargs.update(format="external", external_file=file_paths)

        # Attach image series
        image_series = ImageSeries(**image_series_kwargs)
        if parent_container == "acquisition":
            nwbfile.add_acquisition(image_series)
        elif parent_container == "processing/behavior":
            get_module(nwbfile=nwbfile, name="behavior", description=module_description).add(image_series)

        return nwbfile
