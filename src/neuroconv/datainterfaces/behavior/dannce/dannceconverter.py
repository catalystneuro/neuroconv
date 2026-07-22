from copy import deepcopy
from pathlib import Path

from pydantic import FilePath, validate_call
from pynwb import NWBFile

from .danncedatainterface import DANNCEInterface
from ..video.externalvideointerface import ExternalVideoInterface
from ....basedatainterface import BaseDataInterface
from ....utils import DeepDict, dict_deep_update


class DANNCEConverter(BaseDataInterface):
    """
    Converter combining a :py:class:`~neuroconv.datainterfaces.DANNCEInterface` with one
    :py:class:`~neuroconv.datainterfaces.ExternalVideoInterface` per camera.

    ``DANNCEInterface`` on its own can link each camera's source video via the ``source_videos``
    argument of its ``add_to_nwbfile``, but doing so safely requires the video ``ImageSeries`` to
    already be written to the ``NWBFile`` first, and then looked up by name to pass the live
    objects through -- easy to get wrong (write order, name matching) when wiring up interfaces
    by hand in an ``NWBConverter``. This converter does that wiring internally, so a user combining
    DANNCE with source videos does not need to reimplement it.
    """

    display_name = "DANNCE with source videos"
    keywords = ("DANNCE", "sDANNCE", "social DANNCE", "3D pose estimation", "behavior", "pose estimation", "video")
    associated_suffixes = (".mat", ".mp4")
    info = (
        "Converter for DANNCE and social DANNCE (sDANNCE) 3D pose estimation output data, combined with each "
        "camera's source video."
    )

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        video_file_paths: dict[str, list[FilePath]],
        *,
        frametimes_file_path: FilePath | None = None,
        sampling_rate: float | None = None,
        landmark_names: list[str] | None = None,
        subject_name: str = "ind1",
        metadata_key: str | None = None,
        calibration_path: Path | None = None,
        animal_index: int | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the DANNCE prediction .mat file (e.g., save_data_AVG.mat or save_data_MAX.mat).
        video_file_paths : dict of str to list of FilePath
            One entry per camera, keyed by camera name (e.g. ``{"Camera1": ["cam1_part1.mp4", ...], "Camera2":
            [...]}``). Each value is passed as the ``file_paths`` of one ``ExternalVideoInterface``. The camera
            names are used directly as ``DANNCEInterface``'s ``camera_names``, so they must match the naming used
            by ``calibration_path``, if provided (see :meth:`DANNCEInterface.get_camera_calibrations`).
        frametimes_file_path : FilePath, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        sampling_rate : float, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`. Ignored if ``frametimes_file_path`` is provided.
        landmark_names : list of str, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        subject_name : str, default: "ind1"
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        metadata_key : str, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        calibration_path : str or Path, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`. Only used to load per-camera calibrations
            (intrinsics/extrinsics); the set of cameras itself is always taken from ``video_file_paths``.
        animal_index : int, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        verbose : bool, default: False
            Controls verbosity of the conversion process.
        """
        self.verbose = verbose
        self._camera_names = list(video_file_paths.keys())

        self._dannce_interface = DANNCEInterface(
            file_path=file_path,
            frametimes_file_path=frametimes_file_path,
            sampling_rate=sampling_rate,
            landmark_names=landmark_names,
            subject_name=subject_name,
            metadata_key=metadata_key,
            camera_names=self._camera_names,
            calibration_path=calibration_path,
            animal_index=animal_index,
            verbose=verbose,
        )
        self._video_interfaces: dict[str, ExternalVideoInterface] = {
            camera_name: ExternalVideoInterface(
                file_paths=file_paths,
                metadata_key=f"video_{camera_name}",
                video_name=f"Video{camera_name}",
                verbose=verbose,
            )
            for camera_name, file_paths in video_file_paths.items()
        }

        self.data_interface_objects: dict[str, BaseDataInterface] = {
            "DANNCE": self._dannce_interface,
            **{f"Video{camera_name}": interface for camera_name, interface in self._video_interfaces.items()},
        }

    def get_metadata(self) -> DeepDict:
        metadata = self._dannce_interface.get_metadata()
        for camera_name in self._camera_names:
            video_interface = self._video_interfaces[camera_name]
            video_metadata = video_interface.get_metadata()
            # Point the video at the same camera Device DANNCE already registered (under `camera_name`
            # in `metadata["Devices"]`), dropping the video interface's own default device entry (see
            # ExternalVideoInterface.__init__: `f"{metadata_key}_camera"`), so the two interfaces share
            # one Device (e.g. a calibrated one) instead of each creating their own -- see the matching
            # `create_camera_devices` call in `add_to_nwbfile`.
            video_metadata["Devices"].pop(f"{video_interface.metadata_key}_camera", None)
            video_metadata["Behavior"]["ExternalVideos"][video_interface.metadata_key].update(
                description=f"Source video recorded by camera '{camera_name}'.",
                device_metadata_key=camera_name,
            )
            metadata = dict_deep_update(metadata, video_metadata)
        return metadata

    def get_conversion_options_schema(self) -> dict:
        # `camera_calibrations` carries live `numpy.ndarray` values, not JSON-serializable values, so it
        # cannot be represented in a JSON schema and must be excluded (unlike `nwbfile`/`metadata`, which
        # the base implementation already excludes).
        from ....utils import get_json_schema_from_method_signature

        return get_json_schema_from_method_signature(self.add_to_nwbfile, exclude=["nwbfile", "metadata", "camera_calibrations"])

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *,
        stub_test: bool = False,
        camera_calibrations: dict[str, dict] | None = None,
        starting_frames: dict[str, list[int]] | None = None,
    ) -> None:
        """
        Add each camera's source video and the DANNCE pose estimation data to an NWB file, linking the two.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the data to.
        metadata : dict
            Metadata dictionary. If provided, overrides default metadata from ``get_metadata()``.
        stub_test : bool, default: False
            If True, write only the first 100 frames of the DANNCE pose estimation data for quick smoke testing.
            Video data is always written in full.
        camera_calibrations : dict of str to dict, optional
            Per-camera calibration overrides; see ``DANNCEInterface.add_to_nwbfile``. Merged on top of any
            calibrations already loaded from ``calibration_path`` at construction.
        starting_frames : dict of str to list of int, optional
            Per-camera list of start frames for videos written using external mode, keyed by camera name.
            Required for a given camera only if more than one video path was given for it.
        """
        metadata_copy = deepcopy(metadata)

        # Pre-create each camera's Device (calibrated, if calibration data is available) before
        # writing the videos, so that when each ExternalVideoInterface resolves its device_metadata_key
        # (pointed at the same camera_name entry by get_metadata, above), it reuses this Device instead
        # of creating its own -- Device creation is idempotent on name.
        self._dannce_interface.create_camera_devices(
            nwbfile=nwbfile, metadata=metadata_copy, camera_calibrations=camera_calibrations
        )

        source_videos = {}
        for camera_name in self._camera_names:
            video_interface = self._video_interfaces[camera_name]
            video_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata_copy,
                starting_frames=(starting_frames or {}).get(camera_name),
            )
            image_series_name = metadata_copy["Behavior"]["ExternalVideos"][video_interface.metadata_key]["name"]
            source_videos[camera_name] = nwbfile.acquisition[image_series_name]

        self._dannce_interface.add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata_copy,
            stub_test=stub_test,
            source_videos=source_videos,
            camera_calibrations=camera_calibrations,
        )
