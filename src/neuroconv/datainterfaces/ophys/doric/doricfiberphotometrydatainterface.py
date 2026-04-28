"""Interface for Doric Neuroscience Studio fiber photometry data (.doric HDF5 files)."""
from copy import deepcopy
from datetime import datetime
from typing import Literal

import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from neuroconv.basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from neuroconv.tools.fiber_photometry import add_ophys_device, add_ophys_device_model
from neuroconv.utils import DeepDict

_DORIC_CREATED_FMT = "%a %b %d %H:%M:%S %Y"


class DoricFiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """Interface for fiber photometry data from Doric Neuroscience Studio .doric HDF5 files.

    Reads ROI-averaged fluorescence signals produced by the Doric Neuroscience Studio
    software (compatible with BBC300, BBC600, FPC, and other Doric acquisition hardware).
    Writes data to NWB using the ndx-fiber-photometry extension.

    Stream names are auto-discovered from the HDF5 file on construction by walking
    ``DataAcquisition`` for groups that contain a ``Time`` sibling dataset.  Each
    non-Time 1-D dataset found this way becomes a stream whose name is the path
    relative to ``DataAcquisition`` with ``/`` replaced by ``_``
    (e.g. ``BBC300_ROISignals_Series0001_CAM1EXC1_ROI01``).  Call
    :py:meth:`get_stream_names` to list available streams.

    All fiber photometry hardware metadata (device models, devices, optical fibers,
    indicators, table rows, and response series) must be supplied by the user in the
    ``metadata["Ophys"]["FiberPhotometry"]`` block — this interface does not inject
    hardware defaults.
    """

    keywords = ("fiber photometry",)
    display_name = "DoricFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from Doric Neuroscience Studio .doric HDF5 files."
    associated_suffixes = ("doric",)

    @validate_call
    def __init__(self, *, file_path: FilePath, verbose: bool = False):
        """Initialize the DoricFiberPhotometryInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the .doric HDF5 file produced by Doric Neuroscience Studio.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(file_path=file_path, verbose=verbose)
        # Keep ndx extensions registered so pynwb IO works correctly.
        import ndx_fiber_photometry  # noqa: F401
        import ndx_ophys_devices  # noqa: F401

        import h5py

        self._streams: dict[str, dict] = {}
        self._session_start_time: datetime | None = None

        with h5py.File(self.source_data["file_path"], "r") as f:
            self._streams = self._discover_streams(f)
            created_str = f.attrs.get("Created", "")

        if created_str:
            try:
                self._session_start_time = datetime.strptime(created_str, _DORIC_CREATED_FMT)
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Stream discovery
    # ------------------------------------------------------------------

    @staticmethod
    def _discover_streams(f) -> dict:
        """Walk DataAcquisition and return stream_name → {data_path, time_path}."""
        import h5py

        streams: dict[str, dict] = {}
        if "DataAcquisition" not in f:
            return streams

        def _visit(name: str, obj) -> None:
            if not isinstance(obj, h5py.Group):
                return
            if "Time" not in obj:
                return
            for key in obj:
                if key == "Time":
                    continue
                item = obj[key]
                if isinstance(item, h5py.Dataset) and item.ndim == 1:
                    stream_name = f"{name}/{key}".replace("/", "_")
                    streams[stream_name] = {
                        "data_path": f"DataAcquisition/{name}/{key}",
                        "time_path": f"DataAcquisition/{name}/Time",
                    }

        f["DataAcquisition"].visititems(_visit)
        return streams

    def get_stream_names(self) -> list[str]:
        """Return all stream names discovered in the .doric file.

        Returns
        -------
        list[str]
            Sorted list of stream names that can be referenced as ``stream_name``
            in ``FiberPhotometryResponseSeries`` metadata entries.
        """
        return sorted(self._streams)

    # ------------------------------------------------------------------
    # Internal data loader
    # ------------------------------------------------------------------

    def _load_stream_array(
        self, stream_name: str, t1: float = 0.0, t2: float = 0.0
    ) -> tuple[np.ndarray, np.ndarray]:
        """Load a single stream's data and timestamps from the HDF5 file.

        Parameters
        ----------
        stream_name : str
            A key returned by :py:meth:`get_stream_names`.
        t1 : float
            Start time in seconds (original clock). 0 means beginning of recording.
        t2 : float
            End time in seconds (original clock). 0 means end of recording.

        Returns
        -------
        data : np.ndarray, shape (N,)
        timestamps : np.ndarray, shape (N,)
        """
        import h5py

        info = self._streams[stream_name]
        with h5py.File(self.source_data["file_path"], "r") as f:
            time_data = f[info["time_path"]][:]
            start_idx = int(np.searchsorted(time_data, t1)) if t1 > 0.0 else 0
            end_idx = int(np.searchsorted(time_data, t2, side="right")) if t2 > 0.0 else len(time_data)
            return f[info["data_path"]][start_idx:end_idx], time_data[start_idx:end_idx]

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        if self._session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = self._session_start_time
        return metadata

    # ------------------------------------------------------------------
    # Temporal alignment API (mirrors TDTFiberPhotometryInterface)
    # ------------------------------------------------------------------

    def get_original_timestamps(self, t1: float = 0.0, t2: float = 0.0) -> dict[str, np.ndarray]:
        """Return the original (unaligned) timestamps for every discovered stream.

        Parameters
        ----------
        t1, t2 : float
            Time window in original clock seconds.  0 means start/end of recording.

        Returns
        -------
        dict[str, np.ndarray]
            Maps stream names to their timestamp arrays.
        """
        import h5py

        result: dict[str, np.ndarray] = {}
        time_path_cache: dict[str, np.ndarray] = {}
        with h5py.File(self.source_data["file_path"], "r") as f:
            for stream_name, info in self._streams.items():
                tp = info["time_path"]
                if tp not in time_path_cache:
                    time_data = f[tp][:]
                    start_idx = int(np.searchsorted(time_data, t1)) if t1 > 0.0 else 0
                    end_idx = int(np.searchsorted(time_data, t2, side="right")) if t2 > 0.0 else len(time_data)
                    time_path_cache[tp] = time_data[start_idx:end_idx]
                result[stream_name] = time_path_cache[tp]
        return result

    def get_timestamps(self, t1: float = 0.0, t2: float = 0.0) -> dict[str, np.ndarray]:
        """Return timestamps for every stream (aligned if set, otherwise original).

        Parameters
        ----------
        t1, t2 : float
            Time window used for filtering.

        Returns
        -------
        dict[str, np.ndarray]
        """
        stream_to_timestamps = getattr(self, "stream_name_to_timestamps", None)
        if stream_to_timestamps is None:
            stream_to_timestamps = self.get_original_timestamps(t1=t1, t2=t2)
        stream_to_timestamps = {name: ts[ts >= t1] for name, ts in stream_to_timestamps.items()}
        if t2 == 0.0:
            return stream_to_timestamps
        return {name: ts[ts <= t2] for name, ts in stream_to_timestamps.items()}

    def set_aligned_timestamps(self, stream_name_to_aligned_timestamps: dict[str, np.ndarray]) -> None:
        """Replace timestamps with externally aligned values.

        Parameters
        ----------
        stream_name_to_aligned_timestamps : dict[str, np.ndarray]
            Maps stream names to aligned timestamp arrays (seconds, common session clock).
        """
        self.stream_name_to_timestamps = stream_name_to_aligned_timestamps

    def set_aligned_starting_time(self, aligned_starting_time: float, t1: float = 0.0, t2: float = 0.0) -> None:
        """Shift all timestamps by a fixed offset.

        Parameters
        ----------
        aligned_starting_time : float
            Offset to add to all original timestamps.
        t1, t2 : float
            Time window for the original timestamps.
        """
        stream_name_to_timestamps = self.get_timestamps(t1=t1, t2=t2)
        self.set_aligned_timestamps(
            {name: ts + aligned_starting_time for name, ts in stream_name_to_timestamps.items()}
        )

    def get_original_starting_time_and_rate(
        self, t1: float = 0.0, t2: float = 0.0
    ) -> dict[str, tuple[float, float]]:
        """Derive starting time and sampling rate from the stored Time datasets.

        Parameters
        ----------
        t1, t2 : float
            Time window.

        Returns
        -------
        dict[str, tuple[float, float]]
            Maps stream names to ``(starting_time_in_s, rate_in_Hz)``.
        """
        result: dict[str, tuple[float, float]] = {}
        original_timestamps = self.get_original_timestamps(t1=t1, t2=t2)
        for stream_name, timestamps in original_timestamps.items():
            starting_time = float(timestamps[0]) if len(timestamps) > 0 else 0.0
            if len(timestamps) > 1:
                rate = float(1.0 / np.mean(np.diff(timestamps)))
            else:
                rate = float("nan")
            result[stream_name] = (starting_time, rate)
        return result

    def get_starting_time_and_rate(
        self, t1: float = 0.0, t2: float = 0.0
    ) -> dict[str, tuple[float, float]]:
        """Return starting time and rate (aligned if set, otherwise original).

        Parameters
        ----------
        t1, t2 : float
            Time window.
        """
        stream_name_to_starting_time_and_rate = getattr(self, "stream_name_to_starting_time_and_rate", None)
        if stream_name_to_starting_time_and_rate is None:
            stream_name_to_starting_time_and_rate = self.get_original_starting_time_and_rate(t1=t1, t2=t2)
        return stream_name_to_starting_time_and_rate

    def set_aligned_starting_time_and_rate(
        self, stream_name_to_aligned_starting_time_and_rate: dict[str, tuple[float, float]]
    ) -> None:
        """Set aligned starting time and rate for all streams.

        Parameters
        ----------
        stream_name_to_aligned_starting_time_and_rate : dict[str, tuple[float, float]]
            Maps stream names to ``(starting_time_in_s, rate_in_Hz)``.
        """
        self.stream_name_to_starting_time_and_rate = stream_name_to_aligned_starting_time_and_rate

    # ------------------------------------------------------------------
    # NWB conversion
    # ------------------------------------------------------------------

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *,
        stub_test: bool = False,
        t1: float = 0.0,
        t2: float = 0.0,
        timing_source: Literal["original", "aligned_timestamps", "aligned_starting_time_and_rate"] = "original",
    ) -> None:
        """Add fiber photometry data to an NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            The in-memory object to add the data to.
        metadata : dict
            Metadata dictionary.  The ``metadata["Ophys"]["FiberPhotometry"]`` block
            must contain device models, devices, optical fibers, indicators,
            ``FiberPhotometryTable``, and ``FiberPhotometryResponseSeries`` — each
            ``FiberPhotometryResponseSeries`` entry must include a ``stream_name``
            that matches a name returned by :py:meth:`get_stream_names`.
        stub_test : bool, optional
            If True, load only 1 second of data (requires ``t2 == 0.0``).
        t1 : float, optional
            Start time in seconds (original file clock), default = 0.
        t2 : float, optional
            End time in seconds (original file clock), default = 0 (read to end).
        timing_source : str, optional
            One of ``"original"`` (use timestamps from file), ``"aligned_timestamps"``
            (use timestamps set via :py:meth:`set_aligned_timestamps`), or
            ``"aligned_starting_time_and_rate"`` (use values set via
            :py:meth:`set_aligned_starting_time_and_rate`).
        """
        from ndx_fiber_photometry import (
            FiberPhotometry,
            FiberPhotometryIndicators,
            FiberPhotometryResponseSeries,
            FiberPhotometryTable,
            FiberPhotometryViruses,
            FiberPhotometryVirusInjections,
        )
        from ndx_ophys_devices import (
            FiberInsertion,
            Indicator,
            OpticalFiber,
            ViralVector,
            ViralVectorInjection,
        )

        if stub_test:
            assert (
                t2 == 0.0
            ), f"stub_test cannot be used with a specified t2 ({t2}). Use t2=0.0 for stub_test or set stub_test=False."
            t2 = t1 + 1.0

        if timing_source == "aligned_timestamps":
            stream_name_to_timestamps = self.get_timestamps(t1=t1, t2=t2)
        elif timing_source == "aligned_starting_time_and_rate":
            stream_name_to_starting_time_and_rate = self.get_starting_time_and_rate(t1=t1, t2=t2)
        else:
            assert timing_source == "original", (
                "timing_source must be one of 'original', 'aligned_timestamps', or 'aligned_starting_time_and_rate'."
            )

        # ── Device models ────────────────────────────────────────────────────────
        device_model_types = [
            "OpticalFiberModel",
            "ExcitationSourceModel",
            "PhotodetectorModel",
            "BandOpticalFilterModel",
            "EdgeOpticalFilterModel",
            "DichroicMirrorModel",
        ]
        for device_type in device_model_types:
            for device_meta in metadata["Ophys"]["FiberPhotometry"].get(device_type + "s", []):
                add_ophys_device_model(nwbfile=nwbfile, device_metadata=device_meta, device_type=device_type)

        # ── Devices ──────────────────────────────────────────────────────────────
        device_types = [
            "ExcitationSource",
            "Photodetector",
            "BandOpticalFilter",
            "EdgeOpticalFilter",
            "DichroicMirror",
        ]
        for device_type in device_types:
            for device_meta in metadata["Ophys"]["FiberPhotometry"].get(device_type + "s", []):
                add_ophys_device(nwbfile=nwbfile, device_metadata=device_meta, device_type=device_type)

        # ── Optical fibers (special case: each has a FiberInsertion) ─────────────
        for optical_fiber_meta in metadata["Ophys"]["FiberPhotometry"].get("OpticalFibers", []):
            fiber_insertion = FiberInsertion(**optical_fiber_meta["fiber_insertion"])
            of_meta = deepcopy(optical_fiber_meta)
            of_meta["fiber_insertion"] = fiber_insertion
            assert of_meta["model"] in nwbfile.device_models, (
                f"Device model {of_meta['model']} not found in NWBFile device_models for {of_meta['name']}."
            )
            of_meta["model"] = nwbfile.device_models[of_meta["model"]]
            nwbfile.add_device(OpticalFiber(**of_meta))

        # ── Viral vectors, injections, and indicators ─────────────────────────────
        name_to_viral_vector: dict[str, ViralVector] = {}
        for vv_meta in metadata["Ophys"]["FiberPhotometry"].get("FiberPhotometryViruses", []):
            vv = ViralVector(**vv_meta)
            name_to_viral_vector[vv.name] = vv
        viruses = FiberPhotometryViruses(viral_vectors=list(name_to_viral_vector.values())) if name_to_viral_vector else None

        name_to_injection: dict[str, ViralVectorInjection] = {}
        for inj_meta in metadata["Ophys"]["FiberPhotometry"].get("FiberPhotometryVirusInjections", []):
            inj_meta = deepcopy(inj_meta)
            inj_meta["viral_vector"] = name_to_viral_vector[inj_meta["viral_vector"]]
            inj = ViralVectorInjection(**inj_meta)
            name_to_injection[inj.name] = inj
        virus_injections = (
            FiberPhotometryVirusInjections(viral_vector_injections=list(name_to_injection.values()))
            if name_to_injection
            else None
        )

        name_to_indicator: dict[str, Indicator] = {}
        for ind_meta in metadata["Ophys"]["FiberPhotometry"].get("FiberPhotometryIndicators", []):
            if "viral_vector_injection" in ind_meta:
                ind_meta = deepcopy(ind_meta)
                ind_meta["viral_vector_injection"] = name_to_injection[ind_meta["viral_vector_injection"]]
            ind = Indicator(**ind_meta)
            name_to_indicator[ind.name] = ind
        if not name_to_indicator:
            raise ValueError("At least one indicator must be specified in the metadata.")
        indicators = FiberPhotometryIndicators(indicators=list(name_to_indicator.values()))

        # ── FiberPhotometryTable ──────────────────────────────────────────────────
        table_meta = metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryTable"]
        fiber_photometry_table = FiberPhotometryTable(
            name=table_meta["name"],
            description=table_meta["description"],
        )
        required_fields = [
            "location",
            "excitation_wavelength_in_nm",
            "emission_wavelength_in_nm",
            "indicator",
            "optical_fiber",
            "excitation_source",
            "photodetector",
        ]
        device_fields = [
            "optical_fiber",
            "excitation_source",
            "photodetector",
            "dichroic_mirror",
            "excitation_filter",
            "emission_filter",
        ]
        for row_meta in table_meta["rows"]:
            for field in required_fields:
                assert field in row_meta, (
                    f"FiberPhotometryTable metadata row is missing required field '{field}'."
                )
            row_data = {f: nwbfile.devices[row_meta[f]] for f in device_fields if f in row_meta}
            row_data["location"] = row_meta["location"]
            row_data["excitation_wavelength_in_nm"] = row_meta["excitation_wavelength_in_nm"]
            row_data["emission_wavelength_in_nm"] = row_meta["emission_wavelength_in_nm"]
            row_data["indicator"] = name_to_indicator[row_meta["indicator"]]
            if "coordinates" in row_meta:
                row_data["coordinates"] = row_meta["coordinates"]
            fiber_photometry_table.add_row(**row_data)

        fp_lab_meta = FiberPhotometry(
            name="fiber_photometry",
            fiber_photometry_table=fiber_photometry_table,
            fiber_photometry_viruses=viruses,
            fiber_photometry_virus_injections=virus_injections,
            fiber_photometry_indicators=indicators,
        )
        nwbfile.add_lab_meta_data(fp_lab_meta)

        # ── FiberPhotometryResponseSeries ─────────────────────────────────────────
        for series_meta in metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"]:
            stream_name = series_meta["stream_name"]
            data, file_timestamps = self._load_stream_array(stream_name, t1=t1, t2=t2)

            if timing_source == "aligned_timestamps":
                timing_kwargs = dict(timestamps=stream_name_to_timestamps[stream_name])
            elif timing_source == "aligned_starting_time_and_rate":
                starting_time, rate = stream_name_to_starting_time_and_rate[stream_name]
                timing_kwargs = dict(starting_time=starting_time, rate=rate)
            else:
                timing_kwargs = dict(timestamps=file_timestamps)

            region = fiber_photometry_table.create_fiber_photometry_table_region(
                description=series_meta["fiber_photometry_table_region_description"],
                region=series_meta["fiber_photometry_table_region"],
            )
            nwbfile.add_acquisition(
                FiberPhotometryResponseSeries(
                    name=series_meta["name"],
                    description=series_meta["description"],
                    data=data,
                    unit=series_meta["unit"],
                    fiber_photometry_table_region=region,
                    **timing_kwargs,
                )
            )
