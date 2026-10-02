import re
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


def _loadmat(file_path: Path, **kwargs):
    """``scipy.io.loadmat`` for the prediction files, with MATLAB v7.3/HDF5 files turned into a clear,
    actionable error instead of a raw ``NotImplementedError``.

    Prediction files are written by DANNCE/sDANNCE through ``scipy``, so they are never v7.3. They are
    read with ``scipy`` rather than ``pymatreader`` because ``pymatreader`` squeezes singleton
    dimensions: a one-animal ``pred`` of shape ``(n, 1, 3, k)`` would lose its animal axis, and a file
    with a single frame or a single landmark would become ambiguous.
    """
    from scipy.io import loadmat

    try:
        return loadmat(str(file_path), **kwargs)
    except NotImplementedError as error:
        raise ValueError(
            f"'{file_path}' is a MATLAB v7.3 (HDF5-based) .mat file. DANNCE/sDANNCE write their prediction "
            "files as MATLAB v5/v7 through scipy, so this is not a prediction file."
        ) from error


class _NoTimingInformationWarning(UserWarning):
    """Raised when nothing gives the pose estimation its times yet: no ``sampling_rate`` and no times set.

    A class of its own so that a caller about to supply the times, ``DANNCEConverter`` from the frametimes,
    can hold this warning back without matching its text.
    """


def _read_mat(file_path: Path) -> dict:
    """Read a MATLAB file written by MATLAB itself (Label3D, sync, calibration), v5 or v7.3."""
    from pymatreader import read_mat

    return read_mat(str(file_path))


class DANNCEInterface(BasePoseEstimationInterface):
    """
    Data interface for DANNCE and social DANNCE (sDANNCE) 3D pose estimation datasets.

    DANNCE (3-Dimensional Aligned Neural Network for Computational Ethology) triangulates
    anatomical landmarks from a calibrated multi-camera rig into 3D world-space coordinates. A
    single interface instance handles either single-animal DANNCE output or one animal's slice of
    multi-animal sDANNCE output (selected via ``animal_index``); writing several sDANNCE animals
    to the same NWBFile takes one interface instance per animal.

    Because DANNCE/sDANNCE landmarks are triangulated 3D points rather than raw per-camera 2D
    detections, the data is written as an ``ndx_pose.MultiCameraPoseEstimation`` container: one set
    of 3D ``PoseEstimationSeries`` (one per landmark), plus one empty per-camera ``PoseEstimation``
    child per entry in ``camera_names``, each linking that camera's ``Device`` and, optionally, its
    source video (``source_video_metadata_key``). When calibration is available (``calibration_path``
    at construction, or by editing ``metadata["Devices"]`` before the write), each camera ``Device``
    is written as an ``ndx_pose.CalibratedCamera`` via the unified ``metadata["Devices"]`` ``type``
    field.

    All landmarks share one ``sampleID`` vector, so the interface holds one alignment key,
    ``interface.alignment[interface.metadata_key]``.
    """

    display_name = "DANNCE"
    keywords = ("DANNCE", "sDANNCE", "social DANNCE", "3D pose estimation", "behavior", "pose estimation")
    associated_suffixes = (".mat",)
    info = "Interface for DANNCE and social DANNCE (sDANNCE) 3D pose estimation output data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_paths"]["description"] = (
            "Path to the DANNCE prediction .mat file (e.g., save_data_AVG.mat), or a list of paths "
            "to concatenate into one continuous session (e.g. sDANNCE jobs split by batch)."
        )
        return source_schema

    @staticmethod
    def get_camera_calibrations(calibration_path: str | Path) -> tuple[list[str], dict[str, dict]]:
        """
        Load per-camera intrinsic/extrinsic calibration parameters, auto-detecting the file format.

        Three DANNCE/sDANNCE calibration layouts are supported:

        - A directory of per-camera ``<prefix>camN_params.mat`` files (keys ``K``, ``r``, ``t``,
          ``RDistort``, ``TDistort``); camera names are derived from the numeric index in the
          filenames (``Camera1``, ...).
        - A single ``calibration.json`` file with top-level ``camera_names`` and ``camera_params``
          (keys ``camera_matrix``, ``rotation_matrix``, ``translation_vector``, ``r_distort``,
          ``t_distort``), index-aligned.
        - A single Label3D-style ``*_dannce.mat`` file with top-level ``camnames`` and ``params``
          (same keys as the per-camera ``.mat`` format), index-aligned.

        Parameters
        ----------
        calibration_path : str or Path
            Path to a calibration directory or file in one of the formats described above.

        Returns
        -------
        camera_names : list of str
            Camera names, in the order given by the calibration source.
        camera_calibrations : dict of str to dict
            Per-camera calibration kwargs (``intrinsic_matrix``, ``rotation_matrix``,
            ``translation_vector``, ``distortion_coefficients``), keyed by camera name. Passing the
            calibration source as the ``calibration_path`` argument of ``__init__`` applies these
            automatically; this method is exposed for callers who want to inspect or edit the values
            (e.g. to merge them into ``metadata["Devices"]`` by hand before the write).
        """
        calibration_path = Path(calibration_path)
        if not calibration_path.exists():
            raise FileNotFoundError(f"Calibration path '{calibration_path}' does not exist.")

        if calibration_path.is_dir():
            return DANNCEInterface._load_calibrations_from_cam_params_directory(calibration_path)
        elif calibration_path.suffix == ".json":
            return DANNCEInterface._load_calibrations_from_json(calibration_path)
        elif calibration_path.suffix == ".mat":
            return DANNCEInterface._load_calibrations_from_label3d_mat(calibration_path)
        else:
            raise ValueError(
                f"Unrecognized calibration format for '{calibration_path}'. Expected a directory of "
                "'<prefix>camN_params.mat' files, a '.json' file, or a Label3D-style '.mat' file."
            )

    @staticmethod
    def _load_calibrations_from_cam_params_directory(directory: Path) -> tuple[list[str], dict[str, dict]]:
        """Parse a directory of '<prefix>camN_params.mat' files, one per camera."""
        pattern = re.compile(r".*cam(\d+)_params\.mat$")
        matches = []
        for file_path in directory.iterdir():
            match = pattern.match(file_path.name)
            if match:
                matches.append((int(match.group(1)), file_path))
        if not matches:
            raise ValueError(f"No '*cam<N>_params.mat' files found in '{directory}'.")
        matches.sort(key=lambda pair: pair[0])

        camera_names = [f"Camera{camera_number}" for camera_number, _ in matches]
        camera_calibrations = {}
        for camera_name, (_, file_path) in zip(camera_names, matches):
            calibration = _read_mat(file_path)
            camera_calibrations[camera_name] = dict(
                intrinsic_matrix=np.asarray(calibration["K"]),
                rotation_matrix=np.asarray(calibration["r"]),
                translation_vector=np.asarray(calibration["t"]).squeeze(),
                distortion_coefficients=np.concatenate(
                    [np.asarray(calibration["RDistort"]).squeeze(), np.asarray(calibration["TDistort"]).squeeze()]
                ),
            )
        return camera_names, camera_calibrations

    @staticmethod
    def _load_calibrations_from_json(file_path: Path) -> tuple[list[str], dict[str, dict]]:
        """Parse a single 'calibration.json' file with 'camera_names' and 'camera_params'."""
        import json

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        camera_names = list(data["camera_names"])
        camera_calibrations = {}
        for camera_name, params in zip(camera_names, data["camera_params"]):
            camera_calibrations[camera_name] = dict(
                intrinsic_matrix=np.asarray(params["camera_matrix"]),
                rotation_matrix=np.asarray(params["rotation_matrix"]),
                translation_vector=np.asarray(params["translation_vector"]).squeeze(),
                distortion_coefficients=np.concatenate(
                    [np.asarray(params["r_distort"]).squeeze(), np.asarray(params["t_distort"]).squeeze()]
                ),
            )
        return camera_names, camera_calibrations

    @staticmethod
    def _load_calibrations_from_label3d_mat(file_path: Path) -> tuple[list[str], dict[str, dict]]:
        """Parse a single Label3D-style '*_dannce.mat' file with 'camnames' and 'params'."""
        data = _read_mat(file_path)
        camera_names = list(np.atleast_1d(data["camnames"]))
        params_list = data["params"]
        if isinstance(params_list, dict):
            params_list = [params_list]

        camera_calibrations = {}
        for camera_name, params in zip(camera_names, params_list):
            camera_calibrations[camera_name] = dict(
                intrinsic_matrix=np.asarray(params["K"]),
                rotation_matrix=np.asarray(params["r"]),
                translation_vector=np.asarray(params["t"]).squeeze(),
                distortion_coefficients=np.concatenate(
                    [np.asarray(params["RDistort"]).squeeze(), np.asarray(params["TDistort"]).squeeze()]
                ),
            )
        return camera_names, camera_calibrations

    @staticmethod
    def _load_sync_tables(sync_path: Path) -> list[tuple[str | None, np.ndarray, np.ndarray]]:
        """
        Load the per-camera synchronization tables that map each ``sampleID`` to a video frame.

        Two layouts are supported:

        - A Label3D-style ``*_dannce.mat`` file (MATLAB v5 or v7.3) with a top-level ``sync`` struct
          array, one entry per camera, index-aligned with ``camnames`` when the file has them.
        - A directory of per-camera ``<CameraName>_sync.mat`` files, the layout that predates Label3D.

        Returns
        -------
        list of (camera name or None, sample IDs, frames)
            One entry per camera, in camera order. The camera name is ``None`` when the file does not
            record it. ``sample IDs`` and ``frames`` are the ``data_sampleID`` and ``data_frame``
            columns of that camera's table, as integers.
        """
        sync_path = Path(sync_path)
        if not sync_path.exists():
            raise FileNotFoundError(f"Sync path '{sync_path}' does not exist.")

        if sync_path.is_dir():
            pattern = re.compile(r"^(.*)_sync\.mat$")
            matches = [(pattern.match(path.name), path) for path in sync_path.iterdir()]
            matches = [(match.group(1), path) for match, path in matches if match]
            if not matches:
                raise ValueError(f"No '<CameraName>_sync.mat' files found in '{sync_path}'.")

            def natural_key(pair):
                return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", pair[0])]

            matches.sort(key=natural_key)
            return [
                (camera_name, *DANNCEInterface._get_sync_columns(_read_mat(path), source=path))
                for camera_name, path in matches
            ]

        tables = DANNCEInterface._load_sync_tables_from_label3d_mat(sync_path)
        if tables is None:
            raise ValueError(
                f"'{sync_path}' has no 'sync' table. Pass a Label3D '*_dannce.mat' file or a directory of "
                "'<CameraName>_sync.mat' files as 'sync_path'."
            )
        return tables

    @staticmethod
    def _load_sync_tables_from_label3d_mat(file_path: Path) -> list[tuple[str | None, np.ndarray, np.ndarray]] | None:
        """The ``sync`` tables of a Label3D-style ``.mat`` file, or ``None`` when it has none."""
        data = _read_mat(file_path)
        if "sync" not in data:
            return None
        sync_entries = data["sync"]
        if isinstance(sync_entries, dict):
            # Label3D writes a cell array, one struct per camera, which reads as a list of dicts. A single
            # camera reads as one dict, and a struct array as one dict whose fields are per-camera lists.
            if isinstance(sync_entries.get("data_frame"), list):
                sync_entries = [dict(zip(sync_entries, values)) for values in zip(*sync_entries.values())]
            else:
                sync_entries = [sync_entries]
        camera_names = [str(name) for name in np.atleast_1d(data["camnames"])] if "camnames" in data else []
        if len(camera_names) != len(sync_entries):
            camera_names = [None] * len(sync_entries)
        return [
            (camera_name, *DANNCEInterface._get_sync_columns(entry, source=file_path))
            for camera_name, entry in zip(camera_names, sync_entries)
        ]

    @staticmethod
    def _get_sync_columns(sync_entry: dict, source: Path) -> tuple[np.ndarray, np.ndarray]:
        if "data_sampleID" not in sync_entry or "data_frame" not in sync_entry:
            raise ValueError(f"The sync table in '{source}' has no 'data_sampleID' and 'data_frame' columns.")
        sample_ids = np.rint(np.ravel(sync_entry["data_sampleID"])).astype("int64")
        frames = np.rint(np.ravel(sync_entry["data_frame"])).astype("int64")
        return sample_ids, frames

    def _resolve_video_frame_indices(self, sync_tables: list[tuple[str | None, np.ndarray, np.ndarray]]) -> np.ndarray:
        """Map each predicted ``sampleID`` to its video frame through the reference camera's sync table.

        The reference camera is the first entry of ``camera_names`` when the sync tables name it, and
        the first table otherwise. Cameras are frame-synchronized by construction, so the other tables
        are only checked against it.
        """
        sample_ids = np.rint(self._sample_id).astype("int64")
        table_by_name = {name: (ids, frames) for name, ids, frames in sync_tables if name is not None}
        reference_name = self._camera_names[0]
        if reference_name in table_by_name:
            reference_ids, reference_frames = table_by_name[reference_name]
        else:
            reference_name, reference_ids, reference_frames = sync_tables[0]

        frame_by_sample_id = dict(zip(reference_ids.tolist(), reference_frames.tolist()))
        missing = [sample_id for sample_id in sample_ids.tolist() if sample_id not in frame_by_sample_id]
        if missing:
            raise ValueError(
                f"{len(missing)} of the {len(sample_ids)} predicted sampleIDs are not in the sync table "
                f"(e.g. {missing[:5]}), so their video frames are unknown. Check that the sync table comes "
                "from the same recording as the predictions."
            )
        video_frame_indices = np.array([frame_by_sample_id[sample_id] for sample_id in sample_ids.tolist()])

        for camera_name, ids, frames in sync_tables:
            other = dict(zip(ids.tolist(), frames.tolist()))
            other_frames = [other.get(sample_id) for sample_id in sample_ids.tolist()]
            if any(
                frame is not None and frame != reference for frame, reference in zip(other_frames, video_frame_indices)
            ):
                warnings.warn(
                    f"The sync table of camera '{camera_name}' maps some sampleIDs to different frames than "
                    f"the reference camera '{reference_name}'. The reference camera's frames are used.",
                    UserWarning,
                    stacklevel=5,  # _resolve_video_frame_indices, __init__, two validate_call frames, caller
                )
                break

        return video_frame_indices

    @validate_call
    def __init__(
        self,
        file_paths: FilePath | list[FilePath],
        *,
        sampling_rate: float | None = None,
        landmark_names: list[str] | None = None,
        subject_name: str | None = None,
        metadata_key: str | None = None,
        camera_names: list[str] | None = None,
        calibration_path: Path | None = None,
        sync_path: Path | None = None,
        animal_index: int | None = None,
        verbose: bool = False,
    ):
        """
        Interface for writing DANNCE and social DANNCE (sDANNCE) 3D pose estimation output files to NWB.

        DANNCE (3-Dimensional Aligned Neural Network for Computational Ethology) is a
        multi-camera 3D pose estimation system that tracks anatomical landmarks on animals.
        This interface reads DANNCE prediction .mat files and converts them to NWB format
        using the ndx-pose extension. It transparently supports both single-animal DANNCE output
        (``pred`` shaped ``(n_frames, 3, n_landmarks)``) and multi-animal sDANNCE output (``pred``
        shaped ``(n_frames, n_animals, 3, n_landmarks)``, selected via ``animal_index``).

        Parameters
        ----------
        file_paths : FilePath or list of FilePath
            Path to the DANNCE prediction .mat file (e.g., save_data_AVG.mat or save_data_MAX.mat), or
            a list of such paths -- e.g. sDANNCE jobs split by batch -- to concatenate, in the given
            order, into one continuous session.
        sampling_rate : float, optional
            The frame rate in Hz of the video the predictions were made on. With a sync table (see
            ``sync_path``) each sample's time is its video frame divided by this rate. Without one,
            the times are ``arange(n_samples) / sampling_rate``, which is only correct when the
            predicted samples are consecutive video frames from the start of the recording, with
            none skipped. When it is not given, set the times with
            ``interface.alignment[interface.metadata_key].set_times(times)`` before conversion; a
            warning at construction says so.
        landmark_names : list of str, optional
            Names for each tracked landmark/body part. Must match the number of landmarks in the
            data. If not provided, defaults to ``["landmark_0", "landmark_1", ...]``.
        subject_name : str, optional
            The individual these landmarks belong to. It names the container and skeleton (e.g.
            ``"rat1"`` gives ``PoseEstimationDANNCERat1``), so animals predicted in separate files can be
            written to the same NWBFile without renaming, and it is recorded as the skeleton's
            ``subject``: the skeleton links to the NWBFile's subject only when this matches its
            ``subject_id``. When ``None``, the container is named after ``animal_index`` for a file with
            more than one animal, and plain ``PoseEstimationDANNCE`` otherwise, and the skeleton links
            to the NWBFile's subject.
        metadata_key : str, optional
            The registry key under which this instance's entries are stored in
            ``metadata["Pose"]["Skeletons"|"MultiCameraPoseEstimations"]``, and its alignment key. The
            key is an internal handle and does not appear in the NWB file; rename NWB objects via their
            ``name`` fields in the metadata dict instead. When ``None`` it resolves to
            ``"dannce_<subject_name>"``, else ``"dannce_animal_<animal_index>"`` for a file with more
            than one animal, else ``"dannce"``.
        camera_names : list of str, optional
            Names of the cameras in the multi-camera rig used to produce the 3D predictions (e.g.,
            ``["Camera1", "Camera2", ..., "Camera6"]``). One camera Device and one empty per-camera
            ``PoseEstimation`` child of the ``MultiCameraPoseEstimation`` container is created per
            name; set that child's ``source_video_metadata_key`` in the metadata to link each
            camera's source video. If not provided, defaults to a single camera, ``["Camera1"]``,
            unless ``calibration_path`` is given, in which case it defaults to the camera names
            detected there.
        calibration_path : str or Path, optional
            Path to a camera calibration directory or file; see :meth:`get_camera_calibrations` for the
            supported formats. When provided, the detected camera names and calibrations are used
            automatically -- both to populate ``camera_names`` (unless explicitly overridden above) and
            to mark each camera's ``metadata["Devices"]`` entry with ``type="CalibratedCamera"`` plus
            its calibration fields, so :meth:`add_to_nwbfile` writes ``ndx_pose.CalibratedCamera``
            devices. To override or supply calibration without this argument, edit
            ``metadata["Devices"]`` before the write.
        sync_path : str or Path, optional
            Path to the synchronization tables that map each prediction's ``sampleID`` to a video
            frame: a Label3D-style ``*_dannce.mat`` file (MATLAB v5 or v7.3) with a ``sync`` field, or
            a directory of per-camera ``<CameraName>_sync.mat`` files. A ``sampleID`` is a row label of
            this table, not a frame index, so without it the frames of the predictions are unknown.
            When not given and ``calibration_path`` is a Label3D ``.mat`` file with a ``sync`` field,
            the table is read from there. The first camera's table is used, and a warning is raised
            if the cameras disagree.
        animal_index : int, optional
            Index of the animal to write, selecting along the animal axis of a 4D ``pred`` array
            (shape ``(n_frames, n_animals, 3, n_landmarks)``), as produced by multi-animal sDANNCE
            output. Required when ``pred`` is 4D with more than one animal; construct one interface
            instance per animal to write each animal to the same NWBFile. When ``pred`` is 4D with a
            singleton animal axis (``n_animals == 1``), defaults to ``0`` if omitted. Must be omitted
            (left as ``None``) when ``pred`` is already 3D (single-animal DANNCE output) -- passing it
            in that case raises an error.
        verbose : bool, default: False
            Controls verbosity of the conversion process.
        """
        from importlib.metadata import version

        import ndx_pose  # noqa: F401
        from packaging import version as version_parse

        ndx_pose_version = version("ndx-pose")
        if version_parse.parse(ndx_pose_version) < version_parse.parse("0.4.0"):
            raise ImportError(
                "DANNCE interface requires ndx-pose version 0.4.0 or later (for CalibratedCamera and "
                f"MultiCameraPoseEstimation). Found version {ndx_pose_version}. Please upgrade: "
                "pip install 'ndx-pose>=0.4.0'"
            )

        file_paths = [Path(file_paths)] if not isinstance(file_paths, list) else [Path(p) for p in file_paths]
        for file_path in file_paths:
            if ".mat" not in file_path.suffixes:
                raise IOError(
                    f"The file '{file_path}' is not a valid DANNCE output file. Only .mat files are supported."
                )

        self.subject_name = subject_name
        self.verbose = verbose

        detected_camera_names = None
        self._camera_calibrations = None
        if calibration_path is not None:
            detected_camera_names, self._camera_calibrations = self.get_camera_calibrations(calibration_path)

        if camera_names:
            self._camera_names = list(camera_names)
        elif detected_camera_names:
            self._camera_names = detected_camera_names
        else:
            self._camera_names = ["Camera1"]

        self._animal_index = animal_index
        self._n_animals = None
        self._sampling_rate = sampling_rate

        # Load data from .mat file(s)
        self._load_dannce_data(file_paths)

        # A sampleID is a row label of the sync table, not a frame index, so the frames come from there.
        sync_tables = None
        if sync_path is not None:
            sync_tables = self._load_sync_tables(sync_path)
        elif calibration_path is not None and Path(calibration_path).suffix == ".mat":
            sync_tables = self._load_sync_tables_from_label3d_mat(Path(calibration_path))
        self._video_frame_indices = self._resolve_video_frame_indices(sync_tables) if sync_tables else None

        if sampling_rate is None:
            warnings.warn(
                "No timing information is available for this DANNCE output: no 'sampling_rate' was given. "
                "Pass 'sampling_rate', or call 'interface.alignment[interface.metadata_key].set_times(times)' "
                "with one time per sample before writing.",
                _NoTimingInformationWarning,
                stacklevel=4,  # __init__, two validate_call frames, caller
            )

        # Named after the individual, as SLEAP names a container after its track, so that animals from
        # separate prediction files do not collide in one NWBFile. Without a subject name, animals are
        # told apart by index only where the file itself holds more than one.
        is_multi_animal = self._n_animals is not None and self._n_animals > 1
        if subject_name is not None:
            snake_case_suffix = to_snake_case(subject_name)
            camel_case_suffix = to_camel_case(snake_case_suffix)
        elif is_multi_animal:
            snake_case_suffix = f"animal_{self._animal_index}"
            camel_case_suffix = f"Animal{self._animal_index}"
        else:
            snake_case_suffix = camel_case_suffix = ""
        self.metadata_key = metadata_key or "_".join(part for part in ("dannce", snake_case_suffix) if part)
        self._container_name = f"PoseEstimationDANNCE{camel_case_suffix}"

        # Validate and set landmark names
        n_landmarks = self._pred.shape[2]
        if landmark_names is not None:
            if len(landmark_names) != n_landmarks:
                raise ValueError(
                    f"Length of landmark_names ({len(landmark_names)}) does not match "
                    f"the number of landmarks in the data ({n_landmarks})."
                )
            self._landmark_names = list(landmark_names)
        else:
            self._landmark_names = [f"landmark_{i}" for i in range(n_landmarks)]

        super().__init__(file_paths=file_paths, verbose=verbose)

    def _load_dannce_data(self, file_paths: list[Path]) -> None:
        """Load and parse one or more DANNCE/sDANNCE .mat prediction files.

        Handles both single-animal DANNCE output (``pred`` shape ``(n_samples, 3, n_landmarks)``)
        and multi-animal sDANNCE output (``pred`` shape ``(n_samples, n_animals, 3, n_landmarks)``,
        sliced down to one animal via ``self._animal_index``). When more than one file is given,
        each is loaded independently and their ``pred``, ``p_max``, and ``sampleID`` arrays are
        concatenated along the frames axis, in the order given, after checking they agree on
        ``pred``'s number of dimensions, number of landmarks, and (when 4D) number of animals.
        """
        pred_parts = []
        p_max_parts = []
        sample_id_parts = []
        reference_shape = None  # (pred.ndim, n_landmarks, n_animals or None), from the first file
        for file_path in file_paths:
            mat_data = _loadmat(file_path)

            pred = mat_data["pred"]
            p_max = mat_data["p_max"]
            sample_id = np.squeeze(mat_data["sampleID"]).astype("float64")  # shape: (1, n_samples) or (n_samples,)

            shape = (pred.ndim, pred.shape[-1], pred.shape[1] if pred.ndim == 4 else None)
            if reference_shape is None:
                reference_shape = shape
            elif shape != reference_shape:
                raise ValueError(
                    f"'{file_path}' has pred.ndim={shape[0]}, {shape[1]} landmarks, "
                    f"{shape[2]} animals, which does not match the first file's pred.ndim="
                    f"{reference_shape[0]}, {reference_shape[1]} landmarks, {reference_shape[2]} animals. "
                    "All 'file_paths' must describe the same session and be concatenable."
                )

            pred_parts.append(pred)
            p_max_parts.append(p_max)
            sample_id_parts.append(sample_id)

        pred = np.concatenate(pred_parts, axis=0)
        p_max = np.concatenate(p_max_parts, axis=0)
        self._sample_id = np.concatenate(sample_id_parts, axis=0)

        if pred.ndim == 4:
            if p_max.ndim != 3:
                raise ValueError(
                    f"Expected 3D 'p_max' to pair with 4D 'pred' (multi-animal sDANNCE output), "
                    f"but 'p_max' has shape {p_max.shape}."
                )
            n_animals = pred.shape[1]
            self._n_animals = n_animals
            if self._animal_index is None:
                if n_animals == 1:
                    # A singleton animal axis has only one possible selection, so there is nothing
                    # for the caller to choose between -- default it instead of demanding a
                    # redundant 'animal_index=0'.
                    self._animal_index = 0
                else:
                    raise ValueError(
                        f"The prediction file has an explicit animal axis with {n_animals} animals "
                        f"(pred shape {pred.shape}). Pass 'animal_index' to select which animal to write."
                    )
            if not 0 <= self._animal_index < n_animals:
                raise IndexError(
                    f"animal_index {self._animal_index} is out of range for a file with {n_animals} animals."
                )
            pred = pred[:, self._animal_index, :, :]
            p_max = p_max[:, self._animal_index, :]
        elif pred.ndim == 3:
            if self._animal_index is not None:
                raise ValueError(
                    f"'animal_index' was provided ({self._animal_index}) but the prediction data is "
                    f"already single-animal (pred shape {pred.shape}). Omit 'animal_index' for this file."
                )
        else:
            raise ValueError(
                f"Expected 'pred' to be 3D (single-animal DANNCE output) or 4D (multi-animal sDANNCE "
                f"output), but got shape {pred.shape}."
            )

        self._pred = pred  # shape: (n_samples, 3, n_landmarks)
        self._p_max = p_max  # shape: (n_samples, n_landmarks)

    @property
    def video_frame_indices(self) -> np.ndarray | None:
        """For each predicted sample, the (0-indexed) video frame it was predicted on, shape
        ``(n_samples,)``, resolved from the ``sampleID`` through the sync table (see ``sync_path``).
        ``None`` when there is no sync table, since a ``sampleID`` is not itself a frame index. Used by
        :class:`~neuroconv.datainterfaces.behavior.dannce.dannceconverter.DANNCEConverter` to index a
        camera's per-frame timestamps (``frametimes.npy``)."""
        return self._video_frame_indices

    def get_original_timestamps(self, stub_test: bool = False) -> np.ndarray:
        if self._sampling_rate is None:
            raise ValueError(
                "No timing information is available for this DANNCE output. The prediction file records "
                "sample labels but no frame rate, so the times cannot be derived from the source. Pass "
                "'sampling_rate' to DANNCEInterface, or call "
                "'interface.alignment[interface.metadata_key].set_times(times)' with one time per sample."
            )
        if self._video_frame_indices is not None:
            frames = self._video_frame_indices
        else:
            # No sync table: assume the samples are consecutive frames from the start of the recording.
            frames = np.arange(len(self._sample_id))
        frames = frames[:100] if stub_test else frames
        return frames / self._sampling_rate

    def _get_timestamps(self, stub_test: bool = False) -> np.ndarray:
        time_bearing_object = self.alignment[self.metadata_key]
        if stub_test:
            base_times = (
                self.get_original_timestamps(stub_test=True)
                if time_bearing_object._times is None
                else time_bearing_object._times[:100]
            )
            return base_times + time_bearing_object._object_offset + self.alignment.offset
        return time_bearing_object.get_times()

    def _get_keypoint_names(self) -> list[str]:
        return list(self._landmark_names)

    def _get_keypoint_data(self) -> dict[str, tuple[np.ndarray, np.ndarray | None]]:
        return {
            landmark: (self._pred[:, :, landmark_index], self._p_max[:, landmark_index])
            for landmark_index, landmark in enumerate(self._landmark_names)
        }

    def _get_camera_pose_estimation_metadata_key(self, camera_name: str) -> str:
        return f"{self.metadata_key}_{camera_name}_pose_estimation"

    def get_metadata(self) -> DeepDict:
        """Build the camera devices and the pose registries, with no free text.

        The per-camera ``PoseEstimation`` entries carry no series of their own (DANNCE/sDANNCE only
        produce triangulated 3D landmarks, not raw per-camera 2D data) and exist to link each camera's
        ``Device``, and its source video once ``source_video_metadata_key`` is set, under the
        ``MultiCameraPoseEstimation`` container.
        """
        metadata = self._get_base_metadata()
        metadata_key = self.metadata_key

        for camera_name in self._camera_names:
            device_entry = {"name": camera_name}
            calibration = (self._camera_calibrations or {}).get(camera_name)
            if calibration is not None:
                # Non-generic device type written the unified way: ``type`` names the concrete class
                # (resolved via ``neuroconv.tools.nwb_helpers._device_types``) and the calibration
                # fields ride alongside it as constructor kwargs. Editing this entry -- or adding
                # ``type="CalibratedCamera"`` to a camera that has none -- before the write is how the
                # calibration is overridden or supplied.
                device_entry["type"] = "CalibratedCamera"
                for field in ("intrinsic_matrix", "rotation_matrix", "translation_vector", "distortion_coefficients"):
                    if calibration.get(field) is not None:
                        device_entry[field] = calibration[field]
            metadata["Devices"][camera_name] = device_entry

        metadata["Pose"]["Skeletons"][metadata_key] = {
            "name": f"Skeleton{self._container_name}",
            "nodes": list(self._landmark_names),
        }
        if self.subject_name is not None:
            metadata["Pose"]["Skeletons"][metadata_key]["subject"] = self.subject_name

        pose_estimation_metadata_keys = []
        for camera_name in self._camera_names:
            camera_metadata_key = self._get_camera_pose_estimation_metadata_key(camera_name)
            metadata["Pose"]["PoseEstimations"][camera_metadata_key] = {
                "name": f"{camera_name}PoseEstimation",
                "device_metadata_key": camera_name,
            }
            pose_estimation_metadata_keys.append(camera_metadata_key)

        # DANNCE triangulates in the units of its calibration, which DANNCE/Label3D rigs calibrate in
        # millimeters, and its confidence is the peak of the 3D probability map.
        series_metadata = {}
        for landmark in self._landmark_names:
            landmark_capitalized = landmark.replace("_", " ").title().replace(" ", "")
            series_metadata[landmark] = {
                "name": f"PoseEstimationSeries{landmark_capitalized}",
                "unit": "millimeters",
                "confidence_definition": "Maximum probability from the 3D probability volume.",
            }

        metadata["Pose"]["MultiCameraPoseEstimations"][metadata_key] = {
            "name": self._container_name,
            "source_software": "DANNCE",
            "skeleton_metadata_key": metadata_key,
            "pose_estimation_metadata_keys": pose_estimation_metadata_keys,
            "PoseEstimationSeries": series_metadata,
        }

        return metadata

    def get_metadata_template(self) -> DeepDict:
        """Return the container, skeleton, per-camera children and cameras this interface can write, with
        the blanks marked.

        The multi-camera counterpart of :meth:`BasePoseEstimationInterface.get_metadata_template`: one
        ``MultiCameraPoseEstimation`` container and one skeleton under this interface's
        ``metadata_key``, one per-camera ``PoseEstimation`` child per camera, and one camera ``Device``
        per child, all already cross-referenced. Fill in the blanks and pass the result to
        ``add_to_nwbfile`` or ``run_conversion``; an optional field left blank is skipped rather than
        written. ``reference_frame`` is the field to fill above all others, since ndx-pose requires it.
        """
        metadata_key = self.metadata_key
        device_model_metadata_key = "camera_model"

        camera_entries = {
            self._get_camera_pose_estimation_metadata_key(camera_name): dict(
                name=None, device_metadata_key=camera_name, source_video_metadata_key=None
            )
            for camera_name in self._camera_names
        }
        series_template = {
            landmark: dict(name=None, description=None, unit=None, reference_frame=None, confidence_definition=None)
            for landmark in self._landmark_names
        }
        template = DeepDict(
            dict(
                DeviceModels={device_model_metadata_key: _get_device_model_template_entry()},
                Devices={
                    camera_name: _get_device_template_entry(device_model_metadata_key=device_model_metadata_key)
                    for camera_name in self._camera_names
                },
                Pose=dict(
                    Skeletons={metadata_key: _get_skeleton_template_entry(keypoint_names=self._landmark_names)},
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
        Add DANNCE pose estimation data to an NWB file.

        The metadata given reaches the writer as written rather than merged over this interface's
        defaults, as in :meth:`BasePoseEstimationInterface.add_to_nwbfile`.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the pose estimation data to.
        metadata : dict, optional
            Metadata dictionary. When ``None``, ``get_metadata()`` is used.
        stub_test : bool, default: False
            If True, write only the first 100 frames to the NWB file for quick smoke testing.
            The interface's internal data arrays are not mutated.

        Notes
        -----
        Camera calibration is written by marking a camera's ``metadata["Devices"]`` entry with
        ``type="CalibratedCamera"`` plus its calibration fields (``intrinsic_matrix``,
        ``rotation_matrix``, ``translation_vector``, ``distortion_coefficients``); that entry is then
        built as an ``ndx_pose.CalibratedCamera`` instead of a plain ``Device``. Passing
        ``calibration_path`` at construction fills these in automatically. A camera whose Device is
        already in the ``NWBFile`` (e.g. one written by a video interface, or by another animal's
        interface instance) is reused unchanged. Each camera's source video is linked by setting
        ``source_video_metadata_key`` on its entry in ``metadata["Pose"]["PoseEstimations"]``, which
        names the video's entry in ``metadata["Behavior"]["ExternalVideos"]``; the video has to be
        written first.
        """
        keypoint_data = self._get_keypoint_data()
        if stub_test:
            keypoint_data = {
                landmark: (positions[:100], confidence[:100])
                for landmark, (positions, confidence) in keypoint_data.items()
            }
        _add_multi_camera_pose_estimation_to_nwbfile(
            nwbfile=nwbfile,
            keypoint_data=keypoint_data,
            timestamps=self._get_timestamps(stub_test=stub_test),
            metadata=metadata if metadata is not None else self.get_metadata(),
            metadata_key=self.metadata_key,
        )
