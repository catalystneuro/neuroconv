from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

import numpy as np
from pynwb.behavior import Position, SpatialSeries
from pynwb.file import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module
from ....utils import FilePathType, calculate_regular_series_rate


class FicTracDataInterface(BaseTemporalAlignmentInterface):
    """Data interface for FicTrac datasets."""

    keywords = [
        "fictrack",
        "visual tracking",
        "fictive path",
        "spherical treadmill",
        "visual fixation",
    ]

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

    def __init__(
        self,
        file_path: FilePathType,
        radius: Optional[float] = None,
        verbose: bool = True,
    ):
        """
        Interface for writing FicTrac files to nwb.

        Parameters
        ----------
        file_path : a string or a path
            Path to the .dat file (the output of fictrac)
        radius : float, optional
            The radius of the ball in meters. If provided the radius is stored as a conversion factor
            and the units are set to meters. If not provided the units are set to radians.
        verbose : bool, default: True
            controls verbosity. ``True`` by default.
        """
        self.file_path = Path(file_path)
        self.verbose = verbose
        self._timestamps = None
        self.radius = radius
        self.configuration_file_path = None
        super().__init__(file_path=file_path)

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
        metadata: dict
            metadata info for constructing the nwb file (optional).
        """

        import pandas as pd

        fictrac_data_df = pd.read_csv(self.file_path, sep=",", header=None, names=self.columns_in_dat_file)

        # Get the timestamps
        timestamps = self.get_timestamps()
        starting_time = timestamps[0]

        # Note: The last values of the timestamps look very irregular for the sample file in catalyst neuro gin repo
        # The reason, most likely, is that FicTrac is relying on OpenCV to get the timestamps from the video
        # In my experience, OpenCV is not very accurate with the timestamps at the end of the video.
        rate = calculate_regular_series_rate(series=timestamps)  # Returns None if the series is not regular
        if rate:
            write_timestamps = False
        else:
            write_timestamps = True

        position_container = Position(name="FicTrac")

        for data_dict in self.column_to_nwb_mapping.values():
            spatial_series_kwargs = dict(
                name=data_dict["spatial_series_name"],
                description=data_dict["description"],
                reference_frame=data_dict["reference_frame"],
            )

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
        processing_module.add_data_interface(position_container)

    def get_original_timestamps(self):
        """
        Retrieve and correct timestamps from a FicTrac data file.

        This function addresses two specific issues with timestamps in FicTrac data:

        1. Resetting Initial Timestamp:
        In some instances, FicTrac replaces the initial timestamp (0) with the system time. This commonly occurs
        when the data source is a video file, and OpenCV reports the first timestamp as 0. Since OpenCV also
        uses 0 as a marker for invalid values, FicTrac defaults to system time in that case. This leads to
        inconsistent timestamps like [system_time, t1, t2, t3, ...]. The function corrects this by resetting the
        first timestamp back to 0 when a negative difference is detected between the first two timestamps.

        2. Re-centering Unix Epoch Time:
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
    file_path: FilePathType,
    configuration_file_path: Optional[FilePathType] = None,
) -> Union[datetime, None]:
    """
    Extract the session start time from a FicTrac data file or its configuration file.

    The session start time is determined from the data file if the timestamps are in Unix epoch format. If not, the
    function defaults to extracting the date from the configuration file and assuming that the start time is midnight.
    If neither of these methods works, the function returns None.

    The session start time, has two different meanings depending on the source of the FicTrac data:
    - For video file sources (.avi, .mp4, etc), the session start time corresponds to the time when the
    FicTrac analysis commenced. That is, the session start time reflects the analysis time rather than
    the actual start of the experiment.
    - For camera sources (such as PGR or Basler), the session start time is either the time reported by the camera
    or the system time if the camera's SDK does not provide timestamps to Fictrac. In both cases, this time is
    the experiment start time, barring synchronization issues.

    Parameters
    ----------
    file_path : FilePathType
        Path to the FicTrac data file.
    configuration_file_path : Optional[FilePathType]
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


# TODO: Parse probably will do this in a simpler way.
def parse_fictrac_config(filename) -> dict:
    """
    Parse a FicTrac configuration file and return a dictionary of its parameters. See the
    definition of the parameters in https://github.com/rjdmoore/fictrac/blob/master/doc/params.md for more information.

    Parameters
    ----------
    filename : str, Path
        Path to the configuration file.

    Returns
    -------
    dict
        A dictionary where the keys are the parameter names and the values are the parameter values.

    Raises
    ------
    IOError
        If the file cannot be read.
    ValueError
        If a value in the file cannot be converted to the expected type.

    Examples
    --------
    >>> config = parse_fictrac_config('/path/to/config.txt')
    >>> print(config['src_fn'])
    'sample.mp4'
    """
    import re

    # Tyiping information based on https://github.com/rjdmoore/fictrac/blob/master/doc/params.md
    type_info = {
        "src_fn": "string OR int",
        "vfov": "float",
        "do_display": "bool",
        "save_debug": "bool",
        "save_raw": "bool",
        "sock_host": "string",
        "sock_port": "int",
        "com_port": "string",
        "com_baud": "int",
        "fisheye": "bool",
        "q_factor": "int",
        "src_fps": "float",
        "max_bad_frames": "int",
        "opt_do_global": "bool",
        "opt_max_err": "float",
        "thr_ratio": "float",
        "thr_win_pc": "float",
        "vid_codec": "string",
        "sphere_map_fn": "string",
        "opt_max_evals": "int",
        "opt_bound": "float",
        "opt_tol": "float",
        "c2a_cnrs_xy": "vec<int>",
        "c2a_cnrs_yz": "vec<int>",
        "c2a_cnrs_xz": "vec<int>",
        "c2a_src": "string",
        "c2a_r": "vec<float>",
        "c2a_t": "vec<float>",
        "roi_circ": "vec<int>",
        "roi_c": "vec<float>",
        "roi_r": "float",
        "roi_ignr": "vec<vec<int>>",
    }

    # Function to parse value based on type information
    def parse_value(value_str, type_str):
        value_str = value_str.strip()
        if type_str == "bool":
            return value_str == "y"
        elif "vec" in type_str:
            # remove curly braces and split by comma
            values = value_str.replace("{", "").replace("}", "").split(",")
            if "int" in type_str:
                return [int(val) for val in values]
            elif "float" in type_str:
                return [float(val) for val in values]
        elif type_str == "int":
            return int(value_str)
        elif type_str == "float":
            return float(value_str)
        else:
            return value_str

    # Open and read the file
    with open(filename, "r") as f:
        file_lines = f.readlines()

    parsed_config = {}

    header_line = file_lines[0]
    version, build_date = re.search(
        r"FicTrac (v[0-9.]+) config file \(build date ([A-Za-z0-9 ]+)\)", header_line
    ).groups()
    parsed_config["version"] = version
    parsed_config["build_date"] = build_date

    # Parse the file
    file_content = file_lines[1:]
    for line in file_content[1:]:  # Skip the first line
        key, value_str = line.split(":")
        key = key.strip()
        value_str = value_str.strip()
        if key in type_info:
            parsed_config[key] = parse_value(value_str, type_info[key])
        else:
            raise ValueError(f"Unknown key {key} in the file.")

    return parsed_config
