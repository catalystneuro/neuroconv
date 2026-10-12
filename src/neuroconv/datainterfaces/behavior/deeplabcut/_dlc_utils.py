import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pydantic import FilePath
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
        with open(path, "r", encoding="utf-8") as f:
            cfg = ruamelFile.load(f)
            curr_dir = config_file_path.parent
            if cfg["project_path"] != curr_dir:
                cfg["project_path"] = curr_dir
    except Exception as err:
        if len(err.args) > 2:
            if err.args[2] == "could not determine a constructor for the tag '!!python/tuple'":
                with open(path, "r", encoding="utf-8") as ymlfile:
                    cfg = yaml.load(ymlfile, Loader=yaml.SafeLoader)
            else:
                raise

    return cfg


def _get_cv2_timestamps(file_path: Path | str):
    """
    Extract and return an array of timestamps for each frame in a video using OpenCV.

    Parameters
    ----------
    file_path : Path | str
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


def _get_video_timestamps(movie_file, VARIABILITYBOUND=1000, infer_timestamps=True):
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


def _get_edges_from_config(config_dict: dict, bodyparts: list) -> list:
    """Return the project config's skeleton as pairs of bodypart indices.

    DeepLabCut states the skeleton in the config as pairs of bodypart *names*, while ``ndx-pose`` wants
    indices into the node list, so the names are looked up. A pair naming a bodypart this file does not
    track is skipped rather than guessed at: a project config can outlive the bodyparts of any one run.

    Parameters
    ----------
    config_dict : dict
        The parsed project config. An empty one, which is what an interface built without a config file
        carries, yields no edges.
    bodyparts : list
        The node names, in the order they are written, which is what the indices address.

    Returns
    -------
    list
        Pairs of indices into ``bodyparts``, empty when the config states no skeleton.
    """
    skeleton = config_dict.get("skeleton") or []
    index_of = {bodypart: index for index, bodypart in enumerate(bodyparts)}

    edges = []
    for edge in skeleton:
        if len(edge) == 2 and edge[0] in index_of and edge[1] in index_of:
            edges.append([index_of[edge[0]], index_of[edge[1]]])

    return edges


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
    # An absent pickle is not an error and not worth a warning: DeepLabCut does not always write one, and
    # the project config is the first place the edges are looked for.

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
        # Nothing is invented here. The stem is matched against the config's ``video_sets`` keys, which are
        # absolute paths from the machine that did the training, so a miss is the common case rather than
        # the exception, and the frame size this used to return ("0, 0, 0, 0", which parses to [[0, 0]])
        # was a fabricated one written into the file. See https://github.com/catalystneuro/neuroconv/issues/1046.
        video = None, None

    # The video in the config_file looks like this:
    # video_sets:
    #    /Data/openfield-Pranav-2018-08-20/videos/m1s1.mp4:
    #        crop: 0, 640, 0, 480

    video_file_path, image_shape = video

    return video_file_path, image_shape
