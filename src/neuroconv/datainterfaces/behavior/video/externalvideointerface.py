import warnings
from copy import deepcopy
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.image import ImageSeries

from .video_utils import VideoCaptureContext
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
        self._timestamps = None
        self._starting_time = None
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
        # The camera Device lives at top-level metadata["Devices"], referenced from the video entry
        # by ``device_metadata_key``. A nested ``device`` dict is still accepted for back-compat.
        image_series_metadata_schema["properties"]["device_metadata_key"] = {"type": "string"}
        image_series_metadata_schema["properties"]["device"] = device_metadata_schema
        metadata_schema["properties"]["Devices"] = {
            "type": "object",
            "properties": {},
            "additionalProperties": device_metadata_schema,
        }
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

        Returns
        -------
        timestamps : numpy.ndarray
            The timestamps for the data stream.
        stub_test : bool, default: False
            If timestamps have not been set to this interface, it will attempt to retrieve them
            using the `.get_original_timestamps` method, which scans through each video;
            a process which can take some time to complete.

            To limit that scan to a small number of frames, set `stub_test=True`.
        """
        return self._timestamps or self.get_original_timestamps(stub_test=stub_test)

    def set_aligned_timestamps(self, aligned_timestamps: list[np.ndarray]):
        """
        Replace all timestamps for this interface with those aligned to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_timestamps : list of numpy.ndarray
            The synchronized timestamps for data in this interface.
        """
        self._timestamps = aligned_timestamps

    def set_aligned_starting_time(self, aligned_starting_time: float):
        """
        Set the aligned starting time for the ImageSeries in this interface.

        If the timestamps have already been set, each segment will be shifted by aligned_starting_time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_starting_time : float
            The common starting time for all segments of temporal data in this interface.
        """
        if self._timestamps is not None:
            aligned_segment_starting_times = [aligned_starting_time] * self._number_of_files
            self.set_aligned_segment_starting_times(aligned_segment_starting_times=aligned_segment_starting_times)
        else:
            self._starting_time = aligned_starting_time

    def set_aligned_segment_starting_times(self, aligned_segment_starting_times: list[float], stub_test: bool = False):
        """
        Align the individual starting time for each video (segment) in this interface relative to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        If the timestamps have not already been set, this method will set them to the original timestamps and then shift
        them by the aligned segment starting times.

        Parameters
        ----------
        aligned_segment_starting_times : list of floats
            The relative starting times of each video.
        stub_test : bool, default: False
            If timestamps have not been set to this interface, it will attempt to retrieve them
            using the `.get_original_timestamps` method, which scans through each video;
            a process which can take some time to complete.

            To limit that scan to a small number of frames, set `stub_test=True`.
        """
        aligned_segment_starting_times_length = len(aligned_segment_starting_times)
        assert aligned_segment_starting_times_length == self._number_of_files, (
            f"The length of the 'aligned_segment_starting_times' list ({aligned_segment_starting_times_length}) does not match the "
            "number of video files ({self._number_of_files})!"
        )
        self._timestamps = self.get_timestamps(stub_test=stub_test)
        self.set_aligned_timestamps(
            aligned_timestamps=[
                timestamps + segment_starting_time
                for timestamps, segment_starting_time in zip(
                    self.get_timestamps(stub_test=stub_test), aligned_segment_starting_times
                )
            ]
        )

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray):
        raise NotImplementedError("The `align_by_interpolation` method has not been developed for this interface yet.")

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        starting_frames: list[int] | None = None,
        parent_container: Literal["acquisition", "processing/behavior"] = "acquisition",
        module_description: str | None = None,
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
            (removal on or after December 2026).
        starting_frames : list, optional
            List of start frames for each video written using external mode.
            Required if more than one path is specified.
        parent_container: {'acquisition', 'processing/behavior'}
            The container where the ImageSeries is added, default is nwbfile.acquisition.
            When 'processing/behavior' is chosen, the ImageSeries is added to nwbfile.processing['behavior'].
        module_description: str, optional
            If parent_container is 'processing/behavior', and the module does not exist,
            it will be created with this description. The default description is the same as used by the
            conversion_tools.get_module function.
        always_write_timestamps: bool, default: False
            Set to True to always write timestamps.
            By default (False), the function checks if timestamps are available, and if not, uses starting_time and rate.
            If set to True, timestamps will be written explicitly, regardless of whether they were set directly or need
            to be retrieved from the video file.
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
        device_metadata = None
        if device_metadata_key is not None:
            # Strict resolution against the top-level Devices registry: a missing/typo'd key raises.
            # (metadata is a DeepDict that auto-creates missing keys, so membership is checked explicitly.)
            devices_metadata = deepcopy(metadata).get("Devices") or deepcopy(self.get_metadata()["Devices"])
            if device_metadata_key not in devices_metadata:
                raise KeyError(
                    f"device_metadata_key '{device_metadata_key}' was not found in metadata['Devices'] "
                    f"(available keys: {list(devices_metadata)})."
                )
            device_metadata = devices_metadata[device_metadata_key]
        elif legacy_device_kwargs is not None:
            warnings.warn(
                "Passing the camera device nested under the video metadata entry is deprecated and will be "
                "removed on or after December 2026. Use a top-level metadata['Devices'][key] entry referenced "
                "by 'device_metadata_key' instead.",
                FutureWarning,
                stacklevel=2,
            )
            device_metadata = legacy_device_kwargs

        if device_metadata is not None:
            image_series_kwargs["device"] = _add_device_to_nwbfile(nwbfile=nwbfile, device_metadata=device_metadata)

        if always_write_timestamps:
            timestamps = self.get_timestamps()
            image_series_kwargs.update(timestamps=np.concatenate(timestamps))
        elif self._timestamps is not None:
            # Check if timestamps are regular
            timestamps = np.concatenate(self._timestamps)
            rate = calculate_regular_series_rate(series=timestamps)
            if rate is not None:
                starting_time = timestamps[0]
                image_series_kwargs.update(starting_time=starting_time, rate=rate)
            else:
                image_series_kwargs.update(timestamps=timestamps)
        else:
            if self._number_of_files > 1 and self._starting_time is None:
                raise ValueError(
                    f"No timing information is specified and there are {self._number_of_files} total video files! "
                    "Please specify the temporal alignment of each video."
                )
            starting_time = self._starting_time if self._starting_time is not None else 0.0
            with VideoCaptureContext(file_path=str(file_paths[0])) as video:
                rate = video.get_video_fps()
            image_series_kwargs.update(starting_time=starting_time, rate=rate)

        if self._number_of_files > 1 and starting_frames is None:
            raise TypeError("Multiple paths were specified for the ImageSeries, but no starting_frames were specified!")
        elif starting_frames is not None and len(starting_frames) != self._number_of_files:
            raise ValueError(
                f"Multiple paths ({self._number_of_files}) were specified for the ImageSeries, "
                f"but the length of starting_frames ({len(starting_frames)}) did not match the number of paths!"
            )
        elif starting_frames is not None:
            image_series_kwargs.update(starting_frame=starting_frames)

        image_series_kwargs.update(format="external", external_file=file_paths)

        # Attach image series
        image_series = ImageSeries(**image_series_kwargs)
        if parent_container == "acquisition":
            nwbfile.add_acquisition(image_series)
        elif parent_container == "processing/behavior":
            get_module(nwbfile=nwbfile, name="behavior", description=module_description).add(image_series)

        return nwbfile
