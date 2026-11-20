"""Read the pose-3d CSV and the ``calibration.toml`` that Anipose writes."""

import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

# Anipose writes these six columns for every keypoint, in this order, from version 0.1.0 on.
_KEYPOINT_SUFFIXES = ("x", "y", "z", "error", "ncams", "score")
_TRANSFORM_MATRIX_COLUMNS = [f"M_{row}{column}" for row in range(3) for column in range(3)]
_TRANSFORM_CENTER_COLUMNS = [f"center_{axis}" for axis in range(3)]


def _read_pose_3d(file_path: Path) -> dict:
    """Return the keypoints, frame indices, positions, scores and frame transform of a pose-3d CSV.

    The CSV has one row per frame and, for each keypoint, the columns ``<keypoint>_x``, ``_y``, ``_z``, ``_error``,
    ``_ncams`` and ``_score``, then the frame transform ``M_00`` to ``M_22`` and ``center_0`` to ``center_2`` (from
    Anipose 0.5.3 on), then the frame index ``fnum``. The transform columns are matched by their exact names, since
    a keypoint can itself be called ``pad(center)``. Anipose writes each point as ``X @ M.T - center``, where ``X``
    is the point in the world frame of the calibration, so ``transform`` is ``None`` for the older files that do not
    record it.
    """
    table = pd.read_csv(file_path)
    columns = set(table.columns)
    keypoint_names = []
    for column in table.columns:
        keypoint_name, _, suffix = column.rpartition("_")
        if suffix == "x" and all(f"{keypoint_name}_{other}" in columns for other in _KEYPOINT_SUFFIXES):
            keypoint_names.append(keypoint_name)
    if not keypoint_names or "fnum" not in columns:
        raise ValueError(
            f"'{file_path}' is not an Anipose pose-3d CSV: expected the columns '<keypoint>_x', '_y', '_z', "
            "'_error', '_ncams' and '_score' for every keypoint, and an 'fnum' column."
        )

    positions = np.stack(
        [table[[f"{name}_{axis}" for axis in "xyz"]].to_numpy(dtype="float64") for name in keypoint_names], axis=1
    )
    scores = table[[f"{name}_score" for name in keypoint_names]].to_numpy(dtype="float64")

    transform = None
    if columns.issuperset(_TRANSFORM_MATRIX_COLUMNS + _TRANSFORM_CENTER_COLUMNS):
        # The same value is written in every row.
        matrix = table[_TRANSFORM_MATRIX_COLUMNS].iloc[0].to_numpy(dtype="float64").reshape(3, 3)
        center = table[_TRANSFORM_CENTER_COLUMNS].iloc[0].to_numpy(dtype="float64")
        transform = (matrix, center)

    return dict(
        keypoint_names=keypoint_names,
        frame_indices=table["fnum"].to_numpy(dtype="int64"),
        positions=positions,  # (n_frames, n_keypoints, 3)
        scores=scores,  # (n_frames, n_keypoints)
        transform=transform,
    )


def _rodrigues_to_rotation_matrix(rotation_vector: np.ndarray) -> np.ndarray:
    """Return the rotation matrix of a Rodrigues vector, as ``cv2.Rodrigues`` computes it."""
    rotation_vector = np.asarray(rotation_vector, dtype="float64").ravel()
    angle = np.linalg.norm(rotation_vector)
    if angle == 0:
        return np.eye(3)
    axis = rotation_vector / angle
    cross_product_matrix = np.array([[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]])
    return np.cos(angle) * np.eye(3) + (1 - np.cos(angle)) * np.outer(axis, axis) + np.sin(angle) * cross_product_matrix


def _read_calibration(file_path: Path) -> dict[str, dict]:
    """Return ``{camera name: CalibratedCamera fields}`` for the cameras of a ``calibration.toml``, in file order.

    The file has one table per camera and, when aniposelib wrote it, a ``[metadata]`` table. The order is the order
    of the tables in the file: aniposelib's own ``CameraGroup.load`` sorts the table names as strings, which puts
    ``cam_10`` before ``cam_2`` on rigs of eleven or more cameras. The rotation is stored as a Rodrigues vector and
    returned as a matrix. The image ``size`` has no field in ``CalibratedCamera`` and is not returned.
    """
    with open(file_path, "rb") as file:
        content = tomllib.load(file)

    cameras = {}
    for table_name, table in content.items():
        if not isinstance(table, dict) or "matrix" not in table:
            continue  # the [metadata] table
        fields = dict(
            intrinsic_matrix=np.asarray(table["matrix"], dtype="float64"),
            rotation_matrix=_rodrigues_to_rotation_matrix(table["rotation"]),
            translation_vector=np.asarray(table["translation"], dtype="float64"),
            distortion_coefficients=np.asarray(table["distortions"], dtype="float64"),
        )
        # The fisheye model reads its four coefficients differently from the first four of the pinhole model, and
        # CalibratedCamera has no field for the lens model.
        if table.get("fisheye", False):
            fields["description"] = (
                "Fisheye lens model (OpenCV fisheye): the distortion coefficients are k1, k2, k3 and k4."
            )
        cameras[str(table.get("name", table_name))] = fields

    if not cameras:
        raise ValueError(f"'{file_path}' has no camera tables. Expected a calibration.toml written for Anipose.")
    return cameras
