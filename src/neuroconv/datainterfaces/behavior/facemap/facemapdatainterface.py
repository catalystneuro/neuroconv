from pathlib import Path
from typing import Optional

import h5py
import numpy as np
from pynwb.base import TimeSeries
from pynwb.behavior import EyeTracking, PupilTracking, SpatialSeries
from pynwb.core import DynamicTableRegion
from pynwb.file import NWBFile

from neuroconv.utils.dict import DeepDict

from ..video.video_utils import VideoCaptureContext
from ...._temporal_alignment import _TemporalAlignment
from ....basedatainterface import BaseDataInterface
from ....tools import get_module
from ....tools.nwb_helpers import _get_container_by_name
from ....utils import calculate_regular_series_rate, get_base_schema

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

    def average_motion(self, index: int) -> np.ndarray:
        """Mean motion of each pixel of one cell, flat over the cell's box in MATLAB's column-major order."""
        return self._cell_value("avgmot", index).ravel()

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


class FacemapInterface(BaseDataInterface):
    """Write Facemap pupil, eye-position and motion-SVD outputs to NWB.

    The pupil traces are the interface's own measurements and are described by keyed entries in the top-level
    ``metadata["TimeSeries"]`` and ``metadata["SpatialSeries"]``. The motion SVD of each region (the whole frame,
    which Facemap calls multivideo, and each small ROI) is described by one keyed entry in
    ``metadata["Behavior"]["Facemap"]["MotionSVDMasks"]`` and one in ``["MotionSVDSeries"]``. Each series entry
    names its masks with ``motion_masks_metadata_key``, and a masks entry can name the video it was computed from
    with ``source_video_metadata_key``, a key of ``metadata["Behavior"]["InternalVideos"]`` or
    ``["ExternalVideos"]`` whose ``ImageSeries`` must already be in the file.
    """

    display_name = "Facemap"
    # Every other interface declares `info`; `help` is not read by the GUIDE, so it
    # was reaching `get_format_summaries` as None.
    info = "Interface for the pupil, eye-position and motion-SVD output of the Facemap MATLAB GUI."
    associated_suffixes = (".mat", ".avi")

    keywords = ("eye tracking", "pupil", "face motion")

    def __init__(
        self,
        file_path: FilePathType,
        video_file_path: FilePathType,
        *,
        metadata_key: str | None = None,
        verbose: bool = True,
    ):
        """
        Load and prepare data for facemap.

        Parameters
        ----------
        file_path : string or Path
            Path to the .mat file.
        video_file_path : string or Path
            Path to the .avi file.
        metadata_key : str, optional
            The prefix of this interface's metadata keys and its key in ``temporal_alignment``. Defaults to
            "facemap"; set it so several Facemap interfaces can share an NWB file.
        verbose : bool, default: True
            Allows verbose.
        """
        from ndx_facemap_motionsvd import MotionSVDMasks, MotionSVDSeries  # noqa: F401

        self.metadata_key = metadata_key or "facemap"
        super().__init__(
            file_path=file_path, video_file_path=video_file_path, metadata_key=self.metadata_key, verbose=verbose
        )

        # Facemap writes whichever of these the operator drew an ROI for, and leaves
        # the rest as empty cells rather than omitting them, so presence of the key
        # says nothing about whether it holds data.
        with _ProcFile(file_path) as proc:
            self._has_pupil = proc.has_pupil()
            self._motion_cell_indices = proc.motion_cell_indices()
        # Cell 0 is the whole frame, which Facemap calls multivideo, and the rest are the small ROIs.
        self._region_names = {
            index: "Multivideo" if index == 0 else f"ROI{index}" for index in self._motion_cell_indices
        }
        self._region_metadata_keys = {
            index: f"{self.metadata_key}_{region_name.lower()}" for index, region_name in self._region_names.items()
        }
        self._eye_center_of_mass_metadata_key = f"{self.metadata_key}_eye_center_of_mass"
        self._pupil_metadata_keys = {
            "area": f"{self.metadata_key}_pupil_area",
            "area_raw": f"{self.metadata_key}_pupil_area_raw",
        }

        self._video_times = None
        self.temporal_alignment = _TemporalAlignment()
        self.temporal_alignment._add_time_bearing_object(
            key=self.metadata_key,
            get_native_times=self._get_native_times,
            get_number_of_samples=self._get_number_of_frames,
        )

    def _get_native_times(self) -> np.ndarray:
        # The times ExternalVideoInterface and InternalVideoInterface write for the same video: the container's time
        # for the first frame, then the header frame rate. Reading every frame's position with OpenCV returns 0 for
        # the last frames of some AVI files, so those times are not used.
        if self._video_times is None:
            with VideoCaptureContext(file_path=str(self.source_data["video_file_path"])) as video:
                frame_rate = video.get_video_fps()
                first_frame_times = video.get_video_timestamps(max_frames=1, display_progress=False)
            first_frame_time = float(first_frame_times[0]) if first_frame_times.size else 0.0
            self._video_times = first_frame_time + np.arange(self._get_number_of_frames()) / frame_rate
        return self._video_times

    def _get_number_of_frames(self) -> int:
        with _ProcFile(self.source_data["file_path"]) as proc:
            if self._has_pupil:
                return proc.pupil("area").shape[0]
            return proc.motion_svd(self._motion_cell_indices[0]).shape[0]

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        named_series_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "unit": {"type": "string"},
            },
            "required": ["name", "description", "unit"],
            "additionalProperties": True,
        }
        spatial_series_schema = {
            "type": "object",
            "properties": {
                **named_series_schema["properties"],
                "reference_frame": {"type": "string"},
            },
            "required": [*named_series_schema["required"], "reference_frame"],
            "additionalProperties": True,
        }
        metadata_schema["properties"]["SpatialSeries"] = {
            "type": "object",
            "additionalProperties": spatial_series_schema,
        }
        metadata_schema["properties"]["TimeSeries"] = {
            "type": "object",
            "additionalProperties": named_series_schema,
        }

        motion_masks_entry_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "source_video_metadata_key": {
                    "type": "string",
                    "description": "Key of the Behavior/InternalVideos or Behavior/ExternalVideos entry the masks "
                    "were computed from.",
                },
            },
            "required": ["name", "description"],
            "additionalProperties": False,
        }
        motion_series_entry_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "motion_masks_metadata_key": {
                    "type": "string",
                    "description": "Key of the Behavior/Facemap/MotionSVDMasks entry holding the masks of the series.",
                },
            },
            "required": ["name", "description", "motion_masks_metadata_key"],
            "additionalProperties": False,
        }
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        # Left open so the metadata other interfaces write under Behavior survives validation in a converter.
        metadata_schema["properties"]["Behavior"]["additionalProperties"] = True
        metadata_schema["properties"]["Behavior"]["properties"] = {
            "Facemap": {
                "type": "object",
                "properties": {
                    "MotionSVDMasks": {"type": "object", "additionalProperties": motion_masks_entry_schema},
                    "MotionSVDSeries": {"type": "object", "additionalProperties": motion_series_entry_schema},
                },
                "additionalProperties": False,
            },
        }
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        if self._has_pupil:
            metadata["SpatialSeries"][self._eye_center_of_mass_metadata_key] = dict(
                name="eye_center_of_mass",
                description="Center of mass of the pupil, as (row, column) in pixels of the pupil ROI.",
                reference_frame="Top-left corner of the pupil ROI, with 1-based MATLAB indices.",
                unit="pixels",
            )
            metadata["TimeSeries"][self._pupil_metadata_keys["area"]] = dict(
                name="pupil_area", description="Area of pupil.", unit="pixels^2"
            )
            metadata["TimeSeries"][self._pupil_metadata_keys["area_raw"]] = dict(
                name="pupil_area_raw", description="Raw unprocessed area of pupil.", unit="pixels^2"
            )
        for index, region_name in self._region_names.items():
            region_metadata_key = self._region_metadata_keys[index]
            metadata["Behavior"]["Facemap"]["MotionSVDMasks"][region_metadata_key] = dict(
                name=f"MotionSVDMasks{region_name}", description=f"Motion masks for {region_name}."
            )
            metadata["Behavior"]["Facemap"]["MotionSVDSeries"][region_metadata_key] = dict(
                name=f"MotionSVDSeries{region_name}",
                description=f"Motion SVD components for {region_name}.",
                motion_masks_metadata_key=region_metadata_key,
            )
        return metadata

    def _add_pupil(self, nwbfile: NWBFile, metadata: DeepDict, time_kwargs: dict):
        behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")
        with _ProcFile(self.source_data["file_path"]) as proc:
            eye_center_of_mass = SpatialSeries(
                data=proc.pupil("com"),
                **metadata["SpatialSeries"][self._eye_center_of_mass_metadata_key],
                **time_kwargs,
            )
            behavior_module.add(EyeTracking(name="EyeTracking", spatial_series=eye_center_of_mass))

            pupil_tracking = PupilTracking(name="PupilTracking")
            for pupil_trace_type, pupil_metadata_key in self._pupil_metadata_keys.items():
                pupil_tracking.add_timeseries(
                    TimeSeries(
                        data=proc.pupil(pupil_trace_type),
                        **metadata["TimeSeries"][pupil_metadata_key],
                        **time_kwargs,
                    )
                )
            behavior_module.add(pupil_tracking)

    def _add_motion_svd(
        self, nwbfile: NWBFile, metadata: DeepDict, index: int, first_n_components: int, time_kwargs: dict
    ):
        """
        Add the motion SVD and motion masks of one region.

        From the Facemap documentation:
        motSVD: cell array of motion SVDs [time x components] (in order: multivideo, ROI1, ROI2, ROI3)
        uMotMask: cell array of motion masks [pixels x components]  (in order: multivideo, ROI1, ROI2, ROI3)
        The multivideo masks are 2D arrays [pixels x components], and the ROI masks are 3D arrays
        [rows x columns x components].
        """
        from ndx_facemap_motionsvd import MotionSVDMasks, MotionSVDSeries

        facemap_metadata = metadata["Behavior"]["Facemap"]
        series_metadata = dict(facemap_metadata["MotionSVDSeries"][self._region_metadata_keys[index]])
        masks_metadata = dict(facemap_metadata["MotionSVDMasks"][series_metadata.pop("motion_masks_metadata_key")])

        source_video_metadata_key = masks_metadata.pop("source_video_metadata_key", None)
        if source_video_metadata_key is not None:
            videos = {
                **metadata["Behavior"].get("InternalVideos", {}),
                **metadata["Behavior"].get("ExternalVideos", {}),
            }
            if source_video_metadata_key not in videos:
                raise ValueError(
                    f"source_video_metadata_key '{source_video_metadata_key}' was not found in "
                    "metadata['Behavior']['InternalVideos'] or metadata['Behavior']['ExternalVideos']. "
                    f"Available keys: {list(videos)}."
                )
            masks_metadata["source_video"] = _get_container_by_name(
                nwbfile, videos[source_video_metadata_key]["name"], "ImageSeries"
            )

        behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")
        with _ProcFile(self.source_data["file_path"]) as proc:
            # The boxes are MATLAB [x y width height], x being the column and y the row of the top-left corner.
            box = proc.multivideo_box() if index == 0 else proc.loc_roi(index)
            column_start = int(np.round(box[0]) - 1)  # correct matlab indexing
            row_start = int(np.round(box[1]) - 1)  # correct matlab indexing
            column_end = column_start + int(np.round(box[2]))
            row_end = row_start + int(np.round(box[3]))
            frame = proc.processed_frame()
            # Flat in MATLAB's column-major order, so reshaping to (width, height) and transposing gives (height, width).
            average_motion = proc.average_motion(index).reshape((column_end - column_start, row_end - row_start)).T

            motion_masks_table = MotionSVDMasks(
                **masks_metadata,
                mask_coordinates=[row_start, column_start, row_end, column_end],
                downsampling_factor=proc.scalar("sc"),
                processed_frame_dimension=[frame.shape[0], frame.shape[1]],
                average_motion=average_motion,
            )

            mask = proc.motion_mask(index)
            for component in range(min(first_n_components, mask.shape[-1])):
                if index == 0:
                    image_mask = mask[:, component].reshape((column_end - column_start, row_end - row_start)).T
                else:
                    image_mask = mask[:, :, component]
                motion_masks_table.add_row(image_mask=image_mask, check_ragged=False)

            motion_masks = DynamicTableRegion(
                name="motion_masks",
                data=list(range(len(motion_masks_table))),
                description=f"All the {self._region_names[index]} motion masks.",
                table=motion_masks_table,
            )

            motion_series = MotionSVDSeries(
                **series_metadata,
                data=proc.motion_svd(index)[:, :first_n_components],
                motion_masks=motion_masks,
                unit="unknown",
                **time_kwargs,
            )
            behavior_module.add(motion_masks_table)
            behavior_module.add(motion_series)

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
        resolved_metadata = DeepDict(self.get_metadata())
        if metadata is not None:
            resolved_metadata.deep_update(metadata)

        timestamps = self.temporal_alignment[self.metadata_key].get_times()
        rate = calculate_regular_series_rate(series=timestamps)
        time_kwargs = dict(rate=rate, starting_time=timestamps[0]) if rate else dict(timestamps=timestamps)

        if self._has_pupil:
            self._add_pupil(nwbfile=nwbfile, metadata=resolved_metadata, time_kwargs=time_kwargs)
        elif self.verbose:
            print(f"No pupil ROI in {self.source_data['file_path']}, skipping pupil and eye tracking.")

        for index in self._motion_cell_indices:
            if index == 0 and not include_multivideo_SVD:
                continue
            self._add_motion_svd(
                nwbfile=nwbfile,
                metadata=resolved_metadata,
                index=index,
                first_n_components=first_n_components,
                time_kwargs=time_kwargs,
            )
        if not self._motion_cell_indices and self.verbose:
            print(f"No motion SVD in {self.source_data['file_path']}, skipping motion masks and series.")
