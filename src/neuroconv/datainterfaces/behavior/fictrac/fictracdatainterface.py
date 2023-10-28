import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
        configuration_file_path: Optional[FilePathType] = None,
        verbose: bool = True,
    ):
        """
        Interface for writing FicTrac files to nwb.

        Parameters
        ----------
        file_path : a string or a path
            Path to the .dat file (the output of fictrac)
        radius : float, optional
            The radius of the ball in meters. If provided the data will be converted to meters and stored as such.
        configuration_file_path : a string or a path, optional
            Path to the .txt file with the configuration metadata. Usually called config.txt
        verbose : bool, default: True
            controls verbosity. ``True`` by default.
        """
        self.file_path = Path(file_path)
        self.verbose = verbose
        self.radius = radius
        super().__init__(file_path=file_path)

        self.configuration_file_path = configuration_file_path
        if self.configuration_file_path is None and (self.file_path.parent / "config.txt").is_file():
            self.configuration_file_path = self.file_path.parent / "config.txt"

        self.configuration_metadata = None
        if self.configuration_file_path is not None:
            self.configuration_metadata = parse_fictrac_config(file_path=configuration_file_path)

        self._timestamps = None
        self._starting_time = None

    def get_metadata(self):
        metadata = super().get_metadata()

        session_start_time = extract_session_start_time(self.file_path)
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

        # The first row only contains the session start time and invalid data
        fictrac_data_df = pd.read_csv(self.file_path, sep=",", skiprows=1, header=None, names=self.columns_in_dat_file)

        # Get the timestamps
        timestamps = self.get_timestamps()

        starting_time = timestamps[0]

        # Note: Returns timestamps from the Graber classes in fictrac library. The most common is for them to be
        # video timestamp extracted with OpenCV with all the caveats that come with it.
        rate = calculate_regular_series_rate(series=timestamps)  # Returns None if the series is not regular
        if rate:
            write_timestamps = False
        else:
            write_timestamps = True

        position_container = Position(name="FicTrac")
        if self.configuration_metadata is not None:
            comments = f"configuration_metadata = {json.dumps(self.configuration_metadata)}"

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
                data = data * self.radius
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

        # Add the compass direction container to the processing module
        processing_module = get_module(nwbfile=nwbfile, name="Behavior")
        processing_module.add_data_interface(position_container)

    def get_original_timestamps(self):
        import pandas as pd

        timestamp_index = self.columns_in_dat_file.index("timestamp")

        fictrac_data_df = pd.read_csv(self.file_path, sep=",", skiprows=1, header=None, usecols=[timestamp_index])

        return fictrac_data_df[timestamp_index].values / 1000.0

    def get_timestamps(self):
        timestamps = self._timestamps if self._timestamps is not None else self.get_original_timestamps()
        if self._starting_time is not None:
            # Shift the timestamps to the starting time such that timestamps[0] == self._starting_time
            # timestamps = timestamps - timestamps[0] + self._starting_time
            timestamps = timestamps + self._starting_time

        return timestamps

    def set_aligned_timestamps(self, aligned_timestamps):
        self._timestamps = aligned_timestamps

    def set_aligned_starting_time(self, aligned_starting_time):
        self._starting_time = aligned_starting_time


def extract_session_start_time(file_path: FilePathType) -> datetime:
    """
    Lazily extract the session start datetime from a FicTrac data file.

    In FicTrac the column 22 in the data has the timestamps which are given in milliseconds since the epoch.

    The epoch in Linux is 1970-01-01 00:00:00 UTC.
    """
    with open(file_path, "r") as file:
        # Read the first data line
        first_line = file.readline()

        # Split by comma and extract the timestamp (the 22nd column)
        utc_timestamp = float(first_line.split(",")[21]) / 1000.0  # Transform to seconds

    utc_datetime = datetime.utcfromtimestamp(utc_timestamp).replace(tzinfo=timezone.utc)

    return utc_datetime


def parse_fictrac_config(file_path: str) -> dict:
    """
    Parse a FicTrac configuration file and return a dictionary of its parameters.

    Parameters
    ----------
    file_path : str, Path
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

    KEY_PARSERS = {
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

        parser = KEY_PARSERS.get(key, lambda x: x)
        parsed_config[key] = parser(value)
    return parsed_config
