import warnings
from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from .._pose_metadata_template import _get_skeleton_template_entry
from ..baseposeestimationinterface import BasePoseEstimationInterface
from ....tools.nwb_helpers._metadata_and_file_helpers import (
    _get_device_model_template_entry,
    _get_device_template_entry,
)
from ....tools.pose_estimation import _add_multi_camera_pose_estimation_to_nwbfile
from ....utils import DeepDict, to_camel_case, to_snake_case

_STUB_FRAMES = 100


class AniposeInterface(BasePoseEstimationInterface):
    """
    Data interface for the 3D pose that Anipose triangulates from several calibrated cameras.

    Anipose writes one pose-3d CSV per recording. Each keypoint is written as a 3D ``PoseEstimationSeries`` of
    an ``ndx_pose.MultiCameraPoseEstimation``, with its ``_score`` column as the confidence. The ``_error`` and
    ``_ncams`` columns have no field in ``ndx-pose`` and are not written. When the ``calibration.toml`` is given,
    each of its cameras is written as an ``ndx_pose.CalibratedCamera``, linked from the container through an
    empty per-camera ``PoseEstimation``.
    """

    display_name = "Anipose"
    keywords = BasePoseEstimationInterface.keywords + ("Anipose", "3D pose estimation", "triangulation")
    associated_suffixes = (".csv", ".toml")
    info = "Interface for the 3D pose that Anipose triangulates (pose-3d CSV and calibration.toml)."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        calibration_file_path: FilePath | None = None,
        sampling_rate: float | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """
        Interface for an Anipose pose-3d CSV and, optionally, its ``calibration.toml``.

        Parameters
        ----------
        file_path : FilePath
            Path to a CSV in ``pose-3d`` (written by ``anipose triangulate``) or ``pose-3d-filtered`` (written by
            ``anipose filter-3d``), one per recording.
        calibration_file_path : FilePath, optional
            Path to the ``calibration.toml`` the recording was triangulated with. Each of its cameras is written as
            an ``ndx_pose.CalibratedCamera``. Without it, no cameras are written.
        sampling_rate : float, optional
            The frame rate of the videos, in Hz. The CSV records frame indices (``fnum``) and no times, so each
            time is ``fnum / sampling_rate``. Without it, set the times with
            ``interface.temporal_alignment[interface.metadata_key].set_times(times)`` before writing.
        metadata_key : str, optional
            The key of this interface's entries in ``metadata["Pose"]["Skeletons"]`` and
            ``metadata["Pose"]["MultiCameraPoseEstimations"]``, and its temporal alignment key. Defaults to
            ``"anipose"``.
        verbose : bool, default: False
            Controls verbosity of the conversion process.
        """
        import ndx_pose  # noqa: F401

        from ._anipose_reader import _read_calibration, _read_pose_3d

        self.metadata_key = metadata_key or "anipose"
        self._sampling_rate = sampling_rate

        pose_3d = _read_pose_3d(Path(file_path))
        self._keypoint_names = pose_3d["keypoint_names"]
        self._frame_indices = pose_3d["frame_indices"]
        self._positions = pose_3d["positions"]
        self._scores = pose_3d["scores"]
        self._transform = pose_3d["transform"]
        self._cameras = _read_calibration(Path(calibration_file_path)) if calibration_file_path is not None else {}

        if sampling_rate is None:
            warnings.warn(
                "No timing information is available for this Anipose output: the pose-3d CSV records frame "
                "indices and no times. Pass 'sampling_rate', or call "
                "'interface.temporal_alignment[interface.metadata_key].set_times(times)' with one time per row "
                "before writing.",
                UserWarning,
                stacklevel=4,  # __init__, two validate_call frames, caller
            )

        super().__init__(
            file_path=file_path,
            calibration_file_path=calibration_file_path,
            sampling_rate=sampling_rate,
            metadata_key=self.metadata_key,
            verbose=verbose,
        )

    def _get_original_timestamps(self) -> np.ndarray:
        if self._sampling_rate is None:
            raise ValueError(
                "No timing information is available for this Anipose output. The pose-3d CSV records frame "
                "indices and no times. Pass 'sampling_rate' to AniposeInterface, or call "
                "'interface.temporal_alignment[interface.metadata_key].set_times(times)' with one time per row."
            )
        # From `fnum` and not the row number, since a CSV trimmed by its user keeps the frame indices of its rows.
        return self._frame_indices / self._sampling_rate

    def _get_keypoint_names(self) -> list[str]:
        return list(self._keypoint_names)

    def _get_keypoint_data(self) -> dict[str, tuple[np.ndarray, np.ndarray | None]]:
        return {
            keypoint_name: (self._positions[:, keypoint_index, :], self._scores[:, keypoint_index])
            for keypoint_index, keypoint_name in enumerate(self._keypoint_names)
        }

    def _get_camera_pose_estimation_metadata_key(self, camera_name: str) -> str:
        return f"{self.metadata_key}_{camera_name}_pose_estimation"

    def _get_reference_frame(self) -> str | None:
        """The frame of the points, from the transform the CSV records, or ``None`` for files without it."""
        if self._transform is None:
            return None
        matrix, center = self._transform
        if np.array_equal(matrix, np.eye(3)) and not center.any():
            return "The world frame of the camera calibration that Anipose triangulated with."
        return (
            "The world frame of the camera calibration that Anipose triangulated with, transformed by the axes set "
            f"in the Anipose config: each point is X @ M.T - center, where X is the point in the calibration frame, "
            f"M = {matrix.tolist()} and center = {center.tolist()}."
        )

    def get_metadata(self) -> DeepDict:
        """Build the calibrated cameras and the pose registries, in the shape ``DANNCEInterface`` uses.

        One ``metadata["Devices"]`` entry per camera of the calibration, keyed and named by the camera's ``name``,
        with ``type="CalibratedCamera"`` and its calibration fields. One per-camera entry without series in
        ``metadata["Pose"]["PoseEstimations"]`` linking each camera, and the container in
        ``metadata["Pose"]["MultiCameraPoseEstimations"]`` listing them.
        """
        metadata = self._get_base_metadata()
        metadata_key = self.metadata_key
        container_name = "PoseEstimationAnipose"

        pose_estimation_metadata_keys = []
        for camera_name, calibration in self._cameras.items():
            metadata["Devices"][camera_name] = dict(name=camera_name, type="CalibratedCamera", **calibration)
            camera_metadata_key = self._get_camera_pose_estimation_metadata_key(camera_name)
            metadata["Pose"]["PoseEstimations"][camera_metadata_key] = dict(
                name=f"{camera_name}PoseEstimation", device_metadata_key=camera_name
            )
            pose_estimation_metadata_keys.append(camera_metadata_key)

        metadata["Pose"]["Skeletons"][metadata_key] = dict(
            name=f"Skeleton{container_name}", nodes=list(self._keypoint_names)
        )

        reference_frame = self._get_reference_frame()
        series_metadata = {}
        for keypoint_name in self._keypoint_names:
            series_metadata[keypoint_name] = dict(
                name=f"PoseEstimationSeries{to_camel_case(to_snake_case(keypoint_name))}",
                confidence_definition=(
                    "The lowest 2D detection score among the cameras the point was triangulated from."
                ),
            )
            if reference_frame is not None:
                series_metadata[keypoint_name]["reference_frame"] = reference_frame

        container_entry = dict(
            name=container_name,
            source_software="Anipose",
            skeleton_metadata_key=metadata_key,
            PoseEstimationSeries=series_metadata,
        )
        if pose_estimation_metadata_keys:
            container_entry["pose_estimation_metadata_keys"] = pose_estimation_metadata_keys
        metadata["Pose"]["MultiCameraPoseEstimations"][metadata_key] = container_entry
        return metadata

    def get_metadata_template(self) -> DeepDict:
        """Return the container, skeleton, per-camera entries and cameras this interface can write, with the blanks
        marked, as :meth:`DANNCEInterface.get_metadata_template` does.

        Each series' ``description`` and ``reference_frame`` have to be filled, since ``ndx-pose`` requires both,
        and so does the ``unit``, which Anipose records nowhere: it is the length unit of the calibration board.
        """
        metadata_key = self.metadata_key
        device_model_metadata_key = "camera_model"

        camera_entries = {
            self._get_camera_pose_estimation_metadata_key(camera_name): dict(
                name=None, device_metadata_key=camera_name, source_video_metadata_key=None
            )
            for camera_name in self._cameras
        }
        series_template = {
            keypoint_name: dict(
                name=None, description=None, unit=None, reference_frame=None, confidence_definition=None
            )
            for keypoint_name in self._keypoint_names
        }
        template = DeepDict(
            dict(
                DeviceModels={device_model_metadata_key: _get_device_model_template_entry()},
                Devices={
                    camera_name: _get_device_template_entry(device_model_metadata_key=device_model_metadata_key)
                    for camera_name in self._cameras
                },
                Pose=dict(
                    Skeletons={metadata_key: _get_skeleton_template_entry(keypoint_names=self._keypoint_names)},
                    PoseEstimations=camera_entries,
                    MultiCameraPoseEstimations={
                        metadata_key: dict(
                            name=None,
                            description=None,
                            source_software=None,
                            source_software_version=None,
                            scorer=None,
                            skeleton_metadata_key=metadata_key,
                            pose_estimation_metadata_keys=list(camera_entries),
                            PoseEstimationSeries=series_template,
                        )
                    },
                ),
            )
        )

        # Whatever the source recorded wins over the template, as in the base class.
        template.deep_update(self.get_metadata())
        return template

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, *, stub_test: bool = False) -> None:
        """
        Add the Anipose keypoints, and the calibrated cameras, to an NWB file.

        The metadata given reaches the writer as written, not merged over this interface's defaults, as in
        :meth:`BasePoseEstimationInterface.add_to_nwbfile`.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the pose estimation data to.
        metadata : dict, optional
            Metadata dictionary. When ``None``, ``get_metadata()`` is used.
        stub_test : bool, default: False
            If True, write only the first 100 frames.
        """
        keypoint_data = self._get_keypoint_data()
        timestamps = self._get_timestamps()
        if stub_test:
            keypoint_data = {
                keypoint_name: (positions[:_STUB_FRAMES], confidence[:_STUB_FRAMES])
                for keypoint_name, (positions, confidence) in keypoint_data.items()
            }
            timestamps = timestamps[:_STUB_FRAMES]
        _add_multi_camera_pose_estimation_to_nwbfile(
            nwbfile=nwbfile,
            keypoint_data=keypoint_data,
            timestamps=timestamps,
            metadata=metadata if metadata is not None else self.get_metadata(),
            metadata_key=self.metadata_key,
        )
