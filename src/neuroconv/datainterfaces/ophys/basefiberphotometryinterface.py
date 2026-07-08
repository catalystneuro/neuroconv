"""Base interface for single-series fiber photometry data.

A ``BaseFiberPhotometryInterface`` writes exactly **one** ``FiberPhotometryResponseSeries`` to an
NWBFile, assembled from one or more input *streams* (atomic source signals, e.g. TDT stores or Doric
datasets). All the shared containers (device models, devices, optical fibers, indicators, viral
vectors/injections, the ``FiberPhotometryTable``, and any ``CommandedVoltageSeries``) live under
``metadata["Ophys"]["FiberPhotometry"]`` as name-keyed lists and are built **once** per file — the
first interface to run assembles them from the (converter-merged) metadata and subsequent interfaces
reuse them. Multiple response series therefore means multiple interfaces sharing one table, exactly
like several ecephys recording interfaces sharing one electrodes table.

Child interfaces implement only the format-reading seam:

* ``get_available_streams(...)`` — discover atomic source streams (a classmethod/staticmethod so a
  converter can be authored before construction).
* ``_get_stream_data(stream_name)`` — return time-major data for one stream.
* ``_get_stream_timestamps(stream_name)`` — return the timestamps for one stream.
* ``get_metadata`` — enrich the base scaffold with whatever the format embeds (e.g. session start time).
"""

import warnings
from abc import abstractmethod

import numpy as np
from pynwb.file import NWBFile

from ...basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ...tools.fiber_photometry import (
    FIBER_PHOTOMETRY_PLACEHOLDER,
    add_commanded_voltage_series,
    add_fiber_photometry_lab_metadata,
    add_ophys_device,
    add_ophys_device_model,
    add_optical_fibers,
    get_default_fiber_photometry_metadata,
    get_fiber_photometry_table_region,
)
from ...utils import DeepDict, dict_deep_update, get_base_schema
from ...utils.checks import calculate_regular_series_rate

__all__ = ["BaseFiberPhotometryInterface", "FIBER_PHOTOMETRY_PLACEHOLDER"]

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
    """Base class for single-series fiber photometry interfaces (one ``FiberPhotometryResponseSeries``)."""

    keywords = ("fiber photometry",)

    def __init__(
        self,
        *,
        stream_names: str | list[str],
        metadata_key: str | None = None,
        stream_indices: list[int] | None = None,
        verbose: bool = False,
        **source_data,
    ):
        """Initialize a single-series fiber photometry interface.

        Parameters
        ----------
        stream_names : str or list of str
            The input stream(s) — atomic source signals (e.g. TDT stores) — whose samples are
            column-stacked into this interface's single ``FiberPhotometryResponseSeries``.
        metadata_key : str, optional
            Key under ``metadata["Ophys"]["FiberPhotometry"]`` holding this interface's response-series
            metadata. When ``None`` (default), it is generated from ``stream_names`` (e.g. stream
            ``"_405R"`` gives ``"fiber_photometry_405r"``), so multiple interfaces over different streams
            already get distinct keys. Pass an explicit value to override.
        stream_indices : list of int, optional
            Column indices selecting which channels of the (column-stacked) stream data to keep.
            ``None`` (default) keeps all channels.
        verbose : bool, default: False
            Whether to print status messages.
        **source_data
            Format-specific source arguments (e.g. ``folder_path`` or ``file_path``).
        """
        self.stream_names = [stream_names] if isinstance(stream_names, str) else list(stream_names)
        self.stream_indices = stream_indices
        if metadata_key is None:
            stream_parts = [str(name).replace(" ", "_").strip("_").lower() for name in self.stream_names]
            metadata_key = "_".join(["fiber_photometry", *stream_parts])
        self.metadata_key = metadata_key
        self._aligned_timestamps: np.ndarray | None = None
        super().__init__(verbose=verbose, stream_names=stream_names, **source_data)
        # Keep the ndx extensions registered so pynwb IO works correctly.
        import ndx_fiber_photometry  # noqa: F401
        import ndx_ophys_devices  # noqa: F401

    # ------------------------------------------------------------------
    # Format-reading seam (implemented by children)
    # ------------------------------------------------------------------

    @abstractmethod
    def _get_stream_data(self, *, stream_name: str) -> np.ndarray:
        """Return time-major data for a single atomic source stream.

        Shaped ``(num_samples,)`` or ``(num_samples, num_channels)``.
        """
        raise NotImplementedError

    @abstractmethod
    def _get_stream_timestamps(self, *, stream_name: str) -> np.ndarray:
        """Return the timestamps (shape ``(num_samples,)``) for a single atomic source stream."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Temporal alignment API (scalar, standard)
    # ------------------------------------------------------------------

    def get_original_timestamps(self) -> np.ndarray:
        """Return the original (unaligned) timestamps of this interface's primary stream."""
        return self._get_stream_timestamps(stream_name=self.stream_names[0])

    def get_timestamps(self) -> np.ndarray:
        """Return aligned timestamps if set, otherwise the original timestamps."""
        if self._aligned_timestamps is not None:
            return self._aligned_timestamps
        return self.get_original_timestamps()

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        """Replace this interface's timestamps with externally aligned values."""
        self._aligned_timestamps = np.asarray(aligned_timestamps)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self) -> DeepDict:
        """Return the NWBFile basics combined with the default ``Ophys.FiberPhotometry`` scaffold.

        The scaffold (built by :func:`get_default_fiber_photometry_metadata`) pre-fills required
        fields with sentinels — ``NaN`` for the required numeric wavelengths and
        :data:`FIBER_PHOTOMETRY_PLACEHOLDER` for required strings — so the interface runs on zero
        user metadata. ``add_to_nwbfile`` warns about any surviving sentinel.
        """
        metadata = super().get_metadata()
        default_fiber_photometry_metadata = get_default_fiber_photometry_metadata(metadata_key=self.metadata_key)
        return dict_deep_update(metadata, default_fiber_photometry_metadata)

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

    def _read_response_data(self) -> np.ndarray:
        """Read and column-stack this interface's stream(s) into one time-major data array.

        ``stream_indices`` (if set) selects which columns of the stacked array to keep.
        """
        arrays = []
        for stream_name in self.stream_names:
            data = np.asarray(self._get_stream_data(stream_name=stream_name))
            if data.ndim == 1:
                data = data[:, np.newaxis]
            arrays.append(data)
        combined = np.concatenate(arrays, axis=1)
        if self.stream_indices is not None:
            combined = combined[:, self.stream_indices]
        if combined.shape[1] == 1:
            combined = combined[:, 0]
        return combined

    @staticmethod
    def _timing_kwargs_from_timestamps(timestamps: np.ndarray, always_write_timestamps: bool) -> dict:
        """Return ``dict(starting_time=, rate=)`` when the timestamps are regular, else ``dict(timestamps=)``.

        This is the standard NeuroConv pattern: regular series are written as ``starting_time`` + ``rate``
        (via :func:`~neuroconv.utils.checks.calculate_regular_series_rate`), otherwise the full timestamps
        array is written.
        """
        if not always_write_timestamps:
            rate = calculate_regular_series_rate(series=timestamps)
            if rate is not None:
                return dict(starting_time=float(timestamps[0]), rate=float(rate))
        return dict(timestamps=timestamps)

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
        stub_samples: int = 100,
        always_write_timestamps: bool = False,
        strict: bool = False,
    ) -> None:
        """Add this interface's ``FiberPhotometryResponseSeries`` (and, once, the shared containers).

        The shared containers (devices, indicators, table, commanded voltage) are added through
        idempotent helpers, so this method simply calls them; the first interface to run builds them
        and subsequent interfaces reuse them. Timing is written as ``starting_time`` + ``rate`` when the
        timestamps are regular, otherwise as an explicit timestamps array.

        Parameters
        ----------
        nwbfile : NWBFile
            The in-memory NWBFile to add the data to.
        metadata : dict, optional
            Metadata dictionary; defaults to ``self.get_metadata()``.
        stub_test : bool, default: False
            If True, add only the first ``stub_samples`` samples of each series for testing purposes.
        stub_samples : int, default: 100
            The number of samples to write when ``stub_test`` is True.
        always_write_timestamps : bool, default: False
            If True, always write an explicit timestamps array even when the series is regularly sampled.
        strict : bool, default: False
            If True, raise instead of warning when required metadata still holds placeholder sentinels.
        """
        from ndx_fiber_photometry import FiberPhotometryResponseSeries

        metadata = metadata or self.get_metadata()
        fiber_photometry_metadata = metadata["Ophys"]["FiberPhotometry"]
        self._warn_about_placeholder_metadata(fiber_photometry_metadata, strict=strict)

        def stub(array: np.ndarray) -> np.ndarray:
            return array[: min(stub_samples, len(array))] if stub_test else array

        # Shared containers — the helpers are idempotent, so these run unconditionally.
        for device_type in _DEVICE_MODEL_TYPES:
            for device_metadata in fiber_photometry_metadata.get(device_type + "s", []):
                add_ophys_device_model(nwbfile=nwbfile, device_metadata=device_metadata, device_type=device_type)
        for device_type in _DEVICE_TYPES:
            for device_metadata in fiber_photometry_metadata.get(device_type + "s", []):
                add_ophys_device(nwbfile=nwbfile, device_metadata=device_metadata, device_type=device_type)
        add_optical_fibers(nwbfile=nwbfile, optical_fibers_metadata=fiber_photometry_metadata.get("OpticalFibers", []))

        for commanded_voltage_metadata in fiber_photometry_metadata.get("CommandedVoltageSeries", []):
            commanded_voltage_stream_name = commanded_voltage_metadata["stream_name"]
            commanded_voltage_data = np.asarray(self._get_stream_data(stream_name=commanded_voltage_stream_name))
            index = commanded_voltage_metadata.get("index")
            if index is not None and commanded_voltage_data.ndim == 2:
                commanded_voltage_data = commanded_voltage_data[:, index]
            commanded_voltage_timestamps = self._get_stream_timestamps(stream_name=commanded_voltage_stream_name)
            add_commanded_voltage_series(
                nwbfile=nwbfile,
                name=commanded_voltage_metadata["name"],
                description=commanded_voltage_metadata.get("description", ""),
                data=stub(commanded_voltage_data),
                unit=commanded_voltage_metadata["unit"],
                frequency=commanded_voltage_metadata["frequency"],
                timing_kwargs=self._timing_kwargs_from_timestamps(
                    stub(commanded_voltage_timestamps), always_write_timestamps
                ),
            )

        fiber_photometry_table = add_fiber_photometry_lab_metadata(
            nwbfile=nwbfile, fiber_photometry_metadata=fiber_photometry_metadata
        )

        # Add this interface's single response series.
        data = stub(self._read_response_data())
        timestamps = stub(self.get_timestamps())
        timing_kwargs = self._timing_kwargs_from_timestamps(timestamps, always_write_timestamps)

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
