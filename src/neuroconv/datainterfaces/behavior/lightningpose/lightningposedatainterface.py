import re
import warnings
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ..baseposeestimationinterface import BasePoseEstimationInterface
from ....tools.pose_estimation import _add_pose_estimation_to_nwbfile
from ....utils import (
    DeepDict,
    get_base_schema,
)


class LightningPoseDataInterface(BasePoseEstimationInterface):
    """Data interface for Lightning Pose datasets."""

    display_name = "Lightning Pose"
    keywords = ("pose estimation", "video")
    associated_suffixes = (".csv", ".mp4")
    info = "Interface for handling a single stream of lightning pose data."

    def get_metadata_schema(self, *, use_new_metadata_format: bool = True) -> dict:
        """
        Retrieve JSON schema for metadata specific to the LightningPoseDataInterface.

        Returns
        -------
        dict
            The JSON schema defining the metadata structure.
        """
        # Canonical (dict-based) shape: top-level Devices and top-level Pose.* validate against the
        # base metadata schema, which permits these additional registries. The legacy
        # ``metadata["Behavior"]["PoseEstimation"]`` schema is selected while ``use_new_metadata_format``
        # is False.
        if not use_new_metadata_format:
            return self._get_metadata_schema_old_format()
        return super().get_metadata_schema()

    def _get_metadata_schema_old_format(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")

        metadata_schema["properties"]["Behavior"].update(
            required=["PoseEstimation"],
            properties=dict(
                PoseEstimation=dict(
                    type="object",
                    required=["name"],
                    properties=dict(
                        name=dict(type="string", default="PoseEstimation"),
                        description=dict(type="string"),
                        scorer=dict(type="string"),
                        source_software=dict(type="string", default="LightningPose"),
                        camera_name=dict(type="string", default="CameraPoseEstimation"),
                    ),
                    patternProperties={
                        "^(?!(name|description|scorer|source_software|camera_name)$)[a-zA-Z0-9_]+$": dict(
                            title="PoseEstimationSeries",
                            type="object",
                            properties=dict(
                                name=dict(type="string"),
                                description=dict(type="string"),
                            ),
                            minProperties=1,
                            additionalProperties=False,
                        )
                    },
                    minProperties=2,
                    additionalProperties=False,
                )
            ),
        )

        return metadata_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        original_video_file_path: FilePath,
        labeled_video_file_path: FilePath | None = None,
        verbose: bool = False,
        metadata_key: str = "lightning_pose",
    ):
        """
        Interface for writing pose estimation data from the Lightning Pose algorithm.

        Parameters
        ----------
        file_path : FilePath
            Path to the .csv file that contains the predictions from Lightning Pose.
        original_video_file_path : FilePath
            Path to the original video file (.mp4).
        labeled_video_file_path : a string or a path, optional
            Path to the labeled video file (.mp4).
        verbose : bool, default: False
            controls verbosity. ``True`` by default.
        metadata_key : str, default: "lightning_pose"
            Key addressing this interface's entries in the dict-based metadata: the container under
            ``metadata["Pose"]["PoseEstimations"]``, the skeleton under ``metadata["Pose"]["Skeletons"]``
            and the camera under ``metadata["Devices"]``. It is an internal handle and never appears in
            the written file. Only used by the dict-based shape, reachable through
            ``get_metadata(use_new_metadata_format=True)``.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "original_video_file_path",
                "labeled_video_file_path",
                "verbose",
            ]
            num_positional_args_before_args = 1  # file_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to LightningPoseDataInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            original_video_file_path = positional_values.get("original_video_file_path", original_video_file_path)
            labeled_video_file_path = positional_values.get("labeled_video_file_path", labeled_video_file_path)
            verbose = positional_values.get("verbose", verbose)

        # This import is to assure that the ndx_pose is in the global namespace when an pynwb.io object is created
        # For more detail, see https://github.com/rly/ndx-pose/issues/36
        from importlib.metadata import version

        import ndx_pose  # noqa: F401
        from packaging import version as version_parse

        ndx_pose_version = version("ndx-pose")
        if version_parse.parse(ndx_pose_version) < version_parse.parse("0.2.0"):
            raise ImportError(
                "LightningPose interface requires ndx-pose version 0.2.0 or later. "
                f"Found version {ndx_pose_version}. Please upgrade: "
                "pip install 'ndx-pose>=0.2.0'"
            )

        from neuroconv.datainterfaces.behavior.video.video_utils import (
            VideoCaptureContext,
        )

        self._vc = VideoCaptureContext

        self.file_path = Path(file_path)
        assert self.file_path.exists(), f"The file '{self.file_path}' does not exist."
        self.original_video_file_path = Path(original_video_file_path)
        assert (
            self.original_video_file_path.exists()
        ), f"The original video file '{self.original_video_file_path}' does not exist."

        super().__init__(
            verbose,
            file_path=file_path,
            original_video_file_path=original_video_file_path,
            labeled_video_file_path=labeled_video_file_path,
        )

        self.metadata_key = metadata_key

        # dimension is width by height
        self.dimension = self._get_original_video_shape()

        pose_estimation_data = self._load_source_data()
        _, self.scorer_name = pose_estimation_data.columns.get_level_values(0).drop_duplicates()
        self.pose_estimation_data = pose_estimation_data[self.scorer_name]
        self.keypoint_names = self.pose_estimation_data.columns.get_level_values(0).drop_duplicates().tolist()

        self._times = None

    def _load_source_data(self):
        import pandas as pd

        # The order of the header is "scorer", "bodyparts", "coords"
        pose_estimation_data = pd.read_csv(self.file_path, header=[0, 1, 2])
        return pose_estimation_data

    def _get_original_video_shape(self) -> tuple[int, int]:
        with self._vc(file_path=str(self.original_video_file_path)) as video:
            video_shape = video.get_frame_shape()
        # image size of the original video is in height x width
        return video_shape[0], video_shape[1]

    def get_original_timestamps(self, stub_test: bool = False) -> np.ndarray:
        max_frames = 10 if stub_test else None
        with self._vc(file_path=str(self.original_video_file_path)) as video:
            timestamps = video.get_video_timestamps(max_frames=max_frames)
        return timestamps

    def get_timestamps(self, stub_test: bool = False) -> np.ndarray:
        max_frames = 10 if stub_test else None
        if self._times is None:
            return self.get_original_timestamps(stub_test=stub_test)

        timestamps = self._times if not stub_test else self._times[:max_frames]
        return timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        self._times = aligned_timestamps

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        # TODO: remove the branch and _get_legacy_metadata with the legacy shape.
        if not use_new_metadata_format:
            return self._get_legacy_metadata()

        metadata = super().get_metadata()
        self._add_session_start_time(metadata=metadata)

        labeled_video_file_path = self.source_data["labeled_video_file_path"]
        metadata["Pose"]["Skeletons"][self.metadata_key].update(
            # Lightning Pose predicts each keypoint independently, so the source carries no edges.
            nodes=[keypoint_name.replace(" ", "") for keypoint_name in self.keypoint_names],
            edges=[],
        )
        metadata["Pose"]["PoseEstimations"][self.metadata_key].update(
            source_software="LightningPose",
            scorer=self.scorer_name,
            dimensions=[list(self.dimension)],
            original_videos=[str(self.original_video_file_path)],
            labeled_videos=[str(labeled_video_file_path)] if labeled_video_file_path else None,
            PoseEstimationSeries={
                keypoint_name: {
                    "name": f"PoseEstimationSeries{keypoint_name.replace(' ', '')}",
                    "reference_frame": (
                        "(0,0) is the top-left pixel of the video frame, with x increasing to the right "
                        "and y increasing downward."
                    ),
                }
                for keypoint_name in self.keypoint_names
            },
        )

        return metadata

    def _add_session_start_time(self, metadata: DeepDict) -> None:
        """Take the session start time from the folder structure when it is saved as YYYY-MM-DD/HH-MM-SS."""
        pattern = r"(?P<date_time>\d{4}-\d{2}-\d{2}/\d{2}-\d{2}-\d{2})"
        file_path = "/".join(self.file_path.parts)
        match = re.search(pattern, file_path)
        if match and "session_start_time" not in metadata["NWBFile"]:
            session_start_time = datetime.strptime(match.group("date_time"), "%Y-%m-%d/%H-%M-%S")
            metadata["NWBFile"].update(session_start_time=session_start_time)

    # TODO: remove with the legacy metadata["Behavior"]["PoseEstimation"] block.
    def _get_legacy_metadata(self) -> DeepDict:
        """The container, the camera and every series flattened into one ``Behavior/PoseEstimation`` block.

        Built from ``_get_base_metadata`` rather than from ``get_metadata`` so it never carries the
        dict-based registries: ``add_to_nwbfile`` dispatches on a top-level "Pose" block being present.
        """
        metadata = self._get_base_metadata()
        self._add_session_start_time(metadata=metadata)

        metadata["Behavior"]["PoseEstimation"].update(
            name="PoseEstimation",
            description="Contains the pose estimation series for each keypoint.",
            scorer=self.scorer_name,
            source_software="LightningPose",
            camera_name="CameraPoseEstimation",
        )
        for keypoint_name in self.keypoint_names:
            keypoint_name_without_spaces = keypoint_name.replace(" ", "")
            metadata["Behavior"]["PoseEstimation"].update(
                {
                    keypoint_name: dict(
                        name=f"PoseEstimationSeries{keypoint_name_without_spaces}",
                        description=f"The estimated position (x, y) of {keypoint_name} over time.",
                    )
                }
            )

        return metadata

    def _get_keypoint_names(self) -> list[str]:
        return self.keypoint_names

    def _get_keypoint_data(self) -> dict[str, tuple[np.ndarray, np.ndarray | None]]:
        # Explicitly convert to numpy for HDMF compatibility with pandas 3.0+
        # See https://github.com/hdmf-dev/hdmf/issues/1384
        return {
            keypoint_name: (
                self.pose_estimation_data[keypoint_name][["x", "y"]].to_numpy(dtype="float64"),
                self.pose_estimation_data[keypoint_name]["likelihood"].to_numpy(dtype="float64"),
            )
            for keypoint_name in self.keypoint_names
        }

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        reference_frame: str | None = None,
        confidence_definition: str | None = None,
        stub_test: bool | None = False,
    ) -> None:
        """
        Add the pose estimation data to the nwbfile.

        Parameters
        ----------
        nwbfile : NWBFile
            The nwbfile to which the pose estimation data is added.
        metadata : dict, optional
            The metadata for the pose estimation data. A metadata carrying a top-level ``"Pose"``
            block is read in the dict-based shape; anything else is read in the legacy
            ``metadata["Behavior"]["PoseEstimation"]`` shape.
        reference_frame : str, optional
            Deprecated. The description defining what the (0, 0) coordinate corresponds to. Set it per
            series in ``metadata["Pose"]["PoseEstimations"][metadata_key]["PoseEstimationSeries"]``
            instead.
        confidence_definition : str, optional
            Deprecated. The description of how the confidence was computed, e.g., 'Softmax output of the
            deep neural network'. Set it per series in
            ``metadata["Pose"]["PoseEstimations"][metadata_key]["PoseEstimationSeries"]`` instead.
        stub_test : bool, default: False
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "reference_frame",
                "confidence_definition",
                "stub_test",
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
                f"Passing arguments positionally to LightningPoseDataInterface.add_to_nwbfile() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            reference_frame = positional_values.get("reference_frame", reference_frame)
            confidence_definition = positional_values.get("confidence_definition", confidence_definition)
            stub_test = positional_values.get("stub_test", stub_test)

        # Dispatch on the legacy block being there rather than on the dict-based one being absent, since
        # metadata that mentions neither is not legacy, it is a caller who said nothing about pose. The
        # caller's metadata is passed on as they wrote it; only an absent one falls back to this
        # interface's own.
        # TODO: remove the branch with the legacy metadata["Behavior"]["PoseEstimation"] block.
        uses_legacy_metadata_format = metadata is not None and "PoseEstimation" in metadata.get("Behavior", {})
        describes_pose = metadata is not None and ("Pose" in metadata or uses_legacy_metadata_format)

        # Per block, not per field: a caller who wrote a pose block gets it as they wrote it, absent keys
        # and all, and a caller who wrote none gets this interface's own rather than an error.
        if not describes_pose:
            metadata_copy = self.get_metadata()
        elif uses_legacy_metadata_format:
            metadata_copy = self._translate_legacy_metadata(
                metadata=deepcopy(metadata), defaults=DeepDict(self.get_metadata(use_new_metadata_format=True))
            )
        else:
            metadata_copy = deepcopy(metadata)

        # These two are deprecated as conversion options: the dict-based shape carries them per
        # series, so the values are routed into every series entry rather than applied here.
        deprecated_options = {
            name: value
            for name, value in (
                ("reference_frame", reference_frame),
                ("confidence_definition", confidence_definition),
            )
            if value is not None
        }
        if deprecated_options:
            warnings.warn(
                f"The {list(deprecated_options)} conversion option(s) of "
                "LightningPoseDataInterface.add_to_nwbfile() are deprecated and will be removed on or after "
                "August 2027. Set them per series in "
                "metadata['Pose']['PoseEstimations'][metadata_key]['PoseEstimationSeries'] instead.",
                FutureWarning,
                stacklevel=2,
            )
            # Reached with ``.get`` and checked rather than indexed: ``metadata_copy`` is often a
            # ``DeepDict``, where indexing a key that addresses nothing creates it, which would leave the
            # writer's own check with an empty entry to find instead of a missing one.
            containers_metadata = metadata_copy.get("Pose", {}).get("PoseEstimations", {})
            if self.metadata_key not in containers_metadata:
                raise ValueError(
                    f"metadata_key '{self.metadata_key}' was not found in metadata['Pose']['PoseEstimations'] "
                    f"(available keys: {list(containers_metadata)})."
                )
            for series_entry in containers_metadata[self.metadata_key]["PoseEstimationSeries"].values():
                series_entry.update(deprecated_options)

        keypoint_data = self._get_keypoint_data()
        if stub_test:
            keypoint_data = {
                keypoint_name: (positions[:10], confidence[:10])
                for keypoint_name, (positions, confidence) in keypoint_data.items()
            }
        _add_pose_estimation_to_nwbfile(
            nwbfile=nwbfile,
            keypoint_data=keypoint_data,
            timestamps=self.get_timestamps(stub_test=stub_test),
            metadata=metadata_copy,
            metadata_key=self.metadata_key,
        )

    # TODO: remove with the legacy metadata["Behavior"]["PoseEstimation"] block.
    def _translate_legacy_metadata(self, metadata: dict, defaults: DeepDict) -> DeepDict:
        """Convert the legacy ``metadata["Behavior"]["PoseEstimation"]`` block into the dict-based shape.

        The legacy block is flat: the container's own fields and its series sit side by side, keyed by the
        keypoint name with the spaces removed, and it carries no skeleton, device, video or dimension
        entry of its own. Those come from the dict-based defaults, and the strings the legacy write path
        used to supply are written in here so the same file comes out of the one writer.
        """
        legacy_metadata = metadata["Behavior"]["PoseEstimation"]
        translated = defaults

        container_entry = translated["Pose"]["PoseEstimations"][self.metadata_key]
        for field in ("name", "scorer", "source_software"):
            if field in legacy_metadata:
                container_entry[field] = legacy_metadata[field]
        container_entry["description"] = legacy_metadata.get(
            "description", "Contains the pose estimation series for each keypoint."
        )
        # The legacy shape names a camera and the dict-based one does not, so the cross-reference is set
        # here rather than in get_metadata. It keeps the legacy write producing the device it always did,
        # and goes with the legacy shape.
        container_entry["device_metadata_key"] = self.metadata_key
        translated["Devices"][self.metadata_key] = {
            "name": legacy_metadata["camera_name"],
            "description": "Camera used for behavioral recording and pose estimation.",
        }
        translated["Pose"]["Skeletons"][self.metadata_key]["name"] = f"Skeleton{container_entry['name']}"

        for keypoint_name in self.keypoint_names:
            series_entry = container_entry["PoseEstimationSeries"][keypoint_name]
            series_entry.update(legacy_metadata[keypoint_name.replace(" ", "")])
            series_entry.setdefault("description", f"The estimated position (x, y) of {keypoint_name} over time.")
            series_entry.setdefault("reference_frame", "(0,0) is unknown.")
            series_entry.setdefault("unit", "px")

        # The converter passes the names of the ImageSeries it wrote through Behavior/Videos; without it
        # the videos are referenced by their source path, which is what the defaults already hold.
        videos_metadata = metadata["Behavior"].get("Videos")
        if videos_metadata:
            container_entry["original_videos"] = [videos_metadata[0]["name"]]
            if self.source_data["labeled_video_file_path"]:
                container_entry["labeled_videos"] = [videos_metadata[1]["name"]]

        return translated
