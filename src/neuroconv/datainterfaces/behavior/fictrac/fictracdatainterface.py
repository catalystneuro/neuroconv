from pathlib import Path
from typing import Optional

import numpy as np
from pynwb.behavior import CompassDirection, SpatialSeries
from pynwb.file import NWBFile

# from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface TODO: Add timing methods
from ....basedatainterface import BaseDataInterface
from ....tools import get_module, get_package
from ....utils import FilePathType, calculate_regular_series_rate


class FicTracDataInterface(BaseDataInterface):
    """Data interface for FicTrac datasets."""

    keywords = [
        "fictrack",
        "visual tracking",
        "fictive path",
        "spherical treadmill",
        "visual fixation",
    ]

    data_columns = [
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

    def __init__(
        self,
        file_path: FilePathType,
        verbose: bool = True,
    ):
        """
        Interface for writing fictract files to nwb.

        Parameters
        ----------
        file_path : FilePathType
            Path to the .dat file (the output of fictrac)
        verbose : bool, default: True
            controls verbosity. ``True`` by default.
        """
        self.file_path = Path(file_path)
        self.verbose = verbose
        self._timestamps = None
        super().__init__(file_path=file_path)

    def get_metadata(self):
        metadata = super().get_metadata()
        from datetime import datetime

        config_file = self.file_path.parent / "fictrac_config.txt"
        if config_file.exists():
            self._config_file = parse_fictrac_config(config_file)
            date_string = self._config_file["build_date"]
            date_object = datetime.strptime(date_string, "%b %d %Y")

            metadata["NWBFile"].update(
                session_start_time=date_object,
            )

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

        fictrac_data_df = pd.read_csv(self.file_path, sep=",", header=None, names=self.data_columns)

        # Get the timestamps
        timestamps_milliseconds = fictrac_data_df["timestamp"].values
        timestamps = timestamps_milliseconds / 1000.0
        rate = calculate_regular_series_rate(series=timestamps)  # Returns None if it is not regular
        write_timestamps = True
        if rate:
            write_timestamps = False

        processing_module = get_module(nwbfile=nwbfile, name="Behavior")

        # All the units in FicTrac are in radians, the radius of the ball required to transform to
        # Distances is not specified in the format
        compass_direction_container = CompassDirection(name="FicTrac")

        # Add rotation delta from camera
        rotation_delta_cam_columns = [
            "rotation_delta_x_cam",
            "rotation_delta_y_cam",
            "rotation_delta_z_cam",
        ]

        description = (
            "Change in orientation since last frame in radians from the camera frame. \n"
            "From the point of view of the camera:"
            "x: represents rotation of the axis to the right of the sphere (pitch) "
            "y: represents rotation of the axis under the sphere (yaw)"
            "z: represents rotation of the axis behind the sphere and into the picture (roll)"
        )

        df_cam_delta_rotation = fictrac_data_df[rotation_delta_cam_columns]
        data = df_cam_delta_rotation.to_numpy()
        reference_frame = "camera"
        spatial_seriess_kwargs = dict(
            name="SpatialSeriesRotationDeltaCameraFrame",
            data=data,
            reference_frame=reference_frame,
            unit="radians",
            description=description,
        )

        if write_timestamps:
            spatial_seriess_kwargs["timestamps"] = timestamps
        else:
            spatial_seriess_kwargs["rate"] = rate

        spatial_series = SpatialSeries(**spatial_seriess_kwargs)
        compass_direction_container.add_spatial_series(spatial_series)

        # Add rotation delta from lab
        rotation_delta_lab_columns = [
            "rotation_delta_x_lab",
            "rotation_delta_y_lab",
            "rotation_delta_z_lab",
        ]

        description = (
            "Change in orientation since last frame in radians from the lab frame. \n"
            "From the point of view of the lab:"
            "x: represents rotation of the axis in front of the subject (roll) "
            "y: represents rotation of the axis to the right of the subject (pitch)"
            "z: represents rotation of the axis under the subject (yaw)"
        )

        df_lab_delta_rotation = fictrac_data_df[rotation_delta_lab_columns]
        data = df_lab_delta_rotation.to_numpy()
        reference_frame = "lab"
        spatial_seriess_kwargs = dict(
            name="SpatialSeriesRotationDeltaLabFrame",
            data=data,
            reference_frame=reference_frame,
            unit="radians",
            description=description,
        )

        if write_timestamps:
            spatial_seriess_kwargs["timestamps"] = timestamps
        else:
            spatial_seriess_kwargs["rate"] = rate

        spatial_series = SpatialSeries(**spatial_seriess_kwargs)
        compass_direction_container.add_spatial_series(spatial_series)

        # Add absolute rotation from camera
        rotation_cam_columns = [
            "rotation_x_cam",
            "rotation_y_cam",
            "rotation_z_cam",
        ]

        description = (
            "Orientation in radians from the camera frame. \n"
            "From the point of view of the camera:"
            "x: represents rotation of the axis to the right of the sphere (pitch) "
            "y: represents rotation of the axis under the sphere (yaw)"
            "z: represents rotation of the axis behind the sphere and into the picture (roll)"
        )

        df_cam_rotation = fictrac_data_df[rotation_cam_columns]
        data = df_cam_rotation.to_numpy()
        reference_frame = "camera"
        spatial_seriess_kwargs = dict(
            name="SpatialSeriesRotationCameraFrame",
            data=data,
            reference_frame=reference_frame,
            unit="radians",
            description=description,
        )

        if write_timestamps:
            spatial_seriess_kwargs["timestamps"] = timestamps
        else:
            spatial_seriess_kwargs["rate"] = rate

        spatial_series = SpatialSeries(**spatial_seriess_kwargs)
        compass_direction_container.add_spatial_series(spatial_series)

        # Add absolute rotation from the lab
        rotation_lab_columns = [
            "rotation_x_lab",
            "rotation_y_lab",
            "rotation_z_lab",
        ]

        description = (
            "Orientation in radians from the lab frame. \n"
            "From the point of view of the lab:"
            "x: represents rotation of the axis in front of the subject (roll) "
            "y: represents rotation of the axis to the right of the subject (pitch)"
            "z: represents rotation of the axis under the subject (yaw)"
        )

        df_lab_rotation = fictrac_data_df[rotation_lab_columns]
        data = df_lab_rotation.to_numpy()
        reference_frame = "lab"
        spatial_seriess_kwargs = dict(
            name="SpatialSeriesRotationLabFrame",
            data=data,
            reference_frame=reference_frame,
            unit="radians",
            description=description,
        )

        if write_timestamps:
            spatial_seriess_kwargs["timestamps"] = timestamps
        else:
            spatial_seriess_kwargs["rate"] = rate

        spatial_series = SpatialSeries(**spatial_seriess_kwargs)
        compass_direction_container.add_spatial_series(spatial_series)

        # Add animal heading in radians
        animal_heading = fictrac_data_df["animal_heading"].values
        reference_frame = "lab"
        description = (
            "Animal heading in radians from the lab frame. "
            "This is calculated by integrating the yaw (z-axis) rotations across time."
        )

        spatial_seriess_kwargs = dict(
            name="SpatialSeriesAnimalHeading",
            data=animal_heading,
            reference_frame=reference_frame,
            unit="radians",
            description=description,
        )

        if write_timestamps:
            spatial_seriess_kwargs["timestamps"] = timestamps
        else:
            spatial_seriess_kwargs["rate"] = rate

        spatial_series = SpatialSeries(**spatial_seriess_kwargs)
        compass_direction_container.add_spatial_series(spatial_series)

        # Add movement direction
        movement_direction = fictrac_data_df["movement_direction"].values
        reference_frame = "lab"
        description = (
            "Instantaneous running direction (radians) of the animal in laboratory coordinates"
            "This is the direction the animal is moving in the lab frame. "
            "add to animal heading to get direction in the world."
            "This values is inferred by the rotation of the ball (roll and pitch)"
        )

        spatial_seriess_kwargs = dict(
            name="SpatialSeriesMovementDirection",
            reference_frame=reference_frame,
            data=movement_direction,
            unit="radians",
            description=description,
        )

        if write_timestamps:
            spatial_seriess_kwargs["timestamps"] = timestamps
        else:
            spatial_seriess_kwargs["rate"] = rate

        spatial_series = SpatialSeries(**spatial_seriess_kwargs)
        compass_direction_container.add_spatial_series(spatial_series)

        # Add movement speed
        movement_speed = fictrac_data_df["movement_speed"].values
        reference_frame = "lab"
        description = "Instantaneous running speed (radians/frame) of the animal."

        spatial_seriess_kwargs = dict(
            name="SpatialSeriesMovementSpeed",
            data=movement_speed,
            reference_frame=reference_frame,
            unit="radians",
            description=description,
        )

        if write_timestamps:
            spatial_seriess_kwargs["timestamps"] = timestamps
        else:
            spatial_seriess_kwargs["rate"] = rate

        spatial_series = SpatialSeries(**spatial_seriess_kwargs)
        compass_direction_container.add_spatial_series(spatial_series)

        # Add position in radians from the lab
        position_lab_columns = [
            "x_pos_radians_lab",
            "y_pos_radians_lab",
        ]

        description = (
            "x and y positions in the lab frame in radians. These values are inferred by integrating "
            "the rotation of the across time. "
        )

        df_lab_position = fictrac_data_df[position_lab_columns]
        data = df_lab_position.to_numpy()
        reference_frame = "lab"
        spatial_seriess_kwargs = dict(
            name="SpatialSeriesPosition",
            data=data,
            reference_frame=reference_frame,
            unit="radians",
            description=description,
        )

        if write_timestamps:
            spatial_seriess_kwargs["timestamps"] = timestamps
        else:
            spatial_seriess_kwargs["rate"] = rate

        spatial_series = SpatialSeries(**spatial_seriess_kwargs)
        compass_direction_container.add_spatial_series(spatial_series)

        # Add integrated motion
        integrated_motin_columns = [
            "forward_motion_lab",
            "side_motion_lab",
        ]

        description = "Integrated x/y position (radians) of the sphere in laboratory coordinates neglecting heading."

        df_integrated_motion = fictrac_data_df[integrated_motin_columns]
        data = df_integrated_motion.to_numpy()
        reference_frame = "lab"

        spatial_seriess_kwargs = dict(
            name="SpatialSeriesIntegratedMotion",
            data=data,
            unit="radians",
            reference_frame=reference_frame,
            description=description,
        )

        if write_timestamps:
            spatial_seriess_kwargs["timestamps"] = timestamps
        else:
            spatial_seriess_kwargs["rate"] = rate

        spatial_series = SpatialSeries(**spatial_seriess_kwargs)
        compass_direction_container.add_spatial_series(spatial_series)

        # Add error in rotation delta
        rotation_delta_error = fictrac_data_df["rotation_delta_error"].values
        reference_frame = "lab"
        description = "Error in rotation delta in radians from the lab frame"

        spatial_seriess_kwargs = dict(
            name="SpatialSeriesRotationDeltaError",
            data=rotation_delta_error,
            reference_frame=reference_frame,
            unit="radians",
            description=description,
        )

        if write_timestamps:
            spatial_seriess_kwargs["timestamps"] = timestamps

        else:
            spatial_seriess_kwargs["rate"] = rate

        spatial_series = SpatialSeries(**spatial_seriess_kwargs)
        compass_direction_container.add_spatial_series(spatial_series)

        # Add the compass direction container to the processing module
        processing_module.add_data_interface(compass_direction_container)


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
