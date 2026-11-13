"""Shared helpers for the DANNCE unit tests (``test_dannce_interface.py`` and ``test_dannce_converter.py``)."""

import numpy as np
from scipy.io import savemat


def write_label3d_file(
    file_path,
    *,
    camera_names: list[str] | None = None,
    sample_ids=None,
    frames_per_camera: list | None = None,
    with_calibration: bool = False,
) -> None:
    """Write a Label3D-style ``*_dannce.mat`` laid out as Label3D does: cell arrays with one struct per camera.

    Parameters
    ----------
    file_path : path-like
        Where to write the file.
    camera_names : list of str, optional
        Written as ``camnames``. Left out of the file when not given, as some Label3D files do.
    sample_ids : array-like, optional
        The ``data_sampleID`` column of every camera's ``sync`` table. No ``sync`` is written without it.
    frames_per_camera : list of array-like, optional
        One ``data_frame`` column per camera, pairing row by row with ``sample_ids``.
    with_calibration : bool, default: False
        Also write an identity ``params`` calibration (``K``, ``r``, ``t``, ``RDistort``, ``TDistort``) per camera.
    """
    n_cameras = len(camera_names) if camera_names is not None else len(frames_per_camera)
    contents = {}
    if camera_names is not None:
        contents["camnames"] = np.array(camera_names, dtype=object).reshape(1, -1)
    if sample_ids is not None:
        sync = np.empty((n_cameras, 1), dtype=object)
        for camera_index, frames in enumerate(frames_per_camera):
            sync[camera_index, 0] = dict(
                data_sampleID=np.asarray(sample_ids, dtype="float64"),
                data_frame=np.asarray(frames, dtype="float64"),
            )
        contents["sync"] = sync
    if with_calibration:
        params = np.empty((n_cameras, 1), dtype=object)
        for camera_index in range(n_cameras):
            params[camera_index, 0] = dict(
                K=np.eye(3), r=np.eye(3), t=np.zeros((1, 3)), RDistort=np.zeros((1, 3)), TDistort=np.zeros((1, 2))
            )
        contents["params"] = params
    savemat(str(file_path), contents)
