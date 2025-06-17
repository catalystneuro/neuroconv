import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pydantic import FilePath
from ruamel.yaml import YAML

from ....tools import get_module
from ....utils import DeepDict
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


def _add_pose_estimation_to_nwbfile(
    nwbfile,
    df_animal,
    timestamps,
    exclude_nans=False,
    pose_estimation_metadata_key: str = "PoseEstimationDeepLabCut",
    metadata: dict | None = None,
):
    """
    Adds pose estimation data to an nwbfile using ndx-pose v0.2.0+

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

    # Extract keypoints from the DataFrame
    keypoints = df_animal.columns.get_level_values("bodyparts").unique()

    # Create default metadata structure
    default_metadata = dict()
    animal = ""  # Default empty animal name
    skeleton_default_name = f"Skeleton{pose_estimation_metadata_key}_{animal.capitalize()}"
    # Set up default container structure
    camera_default_name = f"Camera{pose_estimation_metadata_key}"
    default_metadata["PoseEstimation"] = {
        "PoseEstimationContainers": {
            pose_estimation_metadata_key: {
                "name": pose_estimation_metadata_key,
                "description": "2D keypoint coordinates estimated using DeepLabCut.",
                "source_software": "DeepLabCut",
                "scorer": "DeepLabCut",
                "devices": [camera_default_name],
                "PoseEstimationSeries": {},
                "skeleton": skeleton_default_name,
            }
        },
        "Devices": {
            camera_default_name: {
                "name": camera_default_name,
                "description": "Camera used for behavioral recording and pose estimation.",
            }
        },
        "Skeletons": {
            skeleton_default_name: {
                "name": skeleton_default_name,
                "nodes": list(keypoints),
                "edges": [],
                "subject": animal,
            }
        },
    }
    default_metadata = DeepDict(default_metadata)
    # Update with provided metadata if any
    if metadata:
        default_metadata.deep_update(metadata)

    # Access the updated metadata structure directly
    pose_estimation_metadata = default_metadata["PoseEstimation"]
    container_metadata = pose_estimation_metadata["PoseEstimationContainers"][pose_estimation_metadata_key]

    # Get skeleton information
    skeleton_metadata_key = container_metadata["skeleton"]
    skeleton_metadata = pose_estimation_metadata["Skeletons"][skeleton_metadata_key]

    # If the skeleton name is identical to the subject id then link the skeleton to the subject
    skeleton_subject = skeleton_metadata["subject"]
    if nwbfile.subject is not None and skeleton_subject == nwbfile.subject.subject_id:
        subject = nwbfile.subject
    else:
        subject = None

    # Create skeleton
    skeleton = Skeleton(
        name=skeleton_metadata["name"],
        nodes=skeleton_metadata["nodes"],
        edges=np.array(skeleton_metadata["edges"]) if skeleton_metadata["edges"] else None,
        subject=subject,
    )

    behavior_processing_module = get_module(nwbfile=nwbfile, name="behavior", description="processed behavioral data")
    if "Skeletons" not in behavior_processing_module.data_interfaces:
        skeletons = Skeletons(skeletons=[skeleton])
        behavior_processing_module.add(skeletons)
    else:
        skeletons = behavior_processing_module["Skeletons"]
        skeletons.add_skeletons(skeleton)

    # Create pose estimation series for each keypoint
    pose_estimation_series = []
    for keypoint in keypoints:
        data = df_animal.xs(keypoint, level="bodyparts", axis=1).to_numpy()

        if exclude_nans:
            # exclude_nans is inverse infer_timestamps. if not infer, there may be nans
            data = data[~np.isnan(timestamps)]
            timestamps_cleaned = timestamps[~np.isnan(timestamps)]
        else:
            timestamps_cleaned = timestamps

        # Default series kwargs
        pose_estimation_series_kwargs = dict(
            name=f"PoseEstimationSeries{keypoint.capitalize()}",
            description=f"Pose estimation series for {keypoint}.",
            data=data[:, :2],
            unit="pixels",
            reference_frame="(0,0) corresponds to the bottom left corner of the video.",
            confidence=data[:, 2],
            confidence_definition="Softmax output of the deep neural network.",
        )

        # Update with series-specific metadata if available
        pose_estimation_series_metadata = container_metadata["PoseEstimationSeries"]
        if keypoint in pose_estimation_series_metadata:
            pose_estimation_series_kwargs.update(pose_estimation_series_metadata[keypoint])

        # Set timestamps or rate
        timestamps_array = np.asarray(timestamps_cleaned).astype("float64", copy=False)
        rate = calculate_regular_series_rate(timestamps_array)
        if rate is None:
            pose_estimation_series_kwargs["timestamps"] = timestamps_array
        else:
            pose_estimation_series_kwargs["rate"] = rate
            pose_estimation_series_kwargs["starting_time"] = timestamps_array[0]

        # Create PoseEstimationSeries
        series = PoseEstimationSeries(**pose_estimation_series_kwargs)
        pose_estimation_series.append(series)

    # Get device information
    device_metadata_key = container_metadata["devices"][0]
    device_metadata = pose_estimation_metadata["Devices"][device_metadata_key]
    device_name = device_metadata["name"]

    # Create or get the device
    if device_name not in nwbfile.devices:
        camera = nwbfile.create_device(
            name=device_name,
            description=device_metadata["description"],
        )
    else:
        camera = nwbfile.devices[device_name]

    # Create PoseEstimation container with all available metadata
    pose_estimation_container = PoseEstimation(
        name=container_metadata["name"],
        pose_estimation_series=pose_estimation_series,
        description=container_metadata["description"],
        original_videos=container_metadata.get("original_videos", None),
        labeled_videos=container_metadata.get("labeled_videos", None),
        dimensions=container_metadata.get("dimensions", None),
        devices=[camera],
        scorer=container_metadata["scorer"],
        source_software=container_metadata["source_software"],
        source_software_version=container_metadata.get("source_software_version", None),
        skeleton=skeleton,
    )

    behavior_processing_module.add(pose_estimation_container)
    return nwbfile
