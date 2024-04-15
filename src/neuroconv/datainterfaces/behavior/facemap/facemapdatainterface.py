from typing import Optional

import h5py
import numpy as np
from pynwb.base import TimeSeries
from pynwb.behavior import EyeTracking, PupilTracking, SpatialSeries
from pynwb.file import NWBFile
from ndx_facemap_motionsvd import MotionSVDMasks, MotionSVDSeries
from pynwb.core import DynamicTableRegion
from ..video.video_utils import get_video_timestamps
from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module
from ....utils import FilePathType


class FacemapInterface(BaseTemporalAlignmentInterface):
    display_name = "Facemap"
    help = "Interface for Facemap output."

    keywords = ["eye tracking"]

    def __init__(
        self,
        mat_file_path: FilePathType,
        video_file_path: FilePathType,
        first_n_components: int = 500,
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
        first_n_components : int, default: 500
            Number of components to store.
        include_multivideo_SVD : bool, default: True
            Include multivideo motion SVD.
        verbose : bool, default: True
            Allows verbose.
        """
        super().__init__(mat_file_path=mat_file_path, video_file_path=video_file_path, verbose=verbose)
        self.first_n_components = first_n_components
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

    def add_multivideo_motion_SVD(self, nwbfile: NWBFile):
        """
        Add data motion SVD and motion mask for the whole video.

        Parameters
        ----------
        nwbfile : NWBFile
            NWBFile to add motion SVD components data to.
        """

        # From documentation
        # motSVD: cell array of motion SVDs [time x components] (in order: multivideo, ROI1, ROI2, ROI3)
        # uMotMask: cell array of motion masks [pixels x components]  (in order: multivideo, ROI1, ROI2, ROI3)
        # motion masks of multivideo are reported as 2D-arrays npixels x components

        with h5py.File(self.source_data["mat_file_path"], "r") as file:

            behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")

            timestamps = self.get_timestamps()

            # Extract mask_coordinates
            mask_coordinates = file[file[file["proc"]["ROI"][0][0]][0][0]]
            y1 = int(np.round(mask_coordinates[0][0])-1) # correct matlab indexing
            x1 = int(np.round(mask_coordinates[1][0])-1) # correct matlab indexing
            y2 = y1 + int(np.round(mask_coordinates[2][0]))
            x2 = x1 + int(np.round(mask_coordinates[3][0]))
            mask_coordinates = [x1, y1, x2, y2]

            # store multivideo motion mask and motion series
            motion_masks_table = MotionSVDMasks(
                name=f"MotionSVDMasksMultivideo",
                description=f"motion mask for multivideo",
                mask_coordinates=mask_coordinates,
                downsampling_factor=self._get_downsamplig_factor(),
                processed_frame_dimension=self._get_processed_frame_dimension(),
            )

            # add multivideo mask
            mask_ref = file["proc"]["uMotMask"][0][0]
            for c, component in enumerate(file[mask_ref]):
                if c == self.first_n_components:
                    break
                componendt_2d = component.reshape((y2-y1, x2-x1))
                motion_masks_table.add_row(image_mask=componendt_2d.T)

            motion_masks = DynamicTableRegion(
                name="motion_masks",
                data=list(range(len(file["proc"]["motSVD"][:]))),
                description="all the multivideo motion mask",
                table=motion_masks_table,
            )

            series_ref = file["proc"]["motSVD"][0][0]
            data = np.array(file[series_ref])
            data = data[: self.first_n_components, :]

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

        return

    def add_motion_SVD(self, nwbfile: NWBFile):
        """
        Add data motion SVD and motion mask for each ROI.

        Parameters
        ----------
        nwbfile : NWBFile
            NWBFile to add motion SVD components data to.
        """

        # From documentation
        # motSVD: cell array of motion SVDs [time x components] (in order: multivideo, ROI1, ROI2, ROI3)
        # uMotMask: cell array of motion masks [pixels x components]  (in order: multivideo, ROI1, ROI2, ROI3)
        # ROIs motion masks are reported as 3D-arrays x_pixels x y_pixels x components

        with h5py.File(self.source_data["mat_file_path"], "r") as file:

            behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")

            timestamps = self.get_timestamps()
            downsampling_factor=self._get_downsamplig_factor()
            processed_frame_dimension=self._get_processed_frame_dimension()
            # store ROIs motion mask and motion series
            n = 1
            for series_ref, mask_ref in zip(file["proc"]["motSVD"][1:], file["proc"]["uMotMask"][1:]):
                series_ref = series_ref[0]
                mask_ref = mask_ref[0]

                # skipping the first ROI because it referes to "running" mask, from Facemap doc
                mask_coordinates = file[file["proc"]["locROI"][n][0]]
                y1 = int(np.round(mask_coordinates[0][0])-1) # correct matlab indexing
                x1 = int(np.round(mask_coordinates[1][0])-1) # correct matlab indexing
                y2 = y1 + int(np.round(mask_coordinates[2][0]))
                x2 = x1 + int(np.round(mask_coordinates[3][0]))
                mask_coordinates = [x1, y1, x2, y2]

                motion_masks_table = MotionSVDMasks(
                    name=f"MotionSVDMasksROI{n}",
                    description=f"motion mask for ROI{n}",
                    mask_coordinates=mask_coordinates,
                    downsampling_factor=downsampling_factor,
                    processed_frame_dimension=processed_frame_dimension,
                )

                for c, component in enumerate(file[mask_ref]):
                    if c == self.first_n_components:
                        break
                    motion_masks_table.add_row(image_mask=component.T)

                motion_masks = DynamicTableRegion(
                    name="motion_masks",
                    data=list(range(self.first_n_components)),
                    description="all the ROIs motion mask",
                    table=motion_masks_table,
                )

                data = np.array(file[series_ref])
                data = data[: self.first_n_components, :]

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
    
    def _get_downsamplig_factor(self) -> float:
        with h5py.File(self.source_data["mat_file_path"], "r") as file:
            downsamplig_factor = file["proc"]["sc"][0][0]
        return downsamplig_factor
    
    def _get_processed_frame_dimension(self) -> np.ndarray:
        with h5py.File(self.source_data["mat_file_path"], "r") as file:
            processed_frame_ref = file["proc"]["wpix"][0][0]
            frame = file[processed_frame_ref]
            return [frame.shape[1],frame.shape[0]]
        
     
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
        if self.add_multivideo_motion_SVD:
            self.add_multivideo_motion_SVD(nwbfile=nwbfile)
