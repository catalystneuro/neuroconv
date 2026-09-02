from abc import abstractmethod

import numpy as np
from pynwb.file import NWBFile

from ._pose_metadata_template import (
    _get_pose_estimation_template_entry,
    _get_skeleton_template_entry,
)
from ...basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ...tools.nwb_helpers._metadata_and_file_helpers import (
    _get_device_model_template_entry,
    _get_device_template_entry,
)
from ...tools.pose_estimation import _add_pose_estimation_to_nwbfile
from ...utils import DeepDict

__all__ = ["BasePoseEstimationInterface"]


class BasePoseEstimationInterface(BaseTemporalAlignmentInterface):
    """Base class for interfaces writing a single ``ndx-pose`` ``PoseEstimation`` container."""

    keywords = ("behavior", "pose estimation")

    @abstractmethod
    def _get_keypoint_names(self) -> list[str]:
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
        keypoint_names = self._get_keypoint_names()

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

    def get_metadata_template(self) -> DeepDict:
        """Return the container, skeleton and camera this interface can write, with the blanks marked.

        The counterpart to :meth:`get_metadata`, which reports only what the tracker recorded and so
        leaves a user no indication of what else the file could say. This returns those same values
        wrapped in the full structure the writer accepts. Fill in the blanks and pass the result to
        ``add_to_nwbfile`` or ``run_conversion``; an optional field left blank is skipped rather than
        written, and deleting an entry is how you get a file without that object.

        One container and one skeleton under this interface's ``metadata_key``, already
        cross-referenced, and one camera they hang off. What is blank is what only the experimenter can
        supply, which for a pose file is nearly everything: what the coordinates are measured from, what
        their unit is, what the confidence value means, and which body parts are connected.

        Rename the keys to suit the recording; they are handles, not names in the file.
        """
        metadata_key = self.metadata_key
        keypoint_names = self._get_keypoint_names()

        device_metadata_key = "camera"
        device_model_metadata_key = "camera_model"
        template = DeepDict(
            dict(
                DeviceModels={device_model_metadata_key: _get_device_model_template_entry()},
                Devices={
                    device_metadata_key: _get_device_template_entry(device_model_metadata_key=device_model_metadata_key)
                },
                Pose=dict(
                    Skeletons={metadata_key: _get_skeleton_template_entry(keypoint_names=keypoint_names)},
                    PoseEstimations={
                        metadata_key: _get_pose_estimation_template_entry(
                            keypoint_names=keypoint_names,
                            skeleton_metadata_key=metadata_key,
                            device_metadata_key=device_metadata_key,
                        )
                    },
                ),
            )
        )

        # The blanks are a floor rather than an override: whatever the source recorded wins over the
        # template, so a field the tracker was able to read is never handed back as one to fill in.
        template.deep_update(self.get_metadata())
        return template

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
