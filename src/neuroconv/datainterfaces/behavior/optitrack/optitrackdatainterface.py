import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import FilePath, validate_call
from pynwb import TimeSeries
from pynwb.behavior import SpatialSeries
from pynwb.file import NWBFile

from .._pose_metadata_template import _get_skeleton_template_entry
from ..baseposeestimationinterface import BasePoseEstimationInterface
from ....tools.nwb_helpers import get_module
from ....tools.pose_estimation import _add_multi_camera_pose_estimation_to_nwbfile
from ....utils import DeepDict, calculate_regular_series_rate, to_camel_case, to_snake_case

# Rows 3 to 7 of a Motive CSV export, after the export settings line and a blank line
# (Motive docs, "CSV Header"). Format version 1.25 adds a `Parent` row after `ID`.
_MOTIVE_HEADER_LEVELS = ("marker_type", "label", "id", "measurement_type", "axis")
_MOTIVE_HEADER_LEVELS_WITH_PARENT = ("marker_type", "label", "id", "parent", "measurement_type", "axis")

_MOTIVE_CAPTURE_START_TIME_FORMATS = ("%Y-%m-%d %I.%M.%S.%f %p", "%Y-%m-%d %I.%M.%S %p")

# The asset types whose labeled points are written as pose estimation, grouped by the skeleton or marker set
# that owns them. `Rigid Body Marker` columns are not among them: they are where Motive's model puts each
# marker, computed from the rigid body's pose rather than measured.
_POSE_ASSET_TYPES = ("Bone", "Marker")

# The owner of labeled markers whose label names none, as in exports from Motive 2.
_UNOWNED_MARKERS_OWNER = "Markers"

# How many samples ``add_to_nwbfile(stub_test=True)`` writes.
_STUB_SAMPLES = 100


class OptiTrackInterface(BasePoseEstimationInterface):
    """Data interface for the rigid bodies, skeletons and marker sets in OptiTrack Motive CSV exports."""

    display_name = "OptiTrack"
    keywords = ("behavior", "pose estimation", "motion capture")
    associated_suffixes = (".csv",)
    info = "Interface for the rigid bodies, skeletons and marker sets exported to CSV by OptiTrack Motive."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .csv file exported by Motive."
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        verbose: bool = False,
        metadata_key: str | None = None,
    ):
        """
        Interface for writing the rigid bodies, skeletons and marker sets in an OptiTrack Motive CSV export to NWB.

        Each rigid body is one object with a position and an orientation. Its position is written to the
        behavior module as a ``SpatialSeries``, and its orientation as a ``TimeSeries``, Euler angles in
        degrees with columns x, y, z and the export's rotation order in the description, or a unit quaternion
        with columns w, x, y, z.

        The labeled points of each skeleton or marker set, the bones and the labeled markers named
        ``"{owner}:{point}"`` in the export, are written as one ``ndx-pose`` ``MultiCameraPoseEstimation``
        container, since Motive triangulates them in 3D from all of its cameras. A bone also has an orientation,
        which is written as a ``TimeSeries`` like a rigid body's. Unlabeled markers and the ``Rigid Body Marker``
        columns, which Motive computes from the rigid body's pose, are left out.

        Parameters
        ----------
        file_path : FilePath
            Path to the .csv file exported by Motive.
        verbose : bool, default: False
            Controls verbosity.

        metadata_key : str, optional
            Key addressing this interface's entries in the dict-based metadata. Defaults to
            ``"optitrack"`` when not provided.

        Metadata Structure
        ------------------
        One ``SpatialSeries`` and one ``TimeSeries`` per rigid body, keyed ``f"{metadata_key}_{label}"`` and
        ``f"{metadata_key}_{label}_orientation"`` in snake case, and one container and one skeleton per
        skeleton or marker set under the top-level ``metadata["Pose"]`` registries, keyed
        ``f"{metadata_key}_{owner}"`` in snake case. The orientation of each bone of a skeleton is a
        ``TimeSeries`` keyed ``f"{metadata_key}_{owner}_{bone}_orientation"``, with the same fields as a
        rigid body's. For an export in meters, with XYZ Euler angles, of a
        rigid body ``RigidBody`` and a marker set ``Head`` with two markers:

        .. code-block:: python

            metadata = {
                "NWBFile": {
                    # From `Capture Start Time` in the export settings, without a time zone
                    "session_start_time": datetime(2023, 2, 20, 10, 10, 13, 343000),
                },
                "SpatialSeries": {
                    "optitrack_rigid_body": {
                        "name": "PositionRigidBody",
                        "description": "Position (x, y, z) of Rigid Body 'RigidBody'.",
                        "unit": "meters",  # from `Length Units` in the export settings
                    },
                },
                "TimeSeries": {
                    "optitrack_rigid_body_orientation": {
                        "name": "OrientationRigidBody",
                        "description": "Orientation of Rigid Body 'RigidBody' as Euler angles in degrees (x, y, z) ...",
                        "unit": "degrees",
                    },
                },
                "Pose": {
                    "Skeletons": {
                        "optitrack_head": {
                            "name": "SkeletonHead",
                            "nodes": ["Left", "Right"],  # one per labeled point, named as in Motive
                            "edges": [],
                        },
                    },
                    "MultiCameraPoseEstimations": {
                        "optitrack_head": {
                            "name": "PoseEstimationHead",
                            "source_software": "Motive",
                            "skeleton_metadata_key": "optitrack_head",  # -> Pose.Skeletons
                            "PoseEstimationSeries": {
                                "Left": {  # keyed by the point's name in Motive, without its owner
                                    "name": "PoseEstimationSeriesLeft",
                                    "description": "Position (x, y, z) of Marker 'Head:Left'.",
                                    "unit": "meters",
                                },
                                "Right": {...},
                            },
                        },
                    },
                },
            }

        The keys are internal handles and never appear in the NWB file; rename the written objects through
        their ``name`` fields. Delete an entry from ``metadata["SpatialSeries"]``, ``metadata["TimeSeries"]``
        or ``metadata["Pose"]["MultiCameraPoseEstimations"]`` to leave that object out of the file.
        :meth:`get_metadata_template` returns the same structure with the fields the export does not record
        marked as blanks.
        """
        # This import is to assure that the ndx_pose is in the global namespace when an pynwb.io object is created
        # For more detail, see https://github.com/rly/ndx-pose/issues/36
        import ndx_pose  # noqa: F401

        self.file_path = Path(file_path)
        self._header = self._read_header()

        self.metadata_key = metadata_key or "optitrack"
        self._motion_capture_data = None
        self._rigid_bodies = None
        self._labeled_points = None
        self._bone_orientations = None

        super().__init__(verbose=verbose, file_path=file_path)

    def _read_header(self) -> dict[str, str]:
        """Read the header line from a Motive CSV export.

        The first row of the file contains general information about the export, including the format version of the CSV
        export, name of the Take file, the captured frame rate, export frame rate, capture start time, capture start frame,
        number of total frames, total exported frames, rotation type, length units, and coordinate space type.

        When the header is disabled during export, this information is excluded from the CSV files. Instead, the file
        will have frame IDs in the first column, time data on the second column, and the corresponding motion capture
        data in the remaining columns.
        """
        first_line = (
            pd.read_csv(self.file_path, nrows=1, header=None, dtype=str, keep_default_na=False).iloc[0].tolist()
        )
        if first_line[0] == "comment":
            raise ValueError(
                f"'{self.file_path}' is in the row-typed layout of early Motive and Arena exports (one row per asset "
                "per frame, introduced by 'comment' rows), which is not supported yet. Export the take again from a "
                "current Motive version."
            )
        if "Format Version" not in first_line:
            raise ValueError(
                f"'{self.file_path}' does not start with the header information ('Format Version, ...'), it is either"
                f" not a Motive CSV export or it was exported with 'Header information' turned off. "
                f"Export the take again from Motive with 'Header information' enabled."
            )
        header = dict(zip(first_line[0::2], first_line[1::2]))

        return header

    def _read_motion_capture_data(self) -> pd.DataFrame:
        """Read the data from a Motive CSV export.

        The second row of the file is blank, and the next five rows contain the asset header, which has five rows of information for each
        asset in the export. The five rows are: ``Type``, ``Name``, ``ID``, measurement_type, and axis. The measurement_type row
        contains the type of measurement_type for each column (e.g., position, rotation, marker), and the axis row begins with
        ``Frame``and contains the axis for each column (e.g., X, Y, Z). Format version 1.25 adds a sixth row, ``Parent``,
        after ``ID``.
        """
        if self._motion_capture_data is not None:
            return self._motion_capture_data

        with open(self.file_path, encoding="utf-8") as file:
            next(file)  # the export settings line
            num_header_rows = 0
            for line in file:
                if line.strip():
                    num_header_rows += 1
                if line.startswith("Frame,"):
                    break
        header_levels = (
            _MOTIVE_HEADER_LEVELS_WITH_PARENT
            if num_header_rows == len(_MOTIVE_HEADER_LEVELS_WITH_PARENT)
            else _MOTIVE_HEADER_LEVELS
        )
        self._motion_capture_data = pd.read_csv(
            self.file_path, skiprows=1, header=list(range(len(header_levels))), index_col=[0, 1]
        )
        self._motion_capture_data.columns.names = header_levels
        self._motion_capture_data.index.names = ["frame", "time"]
        return self._motion_capture_data

    def _get_assets(self) -> dict[tuple[str, str], dict[str, dict[str, np.ndarray]]]:
        """Every column of the export, as ``{(marker_type, label): {measurement_type: {axis: values}}}``, in file order.

        For example ``assets[("Rigid Body", "RigidBody")]["Position"]["X"]``.
        """
        motion_capture_data = self._read_motion_capture_data()
        assets = {}
        for column, values in motion_capture_data.items():
            levels = dict(zip(motion_capture_data.columns.names, column))
            asset = assets.setdefault((levels["marker_type"], levels["label"]), {})
            asset.setdefault(levels["measurement_type"], {})[levels["axis"]] = values.to_numpy(dtype=np.float64)
        return assets

    def _read_tracked_assets(self) -> None:
        """Sort the assets that were tracked into rigid bodies and labeled points, in file order.

        Fills ``self._rigid_bodies``, ``{label: {"position": (num_frames, 3) array, "orientation": {axis:
        values} or None}}``, ``self._labeled_points``, ``{owner: {point: (asset_type, (num_frames, 3)
        array)}}``, and ``self._bone_orientations``, ``{owner: {bone: {axis: values}}}``. A frame where an
        asset was not tracked, empty or at the origin, is ``np.nan``; assets never tracked in any frame are
        left out with a warning.
        """
        rigid_bodies = {}
        labeled_points = {}
        bone_orientations = {}
        never_tracked = []
        for (asset_type, label), measurements in self._get_assets().items():
            if asset_type == "Bone" and self._header.get("Coordinate Space") == "Local":
                raise ValueError(
                    f"'{self.file_path}' was exported with local coordinates, where each bone's position and "
                    "rotation are relative to its parent bone, which is not supported. Export the take again from "
                    "Motive with global coordinates."
                )
            is_rigid_body = asset_type == "Rigid Body"
            is_labeled_point = asset_type in _POSE_ASSET_TYPES and not label.startswith("Unlabeled")
            if not (is_rigid_body or is_labeled_point) or "Position" not in measurements:
                continue
            position = measurements["Position"]
            positions = np.column_stack([position["X"], position["Y"], position["Z"]])

            # In a frame where an asset was not tracked, Motive leaves its cells empty. In one export in the test
            # data (zeros_instead_of_blanks), a rigid body holds position 0,0,0 in the frames before it was first
            # tracked instead. A position exactly at the origin is treated as untracked.
            is_untracked = (positions == 0.0).all(axis=1)
            positions[is_untracked] = np.nan
            is_untracked |= np.isnan(positions).all(axis=1)

            if is_untracked.all():
                never_tracked.append(f"{asset_type} '{label}'")
                continue

            rotation = measurements.get("Rotation")
            orientation = None if rotation is None else _get_orientation(rotation=rotation, is_untracked=is_untracked)
            if is_rigid_body:
                rigid_bodies[label] = dict(position=positions, orientation=orientation)
                continue

            owner, _, point = label.rpartition(":")
            owner = owner or _UNOWNED_MARKERS_OWNER
            points = labeled_points.setdefault(owner, {})
            if point in points:
                raise ValueError(
                    f"'{label}' in '{self.file_path}' is both a {points[point][0]} and a {asset_type}, so the two "
                    "cannot be told apart as nodes of one skeleton."
                )
            points[point] = (asset_type, positions)
            # Bones have a rotation; markers have none.
            if orientation is not None:
                bone_orientations.setdefault(owner, {})[point] = orientation

        if never_tracked:
            warnings.warn(
                f"Not tracked in any frame of '{self.file_path}', so not written: {', '.join(never_tracked)}.",
                UserWarning,
                stacklevel=3,
            )
        if not rigid_bodies and not labeled_points:
            raise ValueError(f"No asset in '{self.file_path}' was tracked in any frame, so there is nothing to write.")
        self._rigid_bodies = rigid_bodies
        self._labeled_points = labeled_points
        self._bone_orientations = bone_orientations

    def _get_rigid_bodies(self) -> dict[str, dict]:
        """The position and orientation of every rigid body, ``{label: {"position": ..., "orientation": ...}}``."""
        if self._rigid_bodies is None:
            self._read_tracked_assets()
        return self._rigid_bodies

    def _get_labeled_points(self) -> dict[str, dict[str, tuple[str, np.ndarray]]]:
        """The labeled points of every skeleton and marker set, ``{owner: {point: (asset_type, positions)}}``."""
        if self._labeled_points is None:
            self._read_tracked_assets()
        return self._labeled_points

    def _get_bone_orientations(self) -> dict[str, dict[str, dict[str, np.ndarray]]]:
        """The orientation of every bone of every skeleton, ``{owner: {bone: {axis: values}}}``."""
        if self._labeled_points is None:
            self._read_tracked_assets()
        return self._bone_orientations

    def get_original_timestamps(self) -> np.ndarray:
        """The time of each frame, ``Frame / Export Frame Rate``, in seconds from the start of the take.

        The export also has a ``Time (Seconds)`` column. The choice between the two is empirical: across the
        exports we compared they agree, except in Motive 3.0 exports that round ``Time`` to whole milliseconds,
        where the ``Frame / Export Frame Rate`` is the more precise of the two.
        """
        frames = self._read_motion_capture_data().index.get_level_values("frame").to_numpy(dtype=np.float64)
        return frames / float(self._header["Export Frame Rate"])

    def _get_rigid_body_metadata_key(self, label: str) -> str:
        """The key of one rigid body's position in ``metadata["SpatialSeries"]``, e.g. ``"optitrack_transmitter"``.

        Its orientation in ``metadata["TimeSeries"]`` is keyed the same, with ``"_orientation"`` appended.
        """
        return f"{self.metadata_key}_{to_snake_case(label)}"

    def _get_container_metadata_key(self, owner: str) -> str:
        """The key of one skeleton or marker set's container and skeleton, e.g. ``"optitrack_skeleton_001"``."""
        return f"{self.metadata_key}_{to_snake_case(owner)}"

    def _get_bone_orientation_metadata_key(self, owner: str, bone: str) -> str:
        """The key of one bone's orientation in ``metadata["TimeSeries"]``, e.g.
        ``"optitrack_skeleton_001_l_thigh_orientation"``."""
        return f"{self._get_container_metadata_key(owner)}_{to_snake_case(bone)}_orientation"

    def _get_orientation_metadata(self, name: str, asset: str) -> dict:
        """The ``metadata["TimeSeries"]`` entry for one orientation, in the export's rotation type."""
        rotation_type = self._header.get("Rotation Type")
        if rotation_type == "Quaternion":
            description = f"Orientation of {asset} as a unit quaternion, scalar first (w, x, y, z)."
            unit = "n.a."
        else:
            description = (
                f"Orientation of {asset} as Euler angles in degrees (x, y, z), applied in Motive's {rotation_type} "
                "rotation order."
            )
            unit = "degrees"
        return dict(name=name, description=description, unit=unit)

    def _get_keypoint_names(self, owner: str) -> list[str]:
        return list(self._get_labeled_points()[owner])

    def _get_keypoint_data(self, owner: str) -> dict[str, tuple[np.ndarray, np.ndarray | None]]:
        # Motive records no confidence for a position.
        return {point: (positions, None) for point, (_, positions) in self._get_labeled_points()[owner].items()}

    def _get_session_start_time(self) -> datetime | None:
        capture_start_time = self._header.get("Capture Start Time", "")
        if not capture_start_time:
            return None
        for time_format in _MOTIVE_CAPTURE_START_TIME_FORMATS:
            try:
                return datetime.strptime(capture_start_time, time_format)
            except ValueError:
                continue
        warnings.warn(
            f"Could not parse 'Capture Start Time' from the Motive export (got {capture_start_time!r}). "
            f"Expected one of the formats {_MOTIVE_CAPTURE_START_TIME_FORMATS}. Session start time will not be set "
            "automatically."
        )
        return None

    def get_metadata(self) -> DeepDict:
        """One position and orientation per rigid body, and one container and skeleton per skeleton or marker set."""
        metadata = self._get_base_metadata()

        session_start_time = self._get_session_start_time()
        if session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Exports before format version 1.2 do not record their length units.
        length_units = self._header.get("Length Units")
        unit = length_units.lower() if length_units else "n.a."

        for label, rigid_body in self._get_rigid_bodies().items():
            metadata_key = self._get_rigid_body_metadata_key(label)
            series_name = to_camel_case(to_snake_case(label))
            metadata["SpatialSeries"][metadata_key] = dict(
                name=f"Position{series_name}",
                description=f"Position (x, y, z) of Rigid Body '{label}'.",
                unit=unit,
            )

            if rigid_body["orientation"] is not None:
                metadata["TimeSeries"][f"{metadata_key}_orientation"] = self._get_orientation_metadata(
                    name=f"Orientation{series_name}", asset=f"Rigid Body '{label}'"
                )

        for owner, points in self._get_labeled_points().items():
            metadata_key = self._get_container_metadata_key(owner)
            owner_name = to_camel_case(to_snake_case(owner))

            series_metadata = {}
            for point, (asset_type, _) in points.items():
                label = point if owner == _UNOWNED_MARKERS_OWNER else f"{owner}:{point}"
                series_metadata[point] = dict(
                    name=f"PoseEstimationSeries{to_camel_case(to_snake_case(point))}",
                    description=f"Position (x, y, z) of {asset_type} '{label}'.",
                    unit=unit,
                )

            metadata["Pose"]["Skeletons"][metadata_key] = dict(
                name=f"Skeleton{owner_name}", nodes=list(points), edges=[]
            )
            metadata["Pose"]["MultiCameraPoseEstimations"][metadata_key] = dict(
                name=f"PoseEstimation{owner_name}",
                source_software="Motive",
                skeleton_metadata_key=metadata_key,
                PoseEstimationSeries=series_metadata,
            )

            for bone in self._get_bone_orientations().get(owner, {}):
                metadata["TimeSeries"][self._get_bone_orientation_metadata_key(owner, bone)] = (
                    self._get_orientation_metadata(
                        name=f"Orientation{owner_name}{to_camel_case(to_snake_case(bone))}",
                        asset=f"Bone '{owner}:{bone}'",
                    )
                )

        return metadata

    def get_metadata_template(self) -> DeepDict:
        """Return the containers and skeletons this interface can write, with the blanks marked.

        The multi-camera counterpart of :meth:`BasePoseEstimationInterface.get_metadata_template`: one
        ``MultiCameraPoseEstimation`` container and one skeleton per skeleton or marker set, each keyed
        ``f"{metadata_key}_{owner}"`` and already cross-referenced, plus the rigid bodies' series as
        :meth:`get_metadata` returns them. Fill in the blanks and pass the result to ``add_to_nwbfile`` or
        ``run_conversion``.

        The fields offered are the ones a motion capture export can be described by. There is no
        ``confidence_definition``, since Motive records no confidence for a position, and no cameras: a
        ``MultiCameraPoseEstimation`` links its cameras through per-camera ``PoseEstimation`` children,
        and the export records nothing per camera to fill them with. Any field left blank is skipped
        rather than written.
        """
        skeleton_entries = {}
        container_entries = {}
        for owner in self._get_labeled_points():
            metadata_key = self._get_container_metadata_key(owner)
            keypoint_names = self._get_keypoint_names(owner)
            skeleton_entries[metadata_key] = _get_skeleton_template_entry(keypoint_names=keypoint_names)
            container_entries[metadata_key] = dict(
                name=None,
                description=None,
                source_software=None,
                source_software_version=None,
                skeleton_metadata_key=metadata_key,
                PoseEstimationSeries={
                    keypoint_name: dict(name=None, description=None, unit=None, reference_frame=None)
                    for keypoint_name in keypoint_names
                },
            )

        template = DeepDict(dict(Pose=dict(Skeletons=skeleton_entries, MultiCameraPoseEstimations=container_entries)))

        # Whatever the source recorded wins over the template, as in the base class.
        template.deep_update(self.get_metadata())
        return template

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, *, stub_test: bool = False) -> None:
        """Write the rigid bodies' series, one ``MultiCameraPoseEstimation`` per skeleton or marker set, and
        the bones' orientations.

        Everything goes to the file's behavior module. The caller's metadata reaches the writer as they
        wrote it, as in the base class. An object whose entry is not in the metadata is not written, so
        deleting an entry is how to leave it out.
        """
        metadata = metadata if metadata is not None else self.get_metadata()

        end_frame = _STUB_SAMPLES if stub_test else None
        timestamps = self._get_timestamps()[:end_frame]

        containers_metadata = metadata.get("Pose", {}).get("MultiCameraPoseEstimations", {})
        for owner in self._get_labeled_points():
            container_metadata_key = self._get_container_metadata_key(owner)
            if container_metadata_key not in containers_metadata:
                continue
            keypoint_data = {
                name: (positions[:end_frame], confidence)
                for name, (positions, confidence) in self._get_keypoint_data(owner).items()
            }
            _add_multi_camera_pose_estimation_to_nwbfile(
                nwbfile=nwbfile,
                keypoint_data=keypoint_data,
                timestamps=timestamps,
                metadata=metadata,
                metadata_key=container_metadata_key,
            )

        rate = calculate_regular_series_rate(series=timestamps)
        timing = dict(rate=rate, starting_time=float(timestamps[0])) if rate else dict(timestamps=timestamps)
        spatial_series_metadata = metadata.get("SpatialSeries", {})
        time_series_metadata = metadata.get("TimeSeries", {})
        # Written directly to the behavior module without a `Position` container, following
        # NeurodataWithoutBorders/nwb-schema#616, as EthoVisionTrackInterface does.
        behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="processed behavioral data")
        for label, rigid_body in self._get_rigid_bodies().items():
            metadata_key = self._get_rigid_body_metadata_key(label)
            if metadata_key in spatial_series_metadata:
                position = rigid_body["position"][:end_frame]
                behavior_module.add(SpatialSeries(**spatial_series_metadata[metadata_key], data=position, **timing))

        orientations = {
            f"{self._get_rigid_body_metadata_key(label)}_orientation": rigid_body["orientation"]
            for label, rigid_body in self._get_rigid_bodies().items()
            if rigid_body["orientation"] is not None
        }
        for owner, bones in self._get_bone_orientations().items():
            for bone, orientation in bones.items():
                orientations[self._get_bone_orientation_metadata_key(owner, bone)] = orientation
        for orientation_metadata_key, orientation in orientations.items():
            if orientation_metadata_key not in time_series_metadata:
                continue
            data = np.column_stack(list(orientation.values()))[:end_frame]
            behavior_module.add(TimeSeries(**time_series_metadata[orientation_metadata_key], data=data, **timing))


def _get_orientation(*, rotation: dict[str, np.ndarray], is_untracked: np.ndarray) -> dict[str, np.ndarray]:
    """One asset's rotation columns, ``{axis: values}``, in the order they are written.

    Quaternions are written scalar first (W, X, Y, Z), as in MiniscopeHeadOrientationInterface. Euler angles are
    written X, Y, Z whatever the rotation order, which Motive also uses as the column order; the rotation order
    goes in the description. A frame without a position holds no pose, so the orientation is untracked there too.
    """
    axes = ("W", "X", "Y", "Z") if "W" in rotation else ("X", "Y", "Z")
    return {axis: np.where(is_untracked, np.nan, rotation[axis]) for axis in axes}
