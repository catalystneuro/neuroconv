import importlib
import pickle
import warnings
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd
import yaml
from pydantic import FilePath
from pynwb import NWBFile
from ruamel.yaml import YAML


def _read_config(config_file_path: FilePath) -> dict:
    """
    Reads structured config file defining a project.
    """

    ruamelFile = YAML()
    path = Path(config_file_path)

    if not path.exists():
        raise FileNotFoundError(f"Config file {path} not found.")

    try:
        with open(path, "r") as f:
            cfg = ruamelFile.load(f)
            curr_dir = config_file_path.parent
            if cfg["project_path"] != curr_dir:
                cfg["project_path"] = curr_dir
    except Exception as err:
        if len(err.args) > 2:
            if err.args[2] == "could not determine a constructor for the tag '!!python/tuple'":
                with open(path, "r") as ymlfile:
                    cfg = yaml.load(ymlfile, Loader=yaml.SafeLoader)
            else:
                raise

    return cfg


def _get_cv2_timestamps(file_path: Union[Path, str]):
    """
    Extract and return an array of timestamps for each frame in a video using OpenCV.

    Parameters
    ----------
    file_path : Union[Path, str]
        The path to the video file from which to extract timestamps.

    Returns
    -------
    np.ndarray
        A numpy array containing the timestamps (in milliseconds) for each frame in the video.
    """
    import cv2
    from tqdm.auto import tqdm

    reader = cv2.VideoCapture(file_path)
    timestamps = []
    n_frames = int(reader.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = reader.get(cv2.CAP_PROP_FPS)

    # Calculate total time in minutes
    total_time_minutes = n_frames / (fps * 60)

    description = (
        "Inferring timestamps from video.\n"
        "This step can be avoided by previously setting the timestamps with `set_aligned_timestamps`"
    )
    tqdm.write(description)

    # Use tqdm with a context manager
    with tqdm(
        total=n_frames,
        desc="Processing frames",
        unit=" frame",
        bar_format="{l_bar}{bar} | {rate_fmt} | {elapsed}<{remaining} | {unit_divisor}",
    ) as pbar:
        # Note, using unit_divisor instead of postfix because of a bug in tqdm https://github.com/tqdm/tqdm/issues/712

        for frame_idx in range(n_frames):
            _ = reader.read()
            timestamps.append(reader.get(cv2.CAP_PROP_POS_MSEC))

            current_time_minutes = (frame_idx + 1) / (fps * 60)

            pbar.unit_divisor = f"processed {current_time_minutes:.2f} of {total_time_minutes:.2f} minutes"
            pbar.update(1)

    reader.release()
    return timestamps


def _get_movie_timestamps(movie_file, VARIABILITYBOUND=1000, infer_timestamps=True):
    """
    Return numpy array of the timestamps for a video.

    Parameters
    ----------
    movie_file : str
        Path to movie_file
    """

    timestamps = _get_cv2_timestamps(file_path=movie_file)
    timestamps = np.array(timestamps) / 1000  # Convert to seconds

    import cv2

    reader = cv2.VideoCapture(movie_file)
    fps = reader.get(cv2.CAP_PROP_FPS)
    reader.release()

    if np.nanvar(np.diff(timestamps)) < 1.0 / fps * 1.0 / VARIABILITYBOUND:
        warnings.warn(
            "Variability of timestamps suspiciously small. See: https://github.com/DeepLabCut/DLC2NWB/issues/1"
        )

    if any(timestamps[1:] == 0):
        # Infers times when OpenCV provides 0s
        warning_msg = "Removing"
        timestamp_zero_count = np.count_nonzero(timestamps == 0)
        timestamps[1:][timestamps[1:] == 0] = np.nan  # replace 0s with nan

        if infer_timestamps:
            warning_msg = "Replacing"
            timestamps = _infer_nan_timestamps(timestamps)

        warnings.warn(  # warns user of percent of 0 frames
            "%s cv2 timestamps returned as 0: %f%%" % (warning_msg, (timestamp_zero_count / len(timestamps) * 100))
        )

    return timestamps


def _infer_nan_timestamps(timestamps):
    """Given np.array, interpolate nan values using index * sampling rate"""
    bad_timestamps_mask = np.isnan(timestamps)
    # Runs of good timestamps
    good_run_indices = np.where(np.diff(np.hstack(([False], bad_timestamps_mask == False, [False]))))[0].reshape(-1, 2)

    # For each good run, get the diff and append to cumulative array
    sampling_diffs = np.array([])
    for idx in good_run_indices:
        sampling_diffs = np.append(sampling_diffs, np.diff(timestamps[idx[0] : idx[1]]))
    estimated_sampling_rate = np.mean(sampling_diffs)  # Average over diffs

    # Infer timestamps with avg sampling rate
    bad_timestamps_indexes = np.argwhere(bad_timestamps_mask)[:, 0]
    inferred_timestamps = bad_timestamps_indexes * estimated_sampling_rate
    timestamps[bad_timestamps_mask] = inferred_timestamps

    return timestamps


def _ensure_individuals_in_header(df, individual_name: str):
    """
    Ensure that the 'individuals' column is present in the header of the given DataFrame.

    Parameters:
        df (pandas.DataFrame): The DataFrame to modify.
        individual_name (str): The name of the individual to add to the header.

    Returns:
        pandas.DataFrame: The modified DataFrame with the 'individuals' column added to the header.

    Notes:
        - If the 'individuals' column is already present in the header, no modifications are made.
        - If the 'individuals' column is not present, a new DataFrame is created with the 'individual_name'
        as the column name, and the 'individuals' column is added to the header of the DataFrame.
        - The order of the columns in the header is preserved.

    """
    if "individuals" not in df.columns.names:
        # Single animal project -> add individual row to
        # the header of single animal projects.
        temp = pd.concat({individual_name: df}, names=["individuals"], axis=1)
        df = temp.reorder_levels(["scorer", "individuals", "bodyparts", "coords"], axis=1)

    return df


def _get_graph_edges(metadata_file_path: Path):
    """
    Extracts the part affinity field graph from the metadata pickle file.

    Parameters
    ----------
    metadata_file_path : Path
        The path to the metadata pickle file.

    Returns
    -------
    list
        The part affinity field graph, which defines the edges between the keypoints in the pose estimation.
    """
    paf_graph = []
    if metadata_file_path.exists():
        with open(metadata_file_path, "rb") as file:
            metadata = pickle.load(file)

        test_cfg = metadata["data"]["DLC-model-config file"]
        paf_graph = test_cfg.get("partaffinityfield_graph", [])
        if paf_graph:
            paf_inds = test_cfg.get("paf_best")
            if paf_inds is not None:
                paf_graph = [paf_graph[i] for i in paf_inds]
    else:
        warnings.warn("Metadata not found...")

    return paf_graph


def _get_video_info_from_config_file(config_file_path: Path, vidname: str):
    """
    Get the video information from the project config file.

    Parameters
    ----------
    config_file_path : Path
        The path to the project config file.
    vidname : str
        The name of the video.

    Returns
    -------
    tuple
        A tuple containing the video file path and the image shape.
    """
    config_file_path = Path(config_file_path)
    cfg = _read_config(config_file_path)

    video = None
    for video_path, params in cfg["video_sets"].items():
        if vidname in video_path:
            video = video_path, params["crop"]
            break

    if video is None:
        warnings.warn(f"The corresponding video file could not be found in the config file")
        video = None, "0, 0, 0, 0"

    # The video in the config_file looks like this:
    # video_sets:
    #    /Data/openfield-Pranav-2018-08-20/videos/m1s1.mp4:
    #        crop: 0, 640, 0, 480

    video_file_path, image_shape = video

    return video_file_path, image_shape


def _get_pes_args(
    *,
    h5file: Path,
    individual_name: str,
):
    h5file = Path(h5file)

    _, scorer = h5file.stem.split("DLC")
    scorer = "DLC" + scorer

    df = _ensure_individuals_in_header(pd.read_hdf(h5file), individual_name)

    return scorer, df


def _write_pes_to_nwbfile(
    nwbfile,
    animal,
    df_animal,
    scorer,
    video_file_path,
    image_shape,
    paf_graph,
    timestamps,
    exclude_nans,
    pose_estimation_container_kwargs: Optional[dict] = None,
):

    from ndx_pose import PoseEstimation, PoseEstimationSeries

    pose_estimation_container_kwargs = pose_estimation_container_kwargs or dict()

    pose_estimation_series = []
    for keypoint in df_animal.columns.get_level_values("bodyparts").unique():
        data = df_animal.xs(keypoint, level="bodyparts", axis=1).to_numpy()

        if exclude_nans:
            # exclude_nans is inverse infer_timestamps. if not infer, there may be nans
            data = data[~np.isnan(timestamps)]
            timestamps_cleaned = timestamps[~np.isnan(timestamps)]
        else:
            timestamps_cleaned = timestamps

        pes = PoseEstimationSeries(
            name=f"{animal}_{keypoint}" if animal else keypoint,
            description=f"Keypoint {keypoint} from individual {animal}.",
            data=data[:, :2],
            unit="pixels",
            reference_frame="(0,0) corresponds to the bottom left corner of the video.",
            timestamps=timestamps_cleaned,
            confidence=data[:, 2],
            confidence_definition="Softmax output of the deep neural network.",
        )
        pose_estimation_series.append(pes)

    deeplabcut_version = None
    is_deeplabcut_installed = importlib.util.find_spec(name="deeplabcut") is not None
    if is_deeplabcut_installed:
        deeplabcut_version = importlib.metadata.version(distribution_name="deeplabcut")

    # TODO, taken from the original implementation, improve it if the video is passed
    dimensions = [list(map(int, image_shape.split(",")))[1::2]]
    pose_estimation_default_kwargs = dict(
        pose_estimation_series=pose_estimation_series,
        description="2D keypoint coordinates estimated using DeepLabCut.",
        original_videos=[video_file_path],
        dimensions=dimensions,
        scorer=scorer,
        source_software="DeepLabCut",
        source_software_version=deeplabcut_version,
        nodes=[pes.name for pes in pose_estimation_series],
        edges=paf_graph if paf_graph else None,
        **pose_estimation_container_kwargs,
    )
    pose_estimation_default_kwargs.update(pose_estimation_container_kwargs)
    pose_estimation_container = PoseEstimation(**pose_estimation_default_kwargs)

    if "behavior" in nwbfile.processing:  # TODO: replace with get_module
        behavior_processing_module = nwbfile.processing["behavior"]
    else:
        behavior_processing_module = nwbfile.create_processing_module(
            name="behavior", description="processed behavioral data"
        )
    behavior_processing_module.add(pose_estimation_container)

    return nwbfile


def add_subject_to_nwbfile(
    nwbfile: NWBFile,
    h5file: FilePath,
    individual_name: str,
    config_file: Optional[FilePath] = None,
    timestamps: Optional[Union[list, np.ndarray]] = None,
    pose_estimation_container_kwargs: Optional[dict] = None,
) -> NWBFile:
    """
    Given the subject name, add the DLC .h5 file to an in-memory NWBFile object.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        The in-memory nwbfile object to which the subject specific pose estimation series will be added.
    h5file : str or path
        Path to the DeepLabCut .h5 output file.
    individual_name : str
        Name of the subject (whose pose is predicted) for single-animal DLC project.
        For multi-animal projects, the names from the DLC project will be used directly.
    config_file : str or path, optional
        Path to a project config.yaml file
    timestamps : list, np.ndarray or None, default: None
        Alternative timestamps vector. If None, then use the inferred timestamps from DLC2NWB
    pose_estimation_container_kwargs : dict, optional
        Dictionary of keyword argument pairs to pass to the PoseEstimation container.

    Returns
    -------
    nwbfile : pynwb.NWBFile
        nwbfile with pes written in the behavior module
    """
    h5file = Path(h5file)

    if "DLC" not in h5file.name or not h5file.suffix == ".h5":
        raise IOError("The file passed in is not a DeepLabCut h5 data file.")

    video_name, scorer = h5file.stem.split("DLC")
    scorer = "DLC" + scorer

    # TODO probably could be read directly with h5py
    # This requires pytables
    data_frame_from_hdf5 = pd.read_hdf(h5file)
    df = _ensure_individuals_in_header(data_frame_from_hdf5, individual_name)

    # Note the video here is a tuple of the video path and the image shape
    if config_file is not None:
        video_file_path, image_shape = _get_video_info_from_config_file(
            config_file_path=config_file,
            vidname=video_name,
        )
    else:
        video_file_path = None
        image_shape = "0, 0, 0, 0"

    # find timestamps only if required:``
    timestamps_available = timestamps is not None
    if not timestamps_available:
        if video_file_path is None:
            timestamps = df.index.tolist()  # setting timestamps to dummy
        else:
            timestamps = _get_movie_timestamps(video_file_path, infer_timestamps=True)

    # Fetch the corresponding metadata pickle file, we extract the edges graph from here
    # TODO: This is the original implementation way to extract the file name but looks very brittle. Improve it
    filename = str(h5file.parent / h5file.stem)
    for i, c in enumerate(filename[::-1]):
        if c.isnumeric():
            break
    if i > 0:
        filename = filename[:-i]

    metadata_file_path = Path(filename + "_meta.pickle")
    paf_graph = _get_graph_edges(metadata_file_path=metadata_file_path)

    df_animal = df.xs(individual_name, level="individuals", axis=1)

    return _write_pes_to_nwbfile(
        nwbfile,
        individual_name,
        df_animal,
        scorer,
        video_file_path,
        image_shape,
        paf_graph,
        timestamps,
        exclude_nans=False,
        pose_estimation_container_kwargs=pose_estimation_container_kwargs,
    )
