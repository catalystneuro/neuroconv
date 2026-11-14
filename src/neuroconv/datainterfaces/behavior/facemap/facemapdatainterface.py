from pathlib import Path
from typing import Literal, Optional

import h5py
import numpy as np
from pynwb.base import TimeSeries
from pynwb.behavior import EyeTracking, PupilTracking, SpatialSeries
from pynwb.core import DynamicTableRegion
from pynwb.file import NWBFile

from neuroconv.utils.dict import DeepDict

from ..video.video_utils import get_video_timestamps
from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module
from ....utils import get_base_schema, get_schema_from_hdmf_class

FilePathType = str | Path


class _ProcFile:
    """Read a Facemap MATLAB-GUI ``_proc.mat``, whichever container it was written in.

    ``matlab/saveROI.m`` writes ``save(savepath, '-v7.3', 'proc')``, so the file is
    HDF5 and only ``h5py`` opens it. Files resaved by downstream analysis are plain
    MATLAB 5.0 instead, where only ``scipy.io.loadmat`` works. Both are common in
    the wild, and the two libraries disagree about index order, so this class hides
    the choice: every accessor returns arrays in MATLAB's own orientation, which is
    the one ``saveROI.m`` and the Facemap documentation describe.

    ``proc`` fields are also written conditionally, and a field that was never
    populated is still present as an empty cell rather than being absent, so the
    ``has_*`` predicates below distinguish the two.
    """

    def __init__(self, file_path: str | Path):
        self.file_path = str(file_path)
        with open(self.file_path, "rb") as handle:
            self.is_hdf5 = handle.read(16).startswith(b"MATLAB 7.3")
        if self.is_hdf5:
            self._mat = None
        else:
            import scipy.io  # not a core neuroconv dependency

            self._mat = scipy.io.loadmat(self.file_path)["proc"][0, 0]

    def __enter__(self):
        if self.is_hdf5:
            self._h5 = h5py.File(self.file_path, "r")
            self._proc = self._h5["proc"]
        return self

    def __exit__(self, *exc_info):
        if self.is_hdf5:
            self._h5.close()

    # -- MATLAB stores an empty array in HDF5 as a two-element uint64 of its zero
    # -- dimensions, not as a zero-length dataset, so emptiness needs its own test.
    def _is_empty(self, reference) -> bool:
        target = self._h5[reference]
        return target.dtype == np.uint64 and target.shape == (2,) and int(np.prod(target[()])) == 0

    def _cell(self, name: str) -> list:
        if self.is_hdf5:
            return list(self._proc[name][()].ravel())
        return list(np.asarray(self._mat[name]).ravel())

    def _cell_is_empty(self, name: str, index: int) -> bool:
        entries = self._cell(name)
        if index >= len(entries):
            return True
        if self.is_hdf5:
            return self._is_empty(entries[index])
        return np.asarray(entries[index]).size == 0

    def _cell_value(self, name: str, index: int) -> np.ndarray:
        entry = self._cell(name)[index]
        # h5py reverses MATLAB's index order on every axis; transposing restores it.
        return np.asarray(self._h5[entry][()]).T if self.is_hdf5 else np.asarray(entry)

    def has_field(self, name: str) -> bool:
        return name in (self._proc if self.is_hdf5 else self._mat.dtype.names)

    def scalar(self, name: str) -> float:
        source = self._proc[name] if self.is_hdf5 else self._mat[name]
        return float(np.asarray(source).ravel()[0])

    def motion_cell_indices(self) -> list[int]:
        """Which motion-SVD cells hold data.

        Cell 0 is the whole frame and the rest are the small ROIs, in the fixed
        order Facemap writes them, so an ROI that was never drawn leaves an empty
        cell in place rather than shifting the ones after it. Returning indices
        rather than a count keeps that alignment with ``locROI``.
        """
        if not self.has_field("motSVD"):
            return []
        entries = self._cell("motSVD")
        return [index for index in range(len(entries)) if not self._cell_is_empty("motSVD", index)]

    def motion_svd(self, index: int) -> np.ndarray:
        """Motion SVD components for one cell, ``(frames, components)``."""
        return self._cell_value("motSVD", index)

    def motion_mask(self, index: int) -> np.ndarray:
        """Motion masks for one cell.

        Cell 0 is the whole-frame mask, left flat as ``(pixels, components)`` by
        ``saveROI.m``; every other cell was already reshaped by it to
        ``(rows, columns, components)``.
        """
        return self._cell_value("uMotMask", index)

    def multivideo_box(self) -> np.ndarray:
        """The whole-frame box, ``proc.ROI{1}{1}``, reached through two cell levels."""
        if self.is_hdf5:
            return np.asarray(self._h5[self._h5[self._proc["ROI"][0][0]][0][0]][()]).ravel()
        return np.asarray(np.asarray(np.asarray(self._mat["ROI"]).ravel()[0]).ravel()[0]).ravel()

    def loc_roi(self, index: int) -> np.ndarray:
        return self._cell_value("locROI", index).ravel()

    def has_pupil(self) -> bool:
        if not self.has_field("pupil"):
            return False
        if self.is_hdf5:
            return isinstance(self._proc["pupil"], h5py.Group)
        return np.asarray(self._mat["pupil"]).size > 0

    def pupil(self, field: str) -> np.ndarray:
        """One pupil trace, ``(frames, n)``. Assumes a single pupil ROI."""
        if self.is_hdf5:
            return np.asarray(self._proc["pupil"][field][()]).T
        return np.asarray(np.asarray(self._mat["pupil"]).ravel()[0][field])

    def processed_frame(self) -> np.ndarray:
        """``proc.wpix{1}``, the per-pixel mask of what entered the whole-frame SVD."""
        return self._cell_value("wpix", 0)


class FacemapInterface(BaseTemporalAlignmentInterface):
    """Write Facemap pupil, eye-position and motion-SVD outputs to NWB."""

    display_name = "Facemap"
    # Every other interface declares `info`; `help` is not read by the GUIDE, so it
    # was reaching `get_format_summaries` as None.
    info = "Interface for the pupil, eye-position and motion-SVD output of the Facemap MATLAB GUI."
    associated_suffixes = (".mat", ".avi")

    keywords = ("eye tracking", "pupil", "face motion")

    def __init__(
        self,
        mat_file_path: FilePathType,
        video_file_path: FilePathType,
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
        from ndx_facemap_motionsvd import MotionSVDMasks, MotionSVDSeries  # noqa: F401

        super().__init__(mat_file_path=mat_file_path, video_file_path=video_file_path, verbose=verbose)
        self._original_timestamps = None
        self._timestamps = None

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        spatial_series_metadata_schema = get_schema_from_hdmf_class(SpatialSeries)
        time_series_metadata_schema = get_schema_from_hdmf_class(TimeSeries)
        metadata_schema["properties"]["Behavior"].update(
            required=["EyeTracking", "PupilTracking", "MotionSVDMasks", "MotionSVDSeries"],
            properties=dict(
                EyeTracking=dict(
                    type="array",
                    minItems=1,
                    items=spatial_series_metadata_schema,
                ),
                PupilTracking=dict(
                    type="array",
                    minItems=1,
                    items=time_series_metadata_schema,
                ),
                MotionSVDMasks=dict(
                    type="object",
                    properties=dict(
                        name=dict(type="string"),
                        description=dict(type="string"),
                    ),
                    required=["name", "description"],
                ),
                MotionSVDSeries=dict(
                    type="object",
                    properties=dict(
                        name=dict(type="string"),
                        description=dict(type="string"),
                    ),
                    required=["name", "description"],
                ),
            ),
        )

        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        behavior_metadata = dict(
            EyeTracking=[
                dict(
                    name="eye_center_of_mass",
                    description="The position of the eye measured in degrees.",
                    reference_frame="unknown",
                    unit="degrees",
                )
            ],
            PupilTracking=[
                dict(name="pupil_area", description="Area of pupil.", unit="unknown"),
                dict(name="pupil_area_raw", description="Raw unprocessed area of pupil.", unit="unknown"),
            ],
            MotionSVDMasks=dict(name="MotionSVDMasks", description="Motion masks"),
            MotionSVDSeries=dict(name="MotionSVDSeries", description="Motion SVD components"),
        )
        metadata["Behavior"] = behavior_metadata
        return metadata

    def _add_eye_tracking(self, nwbfile: NWBFile, metadata: DeepDict):

        if self._timestamps is None:
            self._timestamps = self.get_timestamps()

        with _ProcFile(self.source_data["mat_file_path"]) as proc:

            behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")
            eye_tracking_metadata = metadata["Behavior"]["EyeTracking"][0]

            eye_com = SpatialSeries(
                name=eye_tracking_metadata["name"],
                description=eye_tracking_metadata["description"],
                data=proc.pupil("com"),
                reference_frame=eye_tracking_metadata["reference_frame"],
                unit=eye_tracking_metadata["unit"],
                timestamps=self._timestamps,
            )

            eye_tracking = EyeTracking(name="EyeTracking", spatial_series=eye_com)

            behavior_module.add(eye_tracking)

    def _add_pupil_data(
        self, nwbfile: NWBFile, metadata: DeepDict, pupil_trace_type: Literal["area_raw", "area"] = "area"
    ):

        with _ProcFile(self.source_data["mat_file_path"]) as proc:

            behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")

            pupil_area_metadata_ind = 0 if pupil_trace_type == "area" else 1
            pupil_area_metadata = metadata["Behavior"]["PupilTracking"][pupil_area_metadata_ind]

            if "EyeTracking" not in behavior_module.data_interfaces:
                self._add_eye_tracking(nwbfile=nwbfile, metadata=metadata)

            eye_tracking_name = metadata["Behavior"]["EyeTracking"][0]["name"]
            eye_com = behavior_module.data_interfaces["EyeTracking"].spatial_series[eye_tracking_name]

            pupil_trace = TimeSeries(
                name=pupil_area_metadata["name"],
                description=pupil_area_metadata["description"],
                data=proc.pupil(pupil_trace_type),
                unit=pupil_area_metadata["unit"],
                timestamps=eye_com,
            )

            if "PupilTracking" not in behavior_module.data_interfaces:
                pupil_tracking = PupilTracking(name="PupilTracking")
                behavior_module.add(pupil_tracking)
            else:
                pupil_tracking = behavior_module.data_interfaces["PupilTracking"]

            pupil_tracking.add_timeseries(pupil_trace)

    def _add_multivideo_motion_SVD(self, nwbfile: NWBFile, metadata: DeepDict, first_n_components: int):
        """
        Add data motion SVD and motion mask for the whole video.

        Parameters
        ----------
        nwbfile : NWBFile
            NWBFile to add motion SVD components data to.
        first_n_components : int
            Number of components to store.
        """
        from ndx_facemap_motionsvd import MotionSVDMasks, MotionSVDSeries

        # From documentation
        # motSVD: cell array of motion SVDs [time x components] (in order: multivideo, ROI1, ROI2, ROI3)
        # uMotMask: cell array of motion masks [pixels x components]  (in order: multivideo, ROI1, ROI2, ROI3)
        # motion masks of multivideo are reported as 2D-arrays npixels x
        if self._timestamps is None:
            self._timestamps = self.get_timestamps()

        motion_mask_name = metadata["Behavior"]["MotionSVDMasks"]["name"]
        motion_mask_description = metadata["Behavior"]["MotionSVDMasks"]["description"]
        motion_series_name = metadata["Behavior"]["MotionSVDSeries"]["name"]
        motion_series_description = metadata["Behavior"]["MotionSVDSeries"]["description"]

        with _ProcFile(self.source_data["mat_file_path"]) as proc:

            behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")

            # Extract mask_coordinates
            box = proc.multivideo_box()
            y1 = int(np.round(box[0]) - 1)  # correct matlab indexing
            x1 = int(np.round(box[1]) - 1)  # correct matlab indexing
            y2 = y1 + int(np.round(box[2]))
            x2 = x1 + int(np.round(box[3]))
            mask_coordinates = [x1, y1, x2, y2]

            # store multivideo motion mask and motion series
            motion_masks_table = MotionSVDMasks(
                name=f"{motion_mask_name}Multivideo",
                description=f"{motion_mask_description} for multivideo.",
                mask_coordinates=mask_coordinates,
                downsampling_factor=self._get_downsamplig_factor(),
                processed_frame_dimension=self._get_processed_frame_dimension(),
            )

            # add multivideo mask
            mask = proc.motion_mask(0)
            for c in range(min(first_n_components, mask.shape[-1])):
                componendt_2d = mask[:, c].reshape((y2 - y1, x2 - x1))
                motion_masks_table.add_row(image_mask=componendt_2d.T, check_ragged=False)

            motion_masks = DynamicTableRegion(
                name="motion_masks",
                data=list(range(len(motion_masks_table))),
                description="all the multivideo motion mask",
                table=motion_masks_table,
            )

            data = proc.motion_svd(0)[:, :first_n_components]

            motion_series = MotionSVDSeries(
                name=f"{motion_series_name}Multivideo",
                description=f"{motion_series_description} for multivideo.",
                data=data,
                motion_masks=motion_masks,
                unit="unknown",
                timestamps=self._timestamps,
            )
            behavior_module.add(motion_masks_table)
            behavior_module.add(motion_series)

        return

    def _add_motion_SVD(self, nwbfile: NWBFile, metadata: DeepDict, first_n_components: int):
        """
        Add data motion SVD and motion mask for each ROI.

        Parameters
        ----------
        nwbfile : NWBFile
            NWBFile to add motion SVD components data to.
        first_n_components : int
            Number of components to store.
        """
        from ndx_facemap_motionsvd import MotionSVDMasks, MotionSVDSeries

        # From documentation
        # motSVD: cell array of motion SVDs [time x components] (in order: multivideo, ROI1, ROI2, ROI3)
        # uMotMask: cell array of motion masks [pixels x components]  (in order: multivideo, ROI1, ROI2, ROI3)
        # ROIs motion masks are reported as 3D-arrays x_pixels x y_pixels x components

        if self._timestamps is None:
            self._timestamps = self.get_timestamps()

        motion_mask_name = metadata["Behavior"]["MotionSVDMasks"]["name"]
        motion_mask_description = metadata["Behavior"]["MotionSVDMasks"]["description"]
        motion_series_name = metadata["Behavior"]["MotionSVDSeries"]["name"]
        motion_series_description = metadata["Behavior"]["MotionSVDSeries"]["description"]

        with _ProcFile(self.source_data["mat_file_path"]) as proc:

            behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")

            downsampling_factor = self._get_downsamplig_factor()
            processed_frame_dimension = self._get_processed_frame_dimension()
            # store ROIs motion mask and motion series
            # skipping the first cell because it refers to the multivideo mask
            for n in [index for index in proc.motion_cell_indices() if index > 0]:

                box = proc.loc_roi(n)
                y1 = int(np.round(box[0]) - 1)  # correct matlab indexing
                x1 = int(np.round(box[1]) - 1)  # correct matlab indexing
                y2 = y1 + int(np.round(box[2]))
                x2 = x1 + int(np.round(box[3]))
                mask_coordinates = [x1, y1, x2, y2]

                motion_masks_table = MotionSVDMasks(
                    name=f"{motion_mask_name}ROI{n}",
                    description=f"{motion_mask_description} for ROI{n}",
                    mask_coordinates=mask_coordinates,
                    downsampling_factor=downsampling_factor,
                    processed_frame_dimension=processed_frame_dimension,
                )

                mask = proc.motion_mask(n)
                for c in range(min(first_n_components, mask.shape[-1])):
                    motion_masks_table.add_row(image_mask=mask[:, :, c], check_ragged=False)

                motion_masks = DynamicTableRegion(
                    name="motion_masks",
                    data=list(range(len(motion_masks_table))),
                    description="all the ROIs motion mask",
                    table=motion_masks_table,
                )

                data = proc.motion_svd(n)[:, :first_n_components]

                motion_series = MotionSVDSeries(
                    name=f"{motion_series_name}ROI{n}",
                    description=f"{motion_series_description} for ROI{n}",
                    data=data,
                    motion_masks=motion_masks,
                    unit="unknown",
                    timestamps=self._timestamps,
                )

                behavior_module.add(motion_masks_table)
                behavior_module.add(motion_series)

        return

    def get_original_timestamps(self) -> np.ndarray:
        if self._original_timestamps is None:
            self._original_timestamps = get_video_timestamps(self.source_data["video_file_path"])
        return self._original_timestamps

    def get_timestamps(self) -> np.ndarray:
        if self._timestamps is None:
            return self.get_original_timestamps()
        else:
            return self._timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = aligned_timestamps

    def _get_downsamplig_factor(self) -> float:
        with _ProcFile(self.source_data["mat_file_path"]) as proc:
            return proc.scalar("sc")

    def _get_processed_frame_dimension(self) -> np.ndarray:
        with _ProcFile(self.source_data["mat_file_path"]) as proc:
            frame = proc.processed_frame()
            return [frame.shape[0], frame.shape[1]]

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        *,
        first_n_components: int = 500,
        include_multivideo_SVD: bool = True,
    ):
        """
        Add facemap data to NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            NWBFile to add facemap data to.
        metadata : dict, optional
            Metadata to add to the NWBFile.
        first_n_components : int, default: 500
            Number of motion SVD components to store, per mask and series.
        include_multivideo_SVD : bool, default: True
            Also write the multivideo (whole-frame) motion SVD.
        """
        # Facemap writes whichever of these the operator drew an ROI for, and leaves
        # the rest as empty cells rather than omitting them, so presence of the key
        # says nothing about whether it holds data.
        with _ProcFile(self.source_data["mat_file_path"]) as proc:
            has_pupil = proc.has_pupil()
            motion_cells = proc.motion_cell_indices()

        if has_pupil:
            self._add_pupil_data(nwbfile=nwbfile, metadata=metadata, pupil_trace_type="area_raw")
            self._add_pupil_data(nwbfile=nwbfile, metadata=metadata, pupil_trace_type="area")
        elif self.verbose:
            print(f"No pupil ROI in {self.source_data['mat_file_path']}, skipping pupil and eye tracking.")

        if any(index > 0 for index in motion_cells):
            self._add_motion_SVD(nwbfile=nwbfile, metadata=metadata, first_n_components=first_n_components)
        if include_multivideo_SVD and 0 in motion_cells:
            self._add_multivideo_motion_SVD(nwbfile=nwbfile, metadata=metadata, first_n_components=first_n_components)
        elif not motion_cells and self.verbose:
            print(f"No motion SVD in {self.source_data['mat_file_path']}, skipping motion masks and series.")
