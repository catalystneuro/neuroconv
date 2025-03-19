import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

import numpy as np
from pydantic import FilePath, validate_call
from pynwb.behavior import Position, SpatialSeries
from pynwb.file import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module
from ....utils import calculate_regular_series_rate


class FicTracDataInterface(BaseTemporalAlignmentInterface):
    """Data interface for FicTrac datasets."""

    display_name = "FicTrac"
    keywords = (
        "fictrack",
        "visual tracking",
        "fictive path",
        "spherical treadmill",
        "visual fixation",
    )
    associated_suffixes = (".dat",)
    info = "Interface for FicTrac .dat files."

    timestamps_column = 21
    # Columns in the .dat binary file with the data. The full description of the header can be found in:
    # https://github.com/rjdmoore/fictrac/blob/master/doc/data_header.txt
    columns_in_dat_file = [
        "frame_counter",
        "rotation_delta_x_cam",
        "rotation_delta_y_cam",
        "rotation_delta_z_cam",
        "rotation_delta_error",
        "rotation_delta_x_lab",
        "rotation_delta_y_lab",
        "rotation_delta_z_lab",
        "rotation_x_cam",
        "rotation_y_cam",
        "rotation_z_cam",
        "rotation_x_lab",
        "rotation_y_lab",
        "rotation_z_lab",
        "x_pos_radians_lab",
        "y_pos_radians_lab",
        "animal_heading",
        "movement_direction",
        "movement_speed",
        "forward_motion_lab",
        "side_motion_lab",
        "timestamp",
        "sequence_counter",
        "delta_timestamp",
        "alt_timestamp",
    ]

    column_to_nwb_mapping = spatial_series_descriptions = {
        "rotation_delta_cam": {
            "column_in_dat_file": ["rotation_delta_x_cam", "rotation_delta_y_cam", "rotation_delta_z_cam"],
            "spatial_series_name": "SpatialSeriesRotationDeltaCameraFrame",
            "description": (
                "Change in orientation since last frame from the camera's perspective. "
                "x: rotation to the sphere's right (pitch), "
                "y: rotation under the sphere (yaw), "
                "z: rotation behind the sphere (roll)"
            ),
            "reference_frame": "camera",
        },
        "rotation_delta_lab": {
            "column_in_dat_file": ["rotation_delta_x_lab", "rotation_delta_y_lab", "rotation_delta_z_lab"],
            "spatial_series_name": "SpatialSeriesRotationDeltaLabFrame",
            "description": (
                "Change in orientation since last frame from the lab's perspective. "
                "x: rotation in front of subject (roll), "
                "y: rotation to subject's right (pitch), "
                "z: rotation under the subject (yaw)"
            ),
            "reference_frame": "lab",
        },
        "rotation_cam": {
            "column_in_dat_file": ["rotation_x_cam", "rotation_y_cam", "rotation_z_cam"],
            "spatial_series_name": "SpatialSeriesRotationCameraFrame",
            "description": (
                "Orientation in radians from the camera's perspective. "
                "x: rotation to the sphere's right (pitch), "
                "y: rotation under the sphere (yaw), "
                "z: rotation behind the sphere (roll)"
            ),
            "reference_frame": "camera",
        },
        "rotation_lab": {
            "column_in_dat_file": ["rotation_x_lab", "rotation_y_lab", "rotation_z_lab"],
            "spatial_series_name": "SpatialSeriesRotationLabFrame",
            "description": (
                "Orientation in radians from the lab's perspective. "
                "x: rotation in front of subject (roll), "
                "y: rotation to subject's right (pitch), "
                "z: rotation under the subject (yaw)"
            ),
            "reference_frame": "lab",
        },
        "animal_heading": {
            "column_in_dat_file": ["animal_heading"],
            "spatial_series_name": "SpatialSeriesAnimalHeading",
            "description": "Animal's heading direction in radians from the lab's perspective.",
            "reference_frame": "lab",
        },
        "movement_direction": {
            "column_in_dat_file": ["movement_direction"],
            "spatial_series_name": "SpatialSeriesMovementDirection",
            "description": (
                "Instantaneous running direction of the animal in the lab coordinates. "
                "Direction inferred by the ball's rotation (roll and pitch)"
            ),
            "reference_frame": "lab",
        },
        "movement_speed": {
            "column_in_dat_file": ["movement_speed"],
            "spatial_series_name": "SpatialSeriesMovementSpeed",
            "description": "Instantaneous running speed of the animal in radians per frame.",
            "reference_frame": "lab",
        },
        "position_lab": {
            "column_in_dat_file": ["x_pos_radians_lab", "y_pos_radians_lab"],
            "spatial_series_name": "SpatialSeriesPosition",
            "description": (
                "x and y positions in the lab frame in radians, inferred by integrating " "the rotation over time."
            ),
            "reference_frame": "lab",
        },
        "integrated_motion": {
            "column_in_dat_file": ["forward_motion_lab", "side_motion_lab"],
            "spatial_series_name": "SpatialSeriesIntegratedMotion",
            "description": ("Integrated x/y position of the sphere in laboratory coordinates, neglecting heading."),
            "reference_frame": "lab",
        },
        "rotation_delta_error": {
            "spatial_series_name": "SpatialSeriesRotationDeltaError",
            "column_in_dat_file": ["rotation_delta_error"],
            "description": "Error in rotation delta in radians from the lab's perspective.",
            "reference_frame": "lab",
        },
    }

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .dat file (the output of fictrac)"
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        radius: Optional[float] = None,
        configuration_file_path: Optional[FilePath] = None,
        verbose: bool = False,
    ):
        """
        Interface for writing FicTrac files to nwb.

        Parameters
        ----------
        file_path : FilePath
            Path to the .dat file (the output of fictrac)
        radius : float, optional
            The radius of the ball in meters. If provided the radius is stored as a conversion factor
            and the units are set to meters. If not provided the units are set to radians.
        configuration_file_path : FilePath, optional
            Path to the .txt file with the configuration metadata. Usually called config.txt
        verbose : bool, default: False
            controls verbosity. ``True`` by default.
        """
        self.file_path = Path(file_path)
        self.verbose = verbose
        self.radius = radius
        self.configuration_file_path = None
        super().__init__(file_path=file_path)

        self.configuration_file_path = configuration_file_path
        if self.configuration_file_path is None and (self.file_path.parent / "config.txt").is_file():
            self.configuration_file_path = self.file_path.parent / "config.txt"

        self.configuration_metadata = None
        if self.configuration_file_path is not None:
            self.configuration_metadata = parse_fictrac_config(file_path=self.configuration_file_path)

        self._timestamps = None
        self._starting_time = None

    def get_metadata(self):
        metadata = super().get_metadata()

        session_start_time = extract_session_start_time(
            file_path=self.file_path,
            configuration_file_path=self.configuration_file_path,
        )
        if session_start_time:
            metadata["NWBFile"].update(session_start_time=session_start_time)

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
    ):
        """
        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict, optional
            metadata info for constructing the nwb file.
        """
        import pandas as pd

        fictrac_data_df = pd.read_csv(self.file_path, sep=",", header=None, names=self.columns_in_dat_file)

        # Get the timestamps
        timestamps = self.get_timestamps()
        starting_time = timestamps[0]

        # Note: Returns the timestamps from the sources in FicTrac (.e.g OpenCV videos, PGR or Basler). The most common  is OpenCV with all the caveats that come with it.
        # video timestamp extracted with OpenCV with all the caveats that come with it.
        rate = calculate_regular_series_rate(series=timestamps)  # Returns None if the series is not regular
        if rate:
            write_timestamps = False
        else:
            write_timestamps = True

        position_container = Position(name="FicTrac")
        # TODO: make FicTrac extension of the Position container to attach these specific attributes with documentation
        if self.configuration_metadata is not None:
            comments = json.dumps(self.configuration_metadata)

        for data_dict in self.column_to_nwb_mapping.values():
            spatial_series_kwargs = dict(
                name=data_dict["spatial_series_name"],
                description=data_dict["description"],
                reference_frame=data_dict["reference_frame"],
            )

            if self.configuration_metadata is not None:
                spatial_series_kwargs["comments"] = comments

            column_in_dat_file = data_dict["column_in_dat_file"]
            data = fictrac_data_df[column_in_dat_file].to_numpy()
            if self.radius is not None:
                spatial_series_kwargs["conversion"] = self.radius
                units = "meters"
            else:
                units = "radians"

            spatial_series_kwargs.update(data=data, unit=units)

            if write_timestamps:
                spatial_series_kwargs["timestamps"] = timestamps
            else:
                spatial_series_kwargs["rate"] = rate
                spatial_series_kwargs["starting_time"] = starting_time

            # Create the spatial series and add it to the container
            spatial_series = SpatialSeries(**spatial_series_kwargs)
            position_container.add_spatial_series(spatial_series)

        # Add the container to the processing module
        processing_module = get_module(nwbfile=nwbfile, name="behavior")
        processing_module.add(position_container)

    def get_original_timestamps(self):
        """
        Retrieve and correct timestamps from a FicTrac data file.

        This function addresses two specific issues with timestamps in FicTrac data:

        1. Resetting Initial Timestamp
           In some instances, FicTrac replaces the initial timestamp (0) with the system time. This commonly occurs
           when the data source is a video file, and OpenCV reports the first timestamp as 0. Since OpenCV also
           uses 0 as a marker for invalid values, FicTrac defaults to system time in that case. This leads to
           inconsistent timestamps like [system_time, t1, t2, t3, ...]. The function corrects this by resetting the
           first timestamp back to 0 when a negative difference is detected between the first two timestamps.
        2. Re-centering Unix Epoch Time
           If timestamps are in Unix epoch time format (time since 1970-01-01 00:00:00 UTC), this function re-centers
           the time series by subtracting the first timestamp. This adjustment ensures that timestamps represent the
           elapsed time since the start of the experiment rather than the Unix epoch. This case appears when one of the
           sources of data in FicTrac (such as PGR or Basler) lacks a timestamp extraction method. FicTrac
           then falls back to using the system time, which is in Unix epoch format.

        Returns
        -------
        np.ndarray
            An array of corrected timestamps, in seconds.

        Notes
        -----
        - The issue of the initial timestamp replacement appears in FicTrac 2.1.1 and earlier versions.
        - Re-centering is essential for timestamps in Unix epoch format as timestamps in an NWB file must be relative
        to the start of the session. The heuristic here is to check if the first timestamp is larger than the length
        of a 10-year experiment in seconds. If so, it's assumed that the timestamps are in Unix epoch format.

        References
        ----------
        Issue discussion on FicTrac's timestamp inconsistencies:
        https://github.com/rjdmoore/fictrac/issues/29
        """

        import pandas as pd

        fictrac_data_df = pd.read_csv(self.file_path, sep=",", header=None, usecols=[self.timestamps_column])

        timestamps = fictrac_data_df[self.timestamps_column].values / 1000.0  # Transform to seconds

        # Correct for the case when only the first timestamp was replaced by system time
        first_difference = timestamps[1] - timestamps[0]
        if first_difference < 0:
            timestamps[0] = 0.0

        # Heuristic to test if timestamps are in Unix epoch
        length_in_seconds_of_a_10_year_experiment = 10 * 365 * 24 * 60 * 60
        all_timestamps_are_in_unix_epoch = np.all(timestamps > length_in_seconds_of_a_10_year_experiment)
        if all_timestamps_are_in_unix_epoch:
            timestamps = timestamps - timestamps[0]
        # TODO: If we agree to ALWAYS constrain timestamps to be relative to the start of the session, we can
        # Always shift here and remove the heuristic above.

        return timestamps

    def get_timestamps(self):
        timestamps = self._timestamps if self._timestamps is not None else self.get_original_timestamps()
        if self._starting_time is not None:
            timestamps = timestamps + self._starting_time

        return timestamps

    def set_aligned_timestamps(self, aligned_timestamps):
        self._timestamps = aligned_timestamps

    def set_aligned_starting_time(self, aligned_starting_time):
        self._starting_time = aligned_starting_time


def extract_session_start_time(
    file_path: FilePath,
    configuration_file_path: Optional[FilePath] = None,
) -> Union[datetime, None]:
    """
    Extract the session start time from a FicTrac data file or its configuration file.

    The session start time is determined from the data file if the timestamps are in Unix epoch format. If not, the
    function defaults to extracting the date from the configuration file and assuming that the start time is midnight.
    If neither of these methods works, the function returns None.

    The session start time, has two different meanings depending on the source of the FicTrac data:
    - For video file sources (.avi, .mp4, etc.), the session start time corresponds to the time when the
    FicTrac analysis commenced. That is, the session start time reflects the analysis time rather than
    the actual start of the experiment.
    - For camera sources (such as PGR or Basler), the session start time is either the time reported by the camera
    or the system time if the camera's SDK does not provide timestamps to Fictrac. In both cases, this time is
    the experiment start time, barring synchronization issues.

    Parameters
    ----------
    file_path : FilePath
        Path to the FicTrac data file.
    configuration_file_path : FilePath, optional
        Path to the FicTrac configuration file. If omitted, the function defaults to searching for
        "fictrac_config.txt" in the same directory as the data file.

    Returns
    -------
    datetime | None
        The session start time of in UTC as a datetime object. `None` if the session start time cannot be extracted.

    """
    with open(file_path, "r") as file:
        first_line = file.readline()

    timestamps_column = FicTracDataInterface.timestamps_column
    first_timestamp = float(first_line.split(",")[timestamps_column]) / 1000.0  # Convert to seconds

    # Heuristic to test if timestamps are in Unix epoch
    length_in_seconds_of_a_10_year_experiment = 10 * 365 * 24 * 60 * 60
    if first_timestamp > length_in_seconds_of_a_10_year_experiment:
        utc_timestamp = first_timestamp
        return datetime.utcfromtimestamp(utc_timestamp).replace(tzinfo=timezone.utc)

    if configuration_file_path is None:
        configuration_file_path = file_path.parent / "fictrac_config.txt"
    if configuration_file_path.is_file():
        configuration_file = parse_fictrac_config(configuration_file_path)
        session_start_time = datetime.strptime(configuration_file.get("build_date", ""), "%b %d %Y")
        # Set the time to midnight UTC from the extracted date
        return session_start_time.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

    return None


def parse_fictrac_config(file_path: FilePath) -> dict:
    """
    Parse a FicTrac configuration file and return a dictionary of its parameters.

    Parameters
    ----------
    file_path : FilePath
        Path to the configuration file in txt format.

    Returns
    -------
    dict
        A dictionary where the keys are the parameter names and the values are the parameter values.

    """

    def parse_bool(x):
        return x.lower() == "y"

    def parse_vec_int(x):
        return [int(val) for val in x.replace("{", "").replace("}", "").split(",")]

    def parse_vec_float(x):
        return [float(val) for val in x.replace("{", "").replace("}", "").split(",")]

    def parse_roi_ignr(x):
        innner_vectors = x.strip("{}").strip().split("}, {")
        return [parse_vec_int(group) for group in innner_vectors]

    def parse_int_or_string(x):
        value = int(x) if x.isdigit() else x
        return value

    key_parsers = {
        "src_fn": parse_int_or_string,
        "vfov": float,
        "do_display": parse_bool,
        "save_debug": parse_bool,
        "save_raw": parse_bool,
        "sock_port": int,
        "com_baud": int,
        "fisheye": parse_bool,
        "q_factor": int,
        "src_fps": float,
        "max_bad_frames": int,
        "opt_do_global": parse_bool,
        "opt_max_err": float,
        "thr_ratio": float,
        "thr_win_pc": float,
        "opt_max_evals": int,
        "opt_bound": float,
        "opt_tol": float,
        "c2a_cnrs_xy": parse_vec_int,
        "c2a_cnrs_yz": parse_vec_int,
        "c2a_cnrs_xz": parse_vec_int,
        "c2a_r": parse_vec_float,
        "c2a_t": parse_vec_float,
        "roi_circ": parse_vec_int,
        "roi_c": parse_vec_float,
        "roi_r": float,
        "roi_ignr": parse_roi_ignr,
    }

    # Open and read the file
    with open(file_path, "r") as f:
        file_lines = f.readlines()

    parsed_config = {}

    # Parse header line
    header_line = file_lines[0]

    version, build_date = re.search(
        r"FicTrac (v[0-9.]+) config file \(build date ([A-Za-z0-9 ]+)\)", header_line
    ).groups()
    parsed_config["version"] = version
    parsed_config["build_date"] = build_date

    # Parse the configuration lines
    configuration_lines = (line for line in file_lines[1:] if ":" in line)
    for line in configuration_lines:
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        parser = key_parsers.get(key, lambda x: x)
        parsed_config[key] = parser(value)
    return parsed_config
