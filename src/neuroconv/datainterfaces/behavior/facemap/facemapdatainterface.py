from typing import Optional

import h5py
import numpy as np
from pynwb.base import TimeSeries
from pynwb.behavior import EyeTracking, PupilTracking, SpatialSeries
from pynwb.file import NWBFile

from ..video.video_utils import get_video_timestamps
from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module, get_package
from ....utils import FilePathType


class FacemapInterface(BaseTemporalAlignmentInterface):
    display_name = "Facemap"
    help = "Interface for Facemap output."

    keywords = ["eye tracking"]

    def __init__(
        self,
        mat_file_path: FilePathType,
        video_file_path: FilePathType,
        include_multivideo_SVD: bool = True,
        verbose: bool = True,
    ):
        """
        Load and prepare data for facemap.

        Parameters
        ----------
        mat_file_path : string or Path
            Path to the .mat file.
        video_file_path : string or Path
            Path to the .avi file.
        verbose : bool, default: True
            Allows verbose.
        """
        super().__init__(mat_file_path=mat_file_path, video_file_path=video_file_path, verbose=verbose)
        self.include_multivideo_SVD = include_multivideo_SVD
        self.original_timestamps = None
        self.timestamps = None

    def add_pupil_data(self, nwbfile: NWBFile):

        timestamps = self.get_timestamps()

        with h5py.File(self.source_data["mat_file_path"], "r") as file:

            behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")

            eye_com = SpatialSeries(
                name="eye_center_of_mass",
                description="The position of the eye measured in degrees.",
                data=file["proc"]["pupil"]["com"][:].T,
                reference_frame="unknown",
                unit="degrees",
                timestamps=timestamps,
            )

            eye_tracking = EyeTracking(name="EyeTracking", spatial_series=eye_com)

            behavior_module.add(eye_tracking)

            pupil_area = TimeSeries(
                name="pupil_area",
                description="Area of pupil",
                data=file["proc"]["pupil"]["area"][:].T,
                unit="unknown",
                timestamps=eye_com,
            )

            pupil_area_raw = TimeSeries(
                name="pupil_area_raw",
                description="Raw unprocessed area of pupil",
                data=file["proc"]["pupil"]["area_raw"][:].T,
                unit="unknown",
                timestamps=eye_com,
            )

            pupil_tracking = PupilTracking(time_series=[pupil_area, pupil_area_raw], name="PupilTracking")

            behavior_module.add(pupil_tracking)

    def add_motion_SVD(self, nwbfile: NWBFile):
        """
        Add data motion SVD and motion mask for each ROI.

        Parameters
        ----------
        nwbfile : NWBFile
            NWBFile to add motion SVD components data to.
        """
        from ndx_facemap_motionsvd import MotionSVDMasks, MotionSVDSeries
        from pynwb.core import DynamicTableRegion

        # From documentation
        # motSVD: cell array of motion SVDs [time x components] (in order: multivideo, ROI1, ROI2, ROI3)
        # uMotMask: cell array of motion masks [pixels x components]  (in order: multivideo, ROI1, ROI2, ROI3)
        # motion masks of multivideo are reported as 2D-arrays npixels x components
        # while ROIs motion masks are reported as 3D-arrays x_pixels x y_pixels x components

        with h5py.File(self.source_data["mat_file_path"], "r") as file:

            behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")

            timestamps = self.get_timestamps()

            # store multivideo motion mask and motion series
            if self.include_multivideo_SVD:
                # add multivideo mask
                mask_ref = file["proc"]["uMotMask"][0][0]
                motion_masks_table = MotionSVDMasks(
                    name=f"MotionSVDMasksMultivideo",
                    description=f"motion mask for multivideo",
                )

                multivideo_mask_ref = file["proc"]["wpix"][0][0]
                multivideo_mask = file[multivideo_mask_ref]
                multivideo_mask = multivideo_mask[:]
                non_zero_multivideo_mask = np.where(multivideo_mask == 1)
                y_indices, x_indices = non_zero_multivideo_mask
                top = np.min(y_indices)
                left = np.min(x_indices)
                bottom = np.max(y_indices)
                right = np.max(x_indices)
                submask = multivideo_mask[top : bottom + 1, left : right + 1]
                componendt_2d_shape = submask.shape

                for component in file[mask_ref]:
                    componendt_2d = component.reshape(componendt_2d_shape)
                    motion_masks_table.add_row(image_mask=componendt_2d.T)

                motion_masks = DynamicTableRegion(
                    name="motion_masks",
                    data=list(range(len(file["proc"]["motSVD"][:]))),
                    description="all the multivideo motion mask",
                    table=motion_masks_table,
                )

                series_ref = file["proc"]["motSVD"][0][0]
                data = np.array(file[series_ref])

                motionsvd_series = MotionSVDSeries(
                    name=f"MotionSVDSeriesMultivideo",
                    description=f"SVD components for multivideo",
                    data=data.T,
                    motion_masks=motion_masks,
                    unit="unknown",
                    timestamps=timestamps,
                )
                behavior_module.add(motion_masks_table)
                behavior_module.add(motionsvd_series)

            # store ROIs motion mask and motion series
            n = 1
            for series_ref, mask_ref in zip(file["proc"]["motSVD"][1:][0], file["proc"]["uMotMask"][1:][0]):

                motion_masks_table = MotionSVDMasks(
                    name=f"MotionSVDMasksROI{n}",
                    description=f"motion mask for ROI{n}",
                )
                for component in file[mask_ref]:
                    motion_masks_table.add_row(image_mask=component.T)

                motion_masks = DynamicTableRegion(
                    name="motion_masks",
                    data=list(range(len(file["proc"]["motSVD"][:]))),
                    description="all the ROIs motion mask",
                    table=motion_masks_table,
                )

                data = np.array(file[series_ref])

                motionsvd_series = MotionSVDSeries(
                    name=f"MotionSVDSeriesROI{n}",
                    description=f"SVD components for ROI{n}",
                    data=data.T,
                    motion_masks=motion_masks,
                    unit="unknown",
                    timestamps=timestamps,
                )
                n = +1

                behavior_module.add(motion_masks_table)
                behavior_module.add(motionsvd_series)

        return

    def get_original_timestamps(self) -> np.ndarray:
        if self.original_timestamps is None:
            self.original_timestamps = get_video_timestamps(self.source_data["video_file_path"])
        return self.original_timestamps

    def get_timestamps(self) -> np.ndarray:
        if self.timestamps is None:
            return self.get_original_timestamps()
        else:
            return self.timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self.timestamps = aligned_timestamps

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        compression: Optional[str] = "gzip",
        compression_opts: Optional[int] = None,
    ):
        """
        Add facemap data to NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            NWBFile to add facemap data to.
        metadata : dict, optional
            Metadata to add to the NWBFile.
        compression : str, optional
            Compression type.
        compression_opts : int, optional
            Compression options.
        """

        self.add_pupil_data(nwbfile=nwbfile)
        self.add_motion_SVD(nwbfile=nwbfile)
