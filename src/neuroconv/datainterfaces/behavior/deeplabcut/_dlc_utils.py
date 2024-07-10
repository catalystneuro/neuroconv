import datetime
import importlib
import os
import pickle
import warnings
from pathlib import Path
from platform import python_version

import cv2
import numpy as np
import pandas as pd
import yaml
from hdmf.build.warnings import DtypeConversionWarning
from ndx_pose import PoseEstimation, PoseEstimationSeries
from packaging.version import Version  # Installed with setuptools
from pynwb import NWBHDF5IO, NWBFile
from ruamel.yaml import YAML


def _read_config(configname):
    """
    Reads structured config file defining a project.
    """
    ruamelFile = YAML()
    path = Path(configname)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                cfg = ruamelFile.load(f)
                curr_dir = os.path.dirname(configname)
                if cfg["project_path"] != curr_dir:
                    cfg["project_path"] = curr_dir
        except Exception as err:
            if len(err.args) > 2:
                if err.args[2] == "could not determine a constructor for the tag '!!python/tuple'":
                    with open(path, "r") as ymlfile:
                        cfg = yaml.load(ymlfile, Loader=yaml.SafeLoader)
                else:
                    raise

    else:
        raise FileNotFoundError(
            "Config file is not found. Please make sure that the file exists and/or that you passed the path of the config file correctly!"
        )
    return cfg


def _get_movie_timestamps(movie_file, VARIABILITYBOUND=1000, infer_timestamps=True):
    """
    Return numpy array of the timestamps for a video.

    Parameters
    ----------
    movie_file : str
        Path to movie_file
    """
    # TODO: consider moving this to DLC, and actually extract alongside video analysis!

    reader = cv2.VideoCapture(movie_file)
    timestamps = []
    for _ in range(len(reader)):
        _ = reader.read()
        timestamps.append(reader.get(cv2.CAP_PROP_POS_MSEC))

    timestamps = np.array(timestamps) / 1000  # Convert to seconds

    if np.nanvar(np.diff(timestamps)) < 1.0 / reader.fps * 1.0 / VARIABILITYBOUND:
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


def _ensure_individuals_in_header(df, dummy_name):
    if "individuals" not in df.columns.names:
        # Single animal project -> add individual row to
        # the header of single animal projects.
        temp = pd.concat({dummy_name: df}, names=["individuals"], axis=1)
        df = temp.reorder_levels(["scorer", "individuals", "bodyparts", "coords"], axis=1)
    return df


def _get_pes_args(config_file, h5file, individual_name, infer_timestamps=True):
    if "DLC" not in h5file or not h5file.endswith(".h5"):
        raise IOError("The file passed in is not a DeepLabCut h5 data file.")

    cfg = _read_config(config_file)

    vidname, scorer = os.path.split(h5file)[-1].split("DLC")
    scorer = "DLC" + os.path.splitext(scorer)[0]
    video = None

    df = _ensure_individuals_in_header(pd.read_hdf(h5file), individual_name)

    # Fetch the corresponding metadata pickle file
    paf_graph = []
    filename, _ = os.path.splitext(h5file)
    for i, c in enumerate(filename[::-1]):
        if c.isnumeric():
            break
    if i > 0:
        filename = filename[:-i]
    metadata_file = filename + "_meta.pickle"
    if os.path.isfile(metadata_file):
        with open(metadata_file, "rb") as file:
            metadata = pickle.load(file)
        test_cfg = metadata["data"]["DLC-model-config file"]
        paf_graph = test_cfg.get("partaffinityfield_graph", [])
        if paf_graph:
            paf_inds = test_cfg.get("paf_best")
            if paf_inds is not None:
                paf_graph = [paf_graph[i] for i in paf_inds]
    else:
        warnings.warn("Metadata not found...")

    for video_path, params in cfg["video_sets"].items():
        if vidname in video_path:
            video = video_path, params["crop"]
            break

    if video is None:
        warnings.warn(f"The video file corresponding to {h5file} could not be found...")
        video = "fake_path", "0, 0, 0, 0"

        timestamps = df.index.tolist()  # setting timestamps to dummy TODO: extract timestamps in DLC?
    else:
        timestamps = _get_movie_timestamps(video[0], infer_timestamps=infer_timestamps)
    return scorer, df, video, paf_graph, timestamps, cfg


def _write_pes_to_nwbfile(
    nwbfile,
    animal,
    df_animal,
    scorer,
    video,  # Expects this to be a tuple; first index is string path, second is the image shape as "0, width, 0, height"
    paf_graph,
    timestamps,
    exclude_nans,
):
    pose_estimation_series = []
    for kpt, xyp in df_animal.groupby(level="bodyparts", axis=1, sort=False):
        data = xyp.to_numpy()

        if exclude_nans:
            # exclude_nans is inverse infer_timestamps. if not infer, there may be nans
            data = data[~np.isnan(timestamps)]
            timestamps_cleaned = timestamps[~np.isnan(timestamps)]
        else:
            timestamps_cleaned = timestamps

        pes = PoseEstimationSeries(
            name=f"{animal}_{kpt}",
            description=f"Keypoint {kpt} from individual {animal}.",
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
    pe = PoseEstimation(
        pose_estimation_series=pose_estimation_series,
        description="2D keypoint coordinates estimated using DeepLabCut.",
        original_videos=[video[0]],
        # TODO check if this is a mandatory arg in ndx-pose (can skip if video is not found_
        dimensions=[list(map(int, video[1].split(",")))[1::2]],
        scorer=scorer,
        source_software="DeepLabCut",
        source_software_version=deeplabcut_version,
        nodes=[pes.name for pes in pose_estimation_series],
        edges=paf_graph if paf_graph else None,
    )
    if "behavior" in nwbfile.processing:
        behavior_pm = nwbfile.processing["behavior"]
    else:
        behavior_pm = nwbfile.create_processing_module(name="behavior", description="processed behavioral data")
    behavior_pm.add(pe)
    return nwbfile


def write_subject_to_nwb(nwbfile, h5file, individual_name, config_file):
    """
    Given, subject name, write h5file to an existing nwbfile.

    Parameters
    ----------
    nwbfile: pynwb.NWBFile
        nwbfile to write the subject specific pose estimation series.
    h5file : str
        Path to a h5 data file
    individual_name : str
        Name of the subject (whose pose is predicted) for single-animal DLC project.
        For multi-animal projects, the names from the DLC project will be used directly.
    config_file : str
        Path to a project config.yaml file
    config_dict : dict
        dict containing configuration options. Provide this as alternative to config.yml file.

    Returns
    -------
    nwbfile: pynwb.NWBFile
        nwbfile with pes written in the behavior module
    """
    scorer, df, video, paf_graph, timestamps, _ = _get_pes_args(config_file, h5file, individual_name)
    df_animal = df.groupby(level="individuals", axis=1).get_group(individual_name)
    return _write_pes_to_nwbfile(nwbfile, individual_name, df_animal, scorer, video, paf_graph, timestamps)


def convert_h5_to_nwb(config, h5file, individual_name="ind1", infer_timestamps=True):
    """
    Convert a DeepLabCut (DLC) video prediction, h5 data file to Neurodata Without Borders (NWB). Also
    takes project config, to store relevant metadata.

    Parameters
    ----------
    config : str
        Path to a project config.yaml file

    h5file : str
        Path to a h5 data file

    individual_name : str
        Name of the subject (whose pose is predicted) for single-animal DLC project.
        For multi-animal projects, the names from the DLC project will be used directly.

    infer_timestamps : bool
        Default True. Uses framerate to infer the timestamps returned as 0 from OpenCV.
        If False, exclude these frames from resulting NWB file.

    TODO: allow one to overwrite those names, with a mapping?

    Returns
    -------
    list of str
        List of paths to the newly created NWB data files.
        By default NWB files are stored in the same folder as the h5file.

    """
    scorer, df, video, paf_graph, timestamps, cfg = _get_pes_args(
        config, h5file, individual_name, infer_timestamps=infer_timestamps
    )
    output_paths = []
    for animal, df_ in df.groupby(level="individuals", axis=1):
        nwbfile = NWBFile(
            session_description=cfg["Task"],
            experimenter=cfg["scorer"],
            identifier=scorer,
            session_start_time=datetime.datetime.now(datetime.timezone.utc),
        )

        # TODO Store the test_pose_config as well?
        nwbfile = _write_pes_to_nwbfile(
            nwbfile, animal, df_, scorer, video, paf_graph, timestamps, exclude_nans=(not infer_timestamps)
        )
        output_path = h5file.replace(".h5", f"_{animal}.nwb")
        with warnings.catch_warnings(), NWBHDF5IO(output_path, mode="w") as io:
            warnings.filterwarnings("ignore", category=DtypeConversionWarning)
            io.write(nwbfile)
        output_paths.append(output_path)

    return output_paths
