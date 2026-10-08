import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from .._pose_metadata_template import _get_pose_estimation_template_entry, _get_skeleton_template_entry
from ..baseposeestimationinterface import BasePoseEstimationInterface
from ....tools.nwb_helpers._metadata_and_file_helpers import (
    _get_device_model_template_entry,
    _get_device_template_entry,
)
from ....tools.pose_estimation import _add_pose_estimation_to_nwbfile
from ....utils import DeepDict, to_camel_case, to_snake_case

# Rows 3 to 7 of a Motive CSV export, after the export settings line and a blank line
# (Motive docs, "CSV Header").
_MOTIVE_HEADER_LEVELS = ("marker_type", "label", "id", "measurement_type", "axis")

_MOTIVE_CAPTURE_START_TIME_FORMATS = ("%Y-%m-%d %I.%M.%S.%f %p", "%Y-%m-%d %I.%M.%S %p")

# How many samples ``add_to_nwbfile(stub_test=True)`` writes.
_STUB_SAMPLES = 100


class OptiTrackInterface(BasePoseEstimationInterface):
    """Data interface for rigid body positions in OptiTrack Motive CSV exports."""

    display_name = "OptiTrack"
    keywords = ("behavior", "pose estimation", "motion capture")
    associated_suffixes = (".csv",)
    info = "Interface for rigid body positions exported to CSV by OptiTrack Motive."

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
        Interface for writing the positions in an OptiTrack Motive CSV export to NWB.

        Each marker type in the export (e.g. ``Rigid Body``) is written as one ``ndx-pose`` ``PoseEstimation``
        container, with one keypoint per marker. Its entry in the metadata is
        keyed ``f"{metadata_key}_{asset_type}"`` in snake case, for example ``"optitrack_rigid_body"``.

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
        One container and one skeleton per asset type in the export, under the top-level
        ``metadata["Pose"]`` registries, both keyed ``f"{metadata_key}_{asset_type}"`` in snake case. For an
        export with a single rigid body, ``RigidBody``, in meters and with no marker columns (a head-mounted
        rigid body on a mouse):

        .. code-block:: python

            metadata = {
                "NWBFile": {
                    # From `Capture Start Time` in the export settings, without a time zone
                    "session_start_time": datetime(2023, 2, 20, 10, 10, 13, 343000),
                },
                "Pose": {
                    "Skeletons": {
                        "optitrack_rigid_body": {
                            "name": "SkeletonPoseEstimationRigidBody",
                            "nodes": ["RigidBody"],  # one per asset, named as in Motive
                            "edges": [],
                        },
                    },
                    "PoseEstimations": {
                        "optitrack_rigid_body": {
                            "name": "PoseEstimationRigidBody",
                            "source_software": "Motive",
                            "source_software_version": "1.23",  # `Format Version` in the export settings
                            "skeleton_metadata_key": "optitrack_rigid_body",  # -> Pose.Skeletons
                            "PoseEstimationSeries": {
                                "RigidBody": {  # keyed by the asset name in Motive
                                    "name": "PoseEstimationSeriesRigidBody",
                                    "description": (
                                        "Position (x, y, z) of the center of rigid body 'RigidBody', as solved "
                                        "by OptiTrack Motive."
                                    ),
                                    "unit": "meters",  # from `Length Units` in the export settings
                                    "reference_frame": (
                                        "Motive's global coordinate system, whose origin is the ground plane set "
                                        "during calibration of the capture volume. The axis convention chosen at "
                                        "export is not recorded in the file."
                                    ),
                                },
                            },
                        },
                    },
                },
            }

        The keys are internal handles and never appear in the NWB file; rename the written objects through
        their ``name`` fields. Delete an entry from ``metadata["Pose"]["PoseEstimations"]`` to leave that
        container out of the file. :meth:`get_metadata_template` returns the same structure with the fields
        the export does not record, such as the camera device, marked as blanks.
        """
        # This import is to assure that the ndx_pose is in the global namespace when an pynwb.io object is created
        # For more detail, see https://github.com/rly/ndx-pose/issues/36
        import ndx_pose  # noqa: F401

        self.file_path = Path(file_path)
        self._header = self._read_header()

        self.metadata_key = metadata_key or "optitrack"
        self._positions = None

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
        ``Frame``and contains the axis for each column (e.g., X, Y, Z).
        """
        data = pd.read_csv(self.file_path, skiprows=1, header=list(range(len(_MOTIVE_HEADER_LEVELS))), index_col=[0, 1])
        data.columns.names = _MOTIVE_HEADER_LEVELS
        data.index.names = ["frame", "time"]
        return data

    def _get_positions(self) -> dict[str, dict[str, np.ndarray]]:
        if self._positions is not None:
            return self._positions
        data = self._read_motion_capture_data()
        measurements = data.xs(key="Position", axis=1, level="measurement_type").droplevel("id", axis=1)
        assets = dict.fromkeys(measurements.columns.droplevel("axis"))  # (type, name) pairs, in file order
        self._positions = {}
        for marker_type, label in assets:
            positions = measurements[(marker_type, label)][["X", "Y", "Z"]].to_numpy()
            self._positions.setdefault(marker_type, {})[label] = positions
        return self._positions

    def get_original_timestamps(self) -> np.ndarray:
        """The ``Time`` column of the export, in seconds from the start of the take."""
        times = self._read_motion_capture_data().index.get_level_values("time").to_numpy()
        return times

    def _get_container_metadata_key(self, asset_type: str) -> str:
        """The key of one asset type's container and skeleton, e.g. ``"optitrack_rigid_body"``."""
        return f"{self.metadata_key}_{to_snake_case(asset_type)}"

    def _get_keypoint_names(self, asset_type: str) -> list[str]:
        return list(self._get_positions()[asset_type])

    def _get_keypoint_data(self, asset_type: str) -> dict[str, tuple[np.ndarray, np.ndarray | None]]:
        # Motive records no confidence for a position.
        return {asset_name: (positions, None) for asset_name, positions in self._get_positions()[asset_type].items()}

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
        """One container and one skeleton per asset type, keyed ``f"{metadata_key}_{asset_type}"``."""
        metadata = self._get_base_metadata()

        session_start_time = self._get_session_start_time()
        if session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # TODO: not sure what this should be. The Motive CSV docs say global coordinates are relative to
        #  "the origin of the ground plane, set with a calibration square during the Calibration process".
        #  Local coordinates are relative to a parent bone.
        reference_frame = "(0,0,0) is unknown."
        unit = self._header.get("Length Units")

        for asset_type, positions in self._get_positions().items():
            container_metadata_key = self._get_container_metadata_key(asset_type)
            container_name = f"PoseEstimation{to_camel_case(to_snake_case(asset_type))}"

            series_metadata = {}
            for asset_name in positions:
                series_entry = dict(
                    name=f"PoseEstimationSeries{to_camel_case(to_snake_case(asset_name))}",
                    description=f"Position (x, y, z) of {asset_type} '{asset_name}' marker.",
                    # reference_frame=reference_frame,
                )
                if unit is not None:
                    series_entry["unit"] = str(unit).lower()
                series_metadata[asset_name] = series_entry

            metadata["Pose"]["Skeletons"][container_metadata_key] = dict(
                name=f"Skeleton{container_name}", nodes=list(positions), edges=[]
            )
            # can we provide the version of the motive software?
            # PROPOSED (question above): not from the CSV. The Motive docs list everything the first row holds
            # (format version, take name, capture and export frame rate, capture start time and frame, frame
            # counts, rotation type, length units, coordinate space), and the Motive version is not among
            # them. A user who knows it can set `source_software_version` in the metadata. A comment here would
            # keep the next reader from wondering the same thing:
            # # `Format Version` is the version of the CSV layout, the only version the export records.
            metadata["Pose"]["PoseEstimations"][container_metadata_key] = dict(
                name=container_name,
                source_software="Motive",
                # source_software_version=self._header["Format Version"],
                skeleton_metadata_key=container_metadata_key,
                PoseEstimationSeries=series_metadata,
            )

        return metadata

    def get_metadata_template(self) -> DeepDict:
        """Return the containers, skeletons and camera system this interface can write, with the blanks marked.

        The per-asset-type counterpart of :meth:`BasePoseEstimationInterface.get_metadata_template`: one
        ``PoseEstimation`` container and one skeleton per asset type, each keyed
        ``f"{metadata_key}_{asset_type}"``, all linked to one ``Device`` for the OptiTrack camera system,
        and already cross-referenced. Fill in the blanks and pass the result to ``add_to_nwbfile`` or
        ``run_conversion``.

        The fields offered are the ones a motion capture export can be described by. There is no
        ``confidence_definition``, since Motive records no confidence for a position, no ``scorer``, since
        no model is run, and no video links, since the positions are triangulated from every camera in the
        system rather than estimated from one video. The ``camera_model`` entry needs a ``name`` and a
        ``manufacturer``; to go without a camera model, delete that entry and the
        ``device_model_metadata_key`` pointing at it. Any other field left blank is skipped rather than
        written.
        """
        device_metadata_key = "camera"
        device_model_metadata_key = "camera_model"

        skeleton_entries = {}
        container_entries = {}
        for asset_type in self._get_positions():
            container_metadata_key = self._get_container_metadata_key(asset_type)
            keypoint_names = self._get_keypoint_names(asset_type)
            skeleton_entries[container_metadata_key] = _get_skeleton_template_entry(keypoint_names=keypoint_names)
            container_entries[container_metadata_key] = _get_pose_estimation_template_entry(
                keypoint_names=keypoint_names,
                skeleton_metadata_key=container_metadata_key,
                device_metadata_key=device_metadata_key,
            )

        template = DeepDict(
            dict(
                DeviceModels={device_model_metadata_key: _get_device_model_template_entry()},
                Devices={
                    device_metadata_key: _get_device_template_entry(device_model_metadata_key=device_model_metadata_key)
                },
                Pose=dict(Skeletons=skeleton_entries, PoseEstimations=container_entries),
            )
        )

        # Whatever the source recorded wins over the template, as in the base class.
        template.deep_update(self.get_metadata())
        return template

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, *, stub_test: bool = False) -> None:
        """Write one ``PoseEstimation`` container per asset type to the file's behavior module.

        The caller's metadata reaches the writer as they wrote it, as in the base class. An asset type whose
        entry is not in ``metadata["Pose"]["PoseEstimations"]`` is not written, so deleting an entry is how
        to leave a container out.
        """
        metadata = metadata if metadata is not None else self.get_metadata()
        containers_metadata = metadata.get("Pose", {}).get("PoseEstimations", {})

        end_frame = _STUB_SAMPLES if stub_test else None
        timestamps = self._get_timestamps()[:end_frame]

        for asset_type in self._get_positions():
            container_metadata_key = self._get_container_metadata_key(asset_type)
            if container_metadata_key not in containers_metadata:
                continue
            keypoint_data = {
                name: (positions[:end_frame], confidence)
                for name, (positions, confidence) in self._get_keypoint_data(asset_type).items()
            }
            _add_pose_estimation_to_nwbfile(
                nwbfile=nwbfile,
                keypoint_data=keypoint_data,
                timestamps=timestamps,
                metadata=metadata,
                metadata_key=container_metadata_key,
            )
