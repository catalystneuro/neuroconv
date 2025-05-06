import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pydantic import FilePath
from ruamel.yaml import YAML

from ....tools import get_module
from ....utils.checks import calculate_regular_series_rate


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


def _write_pes_to_nwbfile(
    nwbfile,
    df_animal,
    timestamps,
    exclude_nans=False,
    metadata: dict | None = None,
):
    """
    Updated version of _write_pes_to_nwbfile to work with ndx-pose v0.2.0+

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        The NWBFile to which the pose estimation data will be added.
    df_animal : pandas.DataFrame
        The DataFrame containing the pose estimation data for the animal.
    timestamps : numpy.ndarray
        The timestamps for the pose estimation data.
    exclude_nans : bool, default: False
        Whether to exclude NaN values from the data.
    metadata : dict, optional
        The metadata dictionary containing additional information for the pose estimation.
    """
    from ndx_pose import PoseEstimation, PoseEstimationSeries, Skeleton, Skeletons
    from pynwb.file import Subject

    # Set default values
    metadata = metadata or {}
    pose_estimation_metadata = metadata.get("PoseEstimation", {})

    # Extract container information
    container_name = next(
        iter(pose_estimation_metadata.get("PoseEstimationContainers", {}).keys()), "PoseEstimationDeepLabCut"
    )
    container_metadata = pose_estimation_metadata.get("PoseEstimationContainers", {}).get(container_name, {})

    # Extract animal/subject information
    animal = container_metadata.get("subject_name", "")

    # Create a subject if it doesn't exist
    if nwbfile.subject is None and animal:
        subject = Subject(subject_id=animal)
        nwbfile.subject = subject
    else:
        subject = nwbfile.subject

    # Extract skeleton information
    skeleton_name = container_metadata.get("skeleton", f"Skeleton{container_name}_{animal.capitalize()}")
    skeleton_metadata = pose_estimation_metadata.get("Skeletons", {}).get(skeleton_name, {})

    # Create skeleton from the keypoints
    keypoints = df_animal.columns.get_level_values("bodyparts").unique()

    # Use provided skeleton_nodes if available, otherwise use keypoints
    nodes = skeleton_metadata.get("nodes", list(keypoints))
    edges = skeleton_metadata.get("edges", [])

    skeleton = Skeleton(
        name=skeleton_name,
        nodes=nodes,
        edges=np.array(edges) if edges else None,  # Convert edges to numpy array
        subject=subject if animal == getattr(subject, "subject_id", "") else None,
    )

    behavior_processing_module = get_module(nwbfile=nwbfile, name="behavior", description="processed behavioral data")
    if "Skeletons" not in behavior_processing_module.data_interfaces:
        skeletons = Skeletons(skeletons=[skeleton])
        behavior_processing_module.add(skeletons)
    else:
        skeletons = behavior_processing_module["Skeletons"]
        skeletons.add_skeletons(skeleton)

    pose_estimation_series = []
    for keypoint in keypoints:
        data = df_animal.xs(keypoint, level="bodyparts", axis=1).to_numpy()

        if exclude_nans:
            # exclude_nans is inverse infer_timestamps. if not infer, there may be nans
            data = data[~np.isnan(timestamps)]
            timestamps_cleaned = timestamps[~np.isnan(timestamps)]
        else:
            timestamps_cleaned = timestamps

        # Start with default series kwargs
        pose_estimation_series_kwargs = dict(
            name=f"{animal}_{keypoint}" if animal else keypoint,
            description=f"Keypoint {keypoint} from individual {animal}.",
            data=data[:, :2],
            unit="pixels",
            reference_frame="(0,0) corresponds to the bottom left corner of the video.",
            confidence=data[:, 2],
            confidence_definition="Softmax output of the deep neural network.",
        )

        # Get series-specific metadata from PoseEstimationSeries if available
        pose_estimation_series_metadata = container_metadata.get("PoseEstimationSeries", {})
        if keypoint in pose_estimation_series_metadata:
            series_metadata = pose_estimation_series_metadata[keypoint]
            pose_estimation_series_kwargs.update(series_metadata)

        timestamps = np.asarray(timestamps_cleaned).astype("float64", copy=False)
        rate = calculate_regular_series_rate(timestamps)
        if rate is None:
            pose_estimation_series_kwargs["timestamps"] = timestamps
        else:
            pose_estimation_series_kwargs["rate"] = rate
            pose_estimation_series_kwargs["starting_time"] = timestamps[0]

        pes = PoseEstimationSeries(
            **pose_estimation_series_kwargs,
        )
        pose_estimation_series.append(pes)

    # Extract device information
    device_name = container_metadata.get("devices", [f"Camera{container_name}"])[0]
    device_metadata = pose_estimation_metadata.get("Devices", {}).get(device_name, {})

    # Create or get the device
    if device_name not in nwbfile.devices:
        camera = nwbfile.create_device(
            name=device_name,
            description=device_metadata.get("description", "Camera used for behavioral recording and pose estimation."),
        )
    else:
        camera = nwbfile.devices[device_name]

    # Extract video information
    original_videos = container_metadata.get("original_videos", None)

    dimensions = container_metadata.get("dimensions", [0, 0])
    dimensions = np.array([dimensions], dtype="uint32") if dimensions else np.array([[0, 0]], dtype="uint32")

    # Create PoseEstimation container with updated arguments
    pose_estimation_default_kwargs = dict(
        name=container_name,
        pose_estimation_series=pose_estimation_series,
        description=container_metadata.get("description", "2D keypoint coordinates estimated using DeepLabCut."),
        original_videos=original_videos,
        devices=[camera],
        scorer=container_metadata.get("scorer", "DeepLabCut"),
        source_software=container_metadata.get("source_software", "DeepLabCut"),
        skeleton=skeleton,
    )

    # Update with any additional container kwargs
    pose_estimation_default_kwargs.update(
        {
            k: v
            for k, v in container_metadata.items()
            if k
            not in [
                "PoseEstimationSeries",
                "name",
                "description",
                "original_videos",
                "dimensions",
                "devices",
                "scorer",
                "source_software",
                "reference_frame",
                "skeleton",
            ]
        }
    )

    pose_estimation_container = PoseEstimation(**pose_estimation_default_kwargs)

    behavior_processing_module.add(pose_estimation_container)

    return nwbfile
