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

    def __init__(self, mat_file_path: FilePathType, video_file_path: FilePathType, verbose: bool = True):
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

        with h5py.File(self.source_data["mat_file_path"], "r") as file:

            behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")

            timestamps = self.get_timestamps()
            n = 0
            for series_ref, mask_ref in zip(file["proc"]["motSVD"][:], file["proc"]["uMotMask"][:]):
                mask_ref = mask_ref[0]
                series_ref = series_ref[0]

                motion_masks_table = MotionSVDMasks(
                    name=f"MotionSVDMasksROI{n}",
                    description=f"motion mask for ROI{n}",
                )

                for component in file[mask_ref]:
                    motion_masks_table.add_row(image_mask=component)

                motion_masks = DynamicTableRegion(
                    name="motion_masks",
                    data=list(range(len(file["proc"]["motSVD"][:]))),
                    description="all the mask",
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
