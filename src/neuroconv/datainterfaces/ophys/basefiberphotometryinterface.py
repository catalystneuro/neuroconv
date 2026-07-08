"""Base interface for single-stream fiber photometry data.

A ``BaseFiberPhotometryInterface`` writes exactly **one** ``FiberPhotometryResponseSeries`` to an
NWBFile. All the shared, cross-stream containers (device models, devices, optical fibers, indicators,
viral vectors/injections, the ``FiberPhotometryTable``, and any ``CommandedVoltageSeries``) live under
``metadata["Ophys"]["FiberPhotometry"]`` as name-keyed lists and are built **once** per file — the
first interface to run assembles them from the (converter-merged) metadata and subsequent interfaces
reuse them. Multiple response series therefore means multiple interfaces sharing one table, exactly
like several ecephys recording interfaces sharing one electrodes table.

Child interfaces implement only the format-reading seam:

* ``get_available_streams(...)`` — discover atomic source streams (a classmethod/staticmethod so a
  converter can be authored before construction).
* ``_get_stream_data(stream_name, t1, t2)`` — return time-major ``(data, timestamps)`` for one stream.
* ``get_metadata`` — enrich the base scaffold with whatever the format embeds (e.g. session start time).
"""

import warnings
from abc import abstractmethod

import numpy as np
from pynwb.file import NWBFile

from ...basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ...tools.fiber_photometry import (
    add_commanded_voltage_series,
    add_fiber_photometry_lab_metadata,
    add_ophys_device,
    add_ophys_device_model,
    add_optical_fibers,
    get_fiber_photometry_table_region,
)
from ...utils import DeepDict, get_base_schema

#: Sentinel written into required string metadata fields the user has not filled in. It is a distinct
#: value from a deliberate ``"unknown"`` so an intentional "unknown" silences the placeholder warning.
FIBER_PHOTOMETRY_PLACEHOLDER = "PLACEHOLDER"

_DEVICE_MODEL_TYPES = [
    "OpticalFiberModel",
    "ExcitationSourceModel",
    "PhotodetectorModel",
    "BandOpticalFilterModel",
    "EdgeOpticalFilterModel",
    "DichroicMirrorModel",
]
_DEVICE_TYPES = [
    "ExcitationSource",
    "Photodetector",
    "BandOpticalFilter",
    "EdgeOpticalFilter",
    "DichroicMirror",
]


class BaseFiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """Base class for single-stream fiber photometry interfaces (one ``FiberPhotometryResponseSeries``)."""

    keywords = ("fiber photometry",)

    def __init__(
        self,
        *,
        stream_name: str | list[str],
        metadata_key: str = "FiberPhotometryResponseSeries",
        verbose: bool = False,
        **source_data,
    ):
        """Initialize a single-stream fiber photometry interface.

        Parameters
        ----------
        stream_name : str or list of str
            The atomic source stream(s) whose samples become this interface's single
            ``FiberPhotometryResponseSeries``. A list is column-stacked into one multi-channel series.
        metadata_key : str, default: "FiberPhotometryResponseSeries"
            Key under ``metadata["Ophys"]["FiberPhotometry"]`` holding this interface's response-series
            metadata. Use distinct keys when combining multiple interfaces in one converter.
        verbose : bool, default: False
            Whether to print status messages.
        **source_data
            Format-specific source arguments (e.g. ``folder_path`` or ``file_path``).
        """
        self.stream_names = [stream_name] if isinstance(stream_name, str) else list(stream_name)
        self.metadata_key = metadata_key
        self._aligned_timestamps: np.ndarray | None = None
        self._aligned_starting_time_and_rate: tuple[float, float] | None = None
        super().__init__(verbose=verbose, stream_name=stream_name, **source_data)
        # Keep the ndx extensions registered so pynwb IO works correctly.
        import ndx_fiber_photometry  # noqa: F401
        import ndx_ophys_devices  # noqa: F401

    # ------------------------------------------------------------------
    # Format-reading seam (implemented by children)
    # ------------------------------------------------------------------

    @abstractmethod
    def _get_stream_data(self, *, stream_name: str, t1: float = 0.0, t2: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        """Return time-major ``(data, timestamps)`` for a single atomic source stream.

        ``data`` is shaped ``(num_samples,)`` or ``(num_samples, num_channels)``; ``timestamps`` is
        shaped ``(num_samples,)``. ``t1``/``t2`` window the read (seconds, original clock; 0 means
        start/end).
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Temporal alignment API (scalar, standard)
    # ------------------------------------------------------------------

    def get_original_timestamps(self) -> np.ndarray:
        """Return the original (unaligned) timestamps of this interface's primary stream."""
        _, timestamps = self._get_stream_data(stream_name=self.stream_names[0])
        return timestamps

    def get_timestamps(self) -> np.ndarray:
        """Return aligned timestamps if set, otherwise the original timestamps."""
        if self._aligned_timestamps is not None:
            return self._aligned_timestamps
        return self.get_original_timestamps()

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        """Replace this interface's timestamps with externally aligned values."""
        self._aligned_timestamps = np.asarray(aligned_timestamps)

    def get_original_starting_time_and_rate(self) -> tuple[float, float]:
        """Derive ``(starting_time_in_s, rate_in_Hz)`` from the original timestamps.

        Children with an exactly known sampling rate should override this.
        """
        timestamps = self.get_original_timestamps()
        starting_time = float(timestamps[0])
        rate = float(1.0 / np.mean(np.diff(timestamps))) if len(timestamps) > 1 else float("nan")
        return starting_time, rate

    def get_starting_time_and_rate(self) -> tuple[float, float]:
        """Return aligned ``(starting_time, rate)`` if set, otherwise the original."""
        if self._aligned_starting_time_and_rate is not None:
            return self._aligned_starting_time_and_rate
        return self.get_original_starting_time_and_rate()

    def set_aligned_starting_time_and_rate(self, aligned_starting_time_and_rate: tuple[float, float]) -> None:
        """Set aligned ``(starting_time, rate)`` for this interface."""
        self._aligned_starting_time_and_rate = aligned_starting_time_and_rate

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self) -> DeepDict:
        """Return a full, editable default scaffold under ``metadata["Ophys"]["FiberPhotometry"]``.

        Required fields the user must supply are pre-filled with sentinels — ``NaN`` for the required
        numeric wavelengths and :data:`FIBER_PHOTOMETRY_PLACEHOLDER` for required strings — so the
        interface runs on zero user metadata. ``add_to_nwbfile`` warns about any surviving sentinel.
        """
        metadata = super().get_metadata()
        placeholder = FIBER_PHOTOMETRY_PLACEHOLDER
        fiber_photometry_metadata = dict(
            OpticalFiberModels=[
                dict(name="optical_fiber_model", manufacturer=placeholder, numerical_aperture=float("nan"))
            ],
            OpticalFibers=[dict(name="optical_fiber", model="optical_fiber_model", fiber_insertion=dict())],
            ExcitationSourceModels=[
                dict(
                    name="excitation_source_model",
                    manufacturer=placeholder,
                    source_type=placeholder,
                    excitation_mode=placeholder,
                )
            ],
            ExcitationSources=[dict(name="excitation_source", model="excitation_source_model")],
            PhotodetectorModels=[dict(name="photodetector_model", manufacturer=placeholder, detector_type=placeholder)],
            Photodetectors=[dict(name="photodetector", model="photodetector_model")],
            FiberPhotometryIndicators=[dict(name="indicator", label=placeholder)],
            FiberPhotometryTable=dict(
                name="fiber_photometry_table",
                description=placeholder,
                rows=[
                    dict(
                        name="row0",
                        location=placeholder,
                        excitation_wavelength_in_nm=float("nan"),
                        emission_wavelength_in_nm=float("nan"),
                        indicator="indicator",
                        optical_fiber="optical_fiber",
                        excitation_source="excitation_source",
                        photodetector="photodetector",
                    )
                ],
            ),
        )
        fiber_photometry_metadata[self.metadata_key] = dict(
            name=self.metadata_key,
            description=placeholder,
            unit="a.u.",
            fiber_photometry_table_region=["row0"],
            fiber_photometry_table_region_description=placeholder,
        )
        metadata["Ophys"] = dict(FiberPhotometry=fiber_photometry_metadata)
        return metadata

    def get_metadata_schema(self) -> dict:
        """Return a permissive schema for the ``Ophys.FiberPhotometry`` metadata block."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ophys"] = get_base_schema(tag="Ophys")
        metadata_schema["properties"]["Ophys"]["required"] = ["FiberPhotometry"]
        metadata_schema["properties"]["Ophys"]["additionalProperties"] = True
        metadata_schema["properties"]["Ophys"]["properties"] = dict(
            FiberPhotometry=dict(type="object", additionalProperties=True)
        )
        return metadata_schema

    # ------------------------------------------------------------------
    # NWB conversion
    # ------------------------------------------------------------------

    def _read_response_data(self, t1: float = 0.0, t2: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        """Read and column-stack this interface's stream(s) into one time-major array + timestamps."""
        arrays = []
        timestamps = None
        for stream_name in self.stream_names:
            data, stream_timestamps = self._get_stream_data(stream_name=stream_name, t1=t1, t2=t2)
            data = np.asarray(data)
            if data.ndim == 1:
                data = data[:, np.newaxis]
            arrays.append(data)
            if timestamps is None:
                timestamps = np.asarray(stream_timestamps)
        combined = np.concatenate(arrays, axis=1)
        if combined.shape[1] == 1:
            combined = combined[:, 0]
        return combined, timestamps

    def _warn_about_placeholder_metadata(self, fiber_photometry_metadata: dict, strict: bool) -> None:
        """Warn (or raise, if ``strict``) about required fields still holding placeholder sentinels."""
        issues = []
        for row in fiber_photometry_metadata.get("FiberPhotometryTable", {}).get("rows", []):
            row_name = row.get("name", "?")
            if row.get("location") == FIBER_PHOTOMETRY_PLACEHOLDER:
                issues.append(f"table row '{row_name}' location")
            for field in ("excitation_wavelength_in_nm", "emission_wavelength_in_nm"):
                value = row.get(field)
                if value is None or (isinstance(value, float) and np.isnan(value)):
                    issues.append(f"table row '{row_name}' {field}")
        for indicator in fiber_photometry_metadata.get("FiberPhotometryIndicators", []):
            if indicator.get("label") == FIBER_PHOTOMETRY_PLACEHOLDER:
                issues.append(f"indicator '{indicator.get('name')}' label")
        if not issues:
            return
        message = (
            "Fiber photometry metadata still contains placeholder values that should be set before "
            "archiving: " + "; ".join(issues) + "."
        )
        if strict:
            raise ValueError(message)
        warnings.warn(message, UserWarning, stacklevel=3)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        t1: float = 0.0,
        t2: float = 0.0,
        timing_source: str = "original",
        strict: bool = False,
    ) -> None:
        """Add this interface's ``FiberPhotometryResponseSeries`` (and, once, the shared containers).

        Parameters
        ----------
        nwbfile : NWBFile
            The in-memory NWBFile to add the data to.
        metadata : dict, optional
            Metadata dictionary; defaults to ``self.get_metadata()``.
        stub_test : bool, default: False
            If True, add only 1 second of data (requires ``t2 == 0.0``).
        t1 : float, default: 0.0
            Start of the time window in seconds on the original clock (0 means start of recording).
        t2 : float, default: 0.0
            End of the time window in seconds on the original clock (0 means end of recording).
        timing_source : {"original", "aligned_timestamps", "aligned_starting_time_and_rate"}
            Which timing to write for the response series.
        strict : bool, default: False
            If True, raise instead of warning when required metadata still holds placeholder sentinels.
        """
        from ndx_fiber_photometry import FiberPhotometryResponseSeries

        metadata = metadata or self.get_metadata()
        fiber_photometry_metadata = metadata["Ophys"]["FiberPhotometry"]
        self._warn_about_placeholder_metadata(fiber_photometry_metadata, strict=strict)

        if stub_test:
            assert (
                t2 == 0.0
            ), f"stub_test cannot be used with a specified t2 ({t2}). Use t2=0.0 for stub_test or set stub_test=False."
            t2 = t1 + 1.0

        assert timing_source in (
            "original",
            "aligned_timestamps",
            "aligned_starting_time_and_rate",
        ), "timing_source must be one of 'original', 'aligned_timestamps', or 'aligned_starting_time_and_rate'."

        # Build the shared containers exactly once per file (first interface to run).
        if "fiber_photometry" not in nwbfile.lab_meta_data:
            for device_type in _DEVICE_MODEL_TYPES:
                for device_metadata in fiber_photometry_metadata.get(device_type + "s", []):
                    add_ophys_device_model(nwbfile=nwbfile, device_metadata=device_metadata, device_type=device_type)
            for device_type in _DEVICE_TYPES:
                for device_metadata in fiber_photometry_metadata.get(device_type + "s", []):
                    add_ophys_device(nwbfile=nwbfile, device_metadata=device_metadata, device_type=device_type)
            add_optical_fibers(
                nwbfile=nwbfile, optical_fibers_metadata=fiber_photometry_metadata.get("OpticalFibers", [])
            )

            for commanded_voltage_metadata in fiber_photometry_metadata.get("CommandedVoltageSeries", []):
                commanded_voltage_data, commanded_voltage_timestamps = self._get_stream_data(
                    stream_name=commanded_voltage_metadata["stream_name"], t1=t1, t2=t2
                )
                index = commanded_voltage_metadata.get("index")
                if index is not None and np.asarray(commanded_voltage_data).ndim == 2:
                    commanded_voltage_data = np.asarray(commanded_voltage_data)[:, index]
                add_commanded_voltage_series(
                    nwbfile=nwbfile,
                    name=commanded_voltage_metadata["name"],
                    description=commanded_voltage_metadata.get("description", ""),
                    data=commanded_voltage_data,
                    unit=commanded_voltage_metadata["unit"],
                    frequency=commanded_voltage_metadata["frequency"],
                    timing_kwargs=dict(timestamps=commanded_voltage_timestamps),
                )

            add_fiber_photometry_lab_metadata(nwbfile=nwbfile, fiber_photometry_metadata=fiber_photometry_metadata)

        fiber_photometry_table = nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table

        # Add this interface's single response series.
        data, original_timestamps = self._read_response_data(t1=t1, t2=t2)
        if timing_source == "aligned_timestamps":
            timing_kwargs = dict(timestamps=self.get_timestamps())
        elif timing_source == "aligned_starting_time_and_rate":
            starting_time, rate = self.get_starting_time_and_rate()
            timing_kwargs = dict(starting_time=starting_time, rate=rate)
        else:
            timing_kwargs = dict(timestamps=original_timestamps)

        series_metadata = fiber_photometry_metadata[self.metadata_key]
        table_region = get_fiber_photometry_table_region(
            fiber_photometry_table=fiber_photometry_table,
            table_rows_metadata=fiber_photometry_metadata["FiberPhotometryTable"]["rows"],
            row_names=series_metadata["fiber_photometry_table_region"],
            description=series_metadata["fiber_photometry_table_region_description"],
        )
        response_series = FiberPhotometryResponseSeries(
            name=series_metadata["name"],
            description=series_metadata["description"],
            data=data,
            unit=series_metadata["unit"],
            fiber_photometry_table_region=table_region,
            **timing_kwargs,
        )
        nwbfile.add_acquisition(response_series)
