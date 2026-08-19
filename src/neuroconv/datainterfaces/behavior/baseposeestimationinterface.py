from abc import abstractmethod

import numpy as np
from pynwb.file import NWBFile

from ...basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ...tools.pose_estimation import _add_pose_estimation_to_nwbfile
from ...utils import DeepDict

__all__ = ["BasePoseEstimationInterface"]


class BasePoseEstimationInterface(BaseTemporalAlignmentInterface):
    """Base class for interfaces writing a single ``ndx-pose`` ``PoseEstimation`` container."""

    keywords = ("behavior", "pose estimation")

    @abstractmethod
    def get_keypoint_names(self) -> list[str]:
        """Return the keypoint names, in the order their series are written."""
        raise NotImplementedError

    @abstractmethod
    def _get_keypoint_data(self) -> dict[str, tuple[np.ndarray, np.ndarray | None]]:
        """Return ``{keypoint name: (positions, confidence)}``.

        Positions are ``(num_frames, 2)`` or ``(num_frames, 3)``; confidence is ``(num_frames,)`` or
        ``None`` when the format does not record it.
        """
        raise NotImplementedError

    def _get_base_metadata(self) -> DeepDict:
        """The metadata without the pose registries on top.

        The seam an interface still offering the legacy shape needs: it produces one shape or the other
        and must not build both, since ``add_to_nwbfile`` dispatches on a top-level ``"Pose"`` block being
        present. It goes when the legacy shapes go.
        """
        return super().get_metadata()

    def get_metadata(self) -> DeepDict:
        """Build the pose registries and their cross-references, with generic names and no free text.

        An interface overrides this, calls it, and sets what its own format records. Nothing is invented
        here: no descriptions, no units, no reference frames, and no scorer, dimensions or video paths.
        """
        metadata = self._get_base_metadata()
        metadata_key = self.metadata_key
        keypoint_names = self.get_keypoint_names()

        container_name = "PoseEstimation"
        metadata["Pose"]["Skeletons"] = {
            metadata_key: {"name": f"Skeleton{container_name}", "nodes": list(keypoint_names)}
        }
        metadata["Pose"]["PoseEstimations"] = {
            metadata_key: {
                "name": container_name,
                "skeleton_metadata_key": metadata_key,
                "PoseEstimationSeries": {
                    keypoint_name: {"name": f"PoseEstimationSeries{keypoint_name}"} for keypoint_name in keypoint_names
                },
            }
        }

        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, **conversion_options) -> None:
        """Write this interface's ``PoseEstimation`` container to the file's behavior module.

        The caller's metadata reaches the writer as they wrote it. It is not merged over this interface's
        defaults, so an absent optional cross-reference says "there is no such object" rather than "the
        user forgot one", and what a required field needs is filled where the object is built.
        """
        _add_pose_estimation_to_nwbfile(
            nwbfile=nwbfile,
            keypoint_data=self._get_keypoint_data(),
            timestamps=self.get_timestamps(),
            metadata=metadata if metadata is not None else self.get_metadata(),
            metadata_key=self.metadata_key,
        )
