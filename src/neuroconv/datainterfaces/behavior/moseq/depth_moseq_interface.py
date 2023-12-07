"""Primary class for converting MoSeq Extraction data."""
from datetime import datetime
from pytz import timezone

import h5py
import numpy as np
from hdmf.backends.hdf5.h5_utils import H5DataIO
from pynwb import TimeSeries, NWBFile
from pynwb.image import GrayscaleImage, ImageMaskSeries
from pynwb.behavior import (
    CompassDirection,
    Position,
    SpatialSeries,
)
from ndx_depth_moseq import DepthImageSeries, MoSeqExtractGroup, MoSeqExtractParameterGroup

from .....basedatainterface import BaseDataInterface
from .....tools import nwb_helpers


def _convert_timestamps_to_seconds(timestamps: np.ndarray[int], scaling_factor: float, maximum_timestamp: int) -> np.ndarray:
    """Converts integer timestamps to seconds using the metadata file.

    Parameters
    ----------
    timestamps : np.ndarray[int]
        The timestamps to convert.
    scaling_factor : float
        The factor by which to scale integer timestamps to seconds.
    maximum_timestamp : int
        The largest timestamp to include. Will clip all timestamps less than this value.

    Returns
    -------
    np.ndarray
        The converted timestamps.
    """
    TIMESTAMPS_TO_SECONDS = metadata["Constants"]["TIMESTAMPS_TO_SECONDS"]
    timestamps[timestamps < timestamps[0]] = (
        maximum_timestamp + timestamps[timestamps < timestamps[0]]
    )
    timestamps -= timestamps[0]
    timestamps = timestamps * TIMESTAMPS_TO_SECONDS
    return timestamps

class MoseqExtractInterface(BaseDataInterface):
    """Moseq interface for markowitz_gillis_nature_2023 conversion"""

    def __init__(
        self,
        file_path: str,
        session_uuid: str,
        session_id: str,
        session_metadata_path: str,
        subject_metadata_path: str,
        alignment_path: str = None,
    ):
        # This should load the data lazily and prepare variables you need
        super().__init__(
            file_path=file_path,
            session_uuid=session_uuid,
            session_id=session_id,
            session_metadata_path=session_metadata_path,
            subject_metadata_path=subject_metadata_path,
            alignment_path=alignment_path,
        )

    def get_original_timestamps(self) -> np.ndarray:
        with h5py.File(self.source_data["file_path"]) as file:
            return np.array(file["timestamps"])

    def align_timestamps(self, metadata: dict) -> np.ndarray:
        timestamps = self.get_original_timestamps()
        timestamps = convert_timestamps_to_seconds(timestamps=timestamps, metadata=metadata)

        self.set_aligned_timestamps(aligned_timestamps=timestamps)
        if self.source_data["alignment_path"] is not None:
            aligned_starting_time = (
                metadata["Alignment"]["bias"] / metadata["Constants"]["DEMODULATED_PHOTOMETRY_SAMPLING_RATE"]
            )
            self.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)
        return self.aligned_timestamps

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict) -> None:
        timestamps = self.align_timestamps(metadata)
        with h5py.File(self.source_data["file_path"]) as file:
            # Version
            version = np.array(file["metadata"]["extraction"]["extract_version"]).item().decode("ASCII")

            # Video
            processed_depth_video = np.array(file["frames"])
            loglikelihood_video = np.array(file["frames_mask"])

            # Extraction
            background = np.array(file["metadata"]["extraction"]["background"])
            is_flipped = np.array(file["metadata"]["extraction"]["flips"])
            roi = np.array(file["metadata"]["extraction"]["roi"]) * 1.0
            true_depth = np.array(file["metadata"]["extraction"]["true_depth"]).item()

            # Kinematics
            kinematic_vars = {}
            for k, v in file["scalars"].items():
                kinematic_vars[k] = np.array(v)

            # Parameters
            parameters = {}
            for name, data in file["metadata"]["extraction"]["parameters"].items():
                if name in {"output_dir", "input_file"}:
                    continue  # skipping this bc it is Null
                data = np.array(data)
                if name == "bg_roi_depth_range":
                    parameters["bg_roi_depth_range_min"] = data[0]
                    parameters["bg_roi_depth_range_max"] = data[1]
                elif name == "bg_roi_dilate":
                    parameters["bg_roi_dilate_x"] = data[0]
                    parameters["bg_roi_dilate_y"] = data[1]
                elif name == "bg_roi_weights":
                    parameters["bg_roi_weight_area"] = data[0]
                    parameters["bg_roi_weight_extent"] = data[1]
                    parameters["bg_roi_weight_dist"] = data[2]
                elif name == "cable_filter_size":
                    parameters["cable_filter_size_x"] = data[0]
                    parameters["cable_filter_size_y"] = data[1]
                elif name == "crop_size":
                    parameters["crop_size_width"] = data[0]
                    parameters["crop_size_height"] = data[1]
                elif name == "frame_trim":
                    parameters["frame_trim_beginning"] = data[0]
                    parameters["frame_trim_end"] = data[1]
                elif name == "model_smoothing_clips":
                    parameters["model_smoothing_clips_x"] = data[0]
                    parameters["model_smoothing_clips_y"] = data[1]
                elif name == "tail_filter_size":
                    parameters["tail_filter_size_x"] = data[0]
                    parameters["tail_filter_size_y"] = data[1]
                elif data.dtype == "object":
                    parameters[name] = data.item().decode("ASCII")
                else:
                    data = np.array([data.item()], dtype=data.dtype)
                    parameters[name] = data[0]

        # Add Imaging Data
        # TODO: grid_spacing to images
        kinect = nwbfile.create_device(name="kinect", manufacturer="Microsoft", description="Microsoft Kinect 2")
        flipped_series = TimeSeries(
            name="flipped_series",
            data=H5DataIO(is_flipped, compression=True),
            unit="a.u.",
            timestamps=H5DataIO(timestamps, compression=True),
            description="Boolean array indicating whether the image was flipped left/right",
        )
        processed_depth_video = DepthImageSeries(
            name="processed_depth_video",
            data=H5DataIO(processed_depth_video, compression=True),
            unit="millimeters",
            format="raw",
            timestamps=flipped_series.timestamps,
            description="3D array of depth frames (nframes x w x h, in mm)",
            distant_depth=true_depth,
            device=kinect,
        )
        loglikelihood_video = ImageMaskSeries(
            name="loglikelihood_video",
            data=H5DataIO(loglikelihood_video, compression=True),
            masked_imageseries=processed_depth_video,
            unit="a.u.",
            format="raw",
            timestamps=flipped_series.timestamps,
            description="Log-likelihood values from the tracking model (nframes x w x h)",
            device=kinect,
        )
        background = GrayscaleImage(
            name="background",
            data=H5DataIO(background, compression=True),
            description="Computed background image.",
        )
        roi = GrayscaleImage(
            name="roi",
            data=H5DataIO(roi, compression=True),
            description="Computed region of interest.",
        )

        # Add Position Data
        position_data = np.vstack(
            (kinematic_vars["centroid_x_mm"], kinematic_vars["centroid_y_mm"], kinematic_vars["height_ave_mm"])
        ).T
        position_series = SpatialSeries(
            name="position",
            description="Position (x, y, height) in an open field.",
            data=H5DataIO(position_data, compression=True),
            timestamps=flipped_series.timestamps,
            reference_frame=metadata["Behavior"]["Position"]["reference_frame"],
            unit="mm",
        )
        position = Position(spatial_series=position_series, name="position")

        # Add Compass Direction Data
        heading_2d_series = SpatialSeries(
            name="heading_2d",
            description=(
                "The location of the mouse was identified by finding the centroid of the contour with the largest area "
                "using the OpenCV findcontours function. An 80×80 pixel bounding box was drawn around the "
                "identified centroid, and the orientation was estimated using an ellipse fit."
            ),
            data=H5DataIO(kinematic_vars["angle"], compression=True),
            timestamps=flipped_series.timestamps,
            reference_frame=metadata["Behavior"]["CompassDirection"]["reference_frame"],
            unit="radians",
        )
        heading_2d = CompassDirection(spatial_series=heading_2d_series, name="heading_2d")

        # Add speed/velocity data
        speed_2d = TimeSeries(
            name="speed_2d",
            description="2D speed (mm / frame), note that missing frames are not accounted for",
            data=H5DataIO(kinematic_vars["velocity_2d_mm"], compression=True),
            timestamps=flipped_series.timestamps,
            unit="mm/frame",
        )
        speed_3d = TimeSeries(
            name="speed_3d",
            description="3D speed (mm / frame), note that missing frames are not accounted for",
            data=H5DataIO(kinematic_vars["velocity_3d_mm"], compression=True),
            timestamps=flipped_series.timestamps,
            unit="mm/frame",
        )
        angular_velocity_2d = TimeSeries(
            name="angular_velocity_2d",
            description="Angular component of velocity (arctan(vel_x, vel_y))",
            data=H5DataIO(kinematic_vars["velocity_theta"], compression=True),
            timestamps=flipped_series.timestamps,
            unit="radians/frame",
        )

        # Add length/width/area data
        length = TimeSeries(
            name="length",
            description="Length of mouse (mm)",
            data=H5DataIO(kinematic_vars["length_mm"], compression=True),
            timestamps=flipped_series.timestamps,
            unit="mm",
        )
        width = TimeSeries(
            name="width",
            description="Width of mouse (mm)",
            data=H5DataIO(kinematic_vars["width_mm"], compression=True),
            timestamps=flipped_series.timestamps,
            unit="mm",
        )
        width_px_to_mm = kinematic_vars["width_mm"] / kinematic_vars["width_px"]
        length_px_to_mm = kinematic_vars["length_mm"] / kinematic_vars["length_px"]
        area_px_to_mm2 = width_px_to_mm * length_px_to_mm
        area_mm2 = kinematic_vars["area_px"] * area_px_to_mm2
        area = TimeSeries(
            name="area",
            description="Pixel-wise area of mouse (mm^2)",
            data=H5DataIO(area_mm2, compression=True),
            timestamps=flipped_series.timestamps,
            unit="mm^2",
        )

        # Add Parameters
        parameters = MoSeqExtractParameterGroup(name="parameters", **parameters)

        # Add MoseqExtractGroup
        moseq_extract_group = MoSeqExtractGroup(
            name="moseq_extract_group",
            version=version,
            parameters=parameters,
            background=background,
            processed_depth_video=processed_depth_video,
            loglikelihood_video=loglikelihood_video,
            roi=roi,
            flipped_series=flipped_series,
            depth_camera=kinect,
            position=position,
            heading_2d=heading_2d,
            speed_2d=speed_2d,
            speed_3d=speed_3d,
            angular_velocity_2d=angular_velocity_2d,
            length=length,
            width=width,
            area=area,
        )
        # Add data into a behavioral processing module
        behavior_module = nwb_helpers.get_module(
            nwbfile,
            name="behavior",
            description="Processed behavioral data from MoSeq",
        )
        behavior_module.add(moseq_extract_group)
