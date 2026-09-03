"""Base interface for single-series fiber photometry data.

A ``BaseFiberPhotometryInterface`` writes exactly **one** ``FiberPhotometryResponseSeries`` to an
NWBFile, assembled from one or more input *streams* (atomic source signals, e.g. TDT stores or Doric
datasets). All the shared containers (device models, devices, optical fibers, indicators, viral
vectors/injections, the ``FiberPhotometryTable``, and any ``CommandedVoltageSeries``) live under
``metadata["FiberPhotometry"]`` as name-keyed lists and are built **once** per file — the
first interface to run assembles them from the (converter-merged) metadata and subsequent interfaces
reuse them. Multiple response series therefore means multiple interfaces sharing one table, exactly
like several ecephys recording interfaces sharing one electrodes table.

Child interfaces implement only the format-reading seam:

* ``get_available_streams(...)`` — discover atomic source streams (a classmethod/staticmethod so a
  converter can be authored before construction).
* ``_get_stream_data(stream_name)`` — return time-major data for one stream.
* ``_get_stream_timestamps(stream_name)`` — return the timestamps for one stream.
* ``get_metadata`` — enrich the base metadata with whatever the format embeds (e.g. session start time).
"""

import warnings
from abc import abstractmethod
from typing import Literal

import numpy as np
from pynwb.file import NWBFile

from ..._temporal_alignment import _TemporalAlignment
from ...basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ...tools.fiber_photometry import (
    add_commanded_voltage_series,
    add_fiber_photometry_devices,
    add_fiber_photometry_lab_metadata,
    get_fiber_photometry_table_region,
)
from ...tools.nwb_helpers import get_module
from ...utils import DeepDict, dict_deep_update, get_base_schema
from ...utils.checks import calculate_regular_series_rate

__all__ = ["BaseFiberPhotometryInterface"]


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
            Key under ``metadata["FiberPhotometry"]`` holding this interface's response-series
            metadata. When ``None`` (default), it is generated from ``stream_names`` (e.g. stream
            ``"_405R"`` gives ``"fiber_photometry_405r"``), so multiple interfaces over different streams
            already get distinct keys. Pass an explicit value to override.
        stream_indices : list of int, optional
            Column indices selecting which columns of the (column-stacked) stream data to keep.
            ``None`` (default) keeps all columns.
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
        # Alignment by composition, the same component the events interfaces hold. This interface writes one
        # response series, so it names one time-bearing object, under the same key its metadata uses. The
        # native times are registered as a callable, so naming the object reads nothing.
        # See neuroconv/_temporal_alignment.py.
        self.alignment = _TemporalAlignment()
        self.alignment._register_series(key=self.metadata_key, get_native_times=self.get_original_timestamps)
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

        Shaped ``(num_samples,)`` or ``(num_samples, num_columns)``.
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
        """Return the times this interface's response series will be written on.

        .. deprecated::
            Use ``interface.alignment[key].get_times()``, which reads the object it names rather than
            assuming the interface writes one. Removed in v0.12.0.
        """
        warnings.warn(
            "`get_timestamps` is deprecated and will be removed in v0.12.0. "
            "Use `interface.alignment[key].get_times()` instead.",
            FutureWarning,
            stacklevel=2,
        )
        return self.alignment[self.metadata_key].get_times()

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        """Replace this interface's timestamps with externally aligned values.

        .. deprecated::
            Use ``interface.alignment[key].set_times(aligned_timestamps)``, which does the same thing and
            names the object it lands on. Removed in v0.12.0.
        """
        warnings.warn(
            "`set_aligned_timestamps` is deprecated and will be removed in v0.12.0. "
            "Use `interface.alignment[key].set_times(times)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        self.alignment[self.metadata_key].set_times(aligned_timestamps)

    def set_aligned_starting_time(self, aligned_starting_time: float) -> None:
        """Shift this interface's times by ``aligned_starting_time`` seconds.

        .. deprecated::
            Use ``interface.alignment.shift_times(delta)``, which is the same rigid shift under a name that
            says so. Removed in v0.12.0.
        """
        warnings.warn(
            "`set_aligned_starting_time` is deprecated and will be removed in v0.12.0. "
            "Use `interface.alignment.shift_times(delta)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        self.alignment.shift_times(aligned_starting_time)

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray) -> None:
        """Re-time this interface against a reference clock through synchronization pulses.

        .. deprecated::
            Use ``interface.alignment.remap_times(local_sync_times=..., reference_sync_times=...)``, whose
            argument names say which clock each set of pulses came off. Removed in v0.12.0.
        """
        warnings.warn(
            "`align_by_interpolation` is deprecated and will be removed in v0.12.0. Use "
            "`interface.alignment.remap_times(local_sync_times=..., reference_sync_times=...)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        self.alignment.remap_times(local_sync_times=unaligned_timestamps, reference_sync_times=aligned_timestamps)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        series_metadata = dict(name="FiberPhotometryResponseSeries")
        return dict_deep_update(metadata, dict(FiberPhotometry={self.metadata_key: series_metadata}))

    def _get_number_of_traces(self) -> int:
        """Return how many traces this interface's response series carries, one per table row.

        Reads the data to measure it. Formats that can answer from a header should override this.
        """
        data = self._read_response_data()
        return 1 if data.ndim == 1 else data.shape[1]

    def get_metadata_template(self) -> DeepDict:
        """Return the full fiber photometry provenance chain, sized to this interface's traces.

        The counterpart to :meth:`get_metadata`, which reports only what the source recorded and so
        leaves a user no indication of what else the file needs. This returns those same values wrapped
        in the structure the writer expects. Fill in the blanks and pass the result to ``add_to_nwbfile``
        or ``run_conversion``; a blank still ``None`` at write time is an error rather than a value.

        One ``FiberPhotometryTable`` row per trace, one optical fiber per row, and a shared excitation
        source, photodetector and indicator, since one interface writes one series and
        `ndx-fiber-photometry
        <https://github.com/catalystneuro/ndx-fiber-photometry#recommended-organization-of-response-series>`_
        recommends one series per excitation/emission wavelength with one column per fiber.

        The wiring is done for you: every ``*_metadata_key`` cross-reference is resolved and the series'
        ``fiber_photometry_table_region`` already lists the row keys in column order. What is left
        ``None`` is what only the experimenter can supply, the brain region each fiber sits in, the two
        wavelengths, the indicator's label and the fiber insertion geometry. Rename the keys to suit the
        recording; they are handles, not names in the file.
        """
        number_of_traces = self._get_number_of_traces()

        row_keys = [f"trace_{index}" for index in range(number_of_traces)]
        optical_fiber_keys = [f"optical_fiber_{index}" for index in range(number_of_traces)]
        excitation_source_key = "excitation_source"
        photodetector_key = "photodetector"
        indicator_key = "indicator"

        # Every entry's ``name`` is blank, and deliberately so: an entry all of whose fields are
        # satisfied reaches no check and is written as stated, so a user who leaves an offered one in
        # place gets hardware the rig never had. Every NWB object requires a name, which makes it the
        # one field that can carry that blank for any entry in any modality.
        devices = {
            optical_fiber_key: dict(
                type="OpticalFiber",
                name=None,
                fiber_insertion=dict(
                    insertion_position_ap_in_mm=None,
                    insertion_position_ml_in_mm=None,
                    insertion_position_dv_in_mm=None,
                    depth_in_mm=None,
                ),
            )
            for optical_fiber_key in optical_fiber_keys
        }
        devices[excitation_source_key] = dict(type="ExcitationSource", name=None)
        devices[photodetector_key] = dict(type="Photodetector", name=None)
        # Optional hardware, offered so a user knows the writer accepts it. Delete what the recording
        # did not use; a blank left behind is refused at write time rather than guessed at.
        # ``BandOpticalFilter`` rather than a generic optical filter, as ndx-ophys-devices has no such
        # class: a filter is a band or an edge one, and the band is the common case here. Swap the type
        # for ``EdgeOpticalFilter`` if that is what the rig used. The wavelengths belong to the filter's
        # model rather than to the filter, so the device itself carries nothing but its name.
        devices["dichroic_mirror"] = dict(type="DichroicMirror", name=None)
        devices["excitation_filter"] = dict(type="BandOpticalFilter", name=None)
        devices["emission_filter"] = dict(type="BandOpticalFilter", name=None)

        # Models carry the make and catalog specifications, shared by every recording that used the same
        # equipment. Optional: fill one and point its device at it, or delete both.
        device_models = {
            "optical_fiber_model": dict(
                type="OpticalFiberModel", name=None, manufacturer=None, numerical_aperture=None
            ),
            "excitation_source_model": dict(
                type="ExcitationSourceModel",
                name=None,
                manufacturer=None,
                source_type=None,
                excitation_mode=None,
            ),
            "photodetector_model": dict(type="PhotodetectorModel", name=None, manufacturer=None, detector_type=None),
        }
        for device_metadata in devices.values():
            device_metadata.setdefault("device_model_metadata_key", None)

        fiber_photometry = dict(
            FiberPhotometryIndicators={indicator_key: dict(name=None, label=None)},
            FiberPhotometryTable=dict(
                name="fiber_photometry_table",
                description="Each row describes one trace: the fiber, hardware and indicator that produced it.",
                rows={
                    row_key: dict(
                        location=None,
                        excitation_wavelength_in_nm=None,
                        emission_wavelength_in_nm=None,
                        indicator_metadata_key=indicator_key,
                        optical_fiber_metadata_key=optical_fiber_key,
                        excitation_source_metadata_key=excitation_source_key,
                        photodetector_metadata_key=photodetector_key,
                        coordinates=None,
                        notes=None,
                        dichroic_mirror_metadata_key=None,
                        excitation_filter_metadata_key=None,
                        emission_filter_metadata_key=None,
                    )
                    for row_key, optical_fiber_key in zip(row_keys, optical_fiber_keys)
                },
            ),
        )
        fiber_photometry[self.metadata_key] = dict(fiber_photometry_table_region=row_keys, description=None)

        template = DeepDict(dict(DeviceModels=device_models, Devices=devices, FiberPhotometry=fiber_photometry))

        # The blanks are a floor rather than an override: whatever the source recorded wins over the
        # template, so a field the interface was able to read is never handed back as one to fill in.
        template.deep_update(self.get_metadata())
        return template

    def get_metadata_schema(self) -> dict:
        """Return a permissive schema for the ``FiberPhotometry`` block.

        The device registries are declared centrally in ``base_metadata_schema.json``, so only
        ``FiberPhotometry`` still needs an escape hatch here, until it gets a declaration of its own.
        """
        metadata_schema = super().get_metadata_schema()
        for tag in ("FiberPhotometry",):
            metadata_schema["properties"][tag] = get_base_schema(tag=tag)
            metadata_schema["properties"][tag]["additionalProperties"] = True
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

    def _validate_metadata(self, fiber_photometry_metadata: dict) -> None:
        """Enforce that a table region and a ``FiberPhotometryTable`` are provided together, or neither.

        Fiber photometry provenance is all-or-nothing: either supply nothing beyond the response series
        (a bare series is a legal NWB write, since ``fiber_photometry_table_region`` is optional) or supply
        the complete chain. This checks the one invariant that would otherwise fail cryptically — a series
        referencing a table region with no table, or a table with no series referencing it. The remaining
        completeness (required row fields, resolvable device/indicator references) is enforced loudly by the
        ``add_*`` helpers when the table is built.
        """
        table_present = "FiberPhotometryTable" in fiber_photometry_metadata
        region_present = "fiber_photometry_table_region" in fiber_photometry_metadata[self.metadata_key]
        if region_present and not table_present:
            raise ValueError(
                f"Response series '{self.metadata_key}' has a 'fiber_photometry_table_region' but no "
                "'FiberPhotometryTable' metadata is provided. Provide the full FiberPhotometry chain "
                "(devices, indicators, and table) or remove the table region for a bare response series."
            )
        if table_present and not region_present:
            raise ValueError(
                "A 'FiberPhotometryTable' is provided but response series "
                f"'{self.metadata_key}' has no 'fiber_photometry_table_region' referencing it. Add a "
                "'fiber_photometry_table_region' to the series metadata."
            )

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        stub_samples: int = 100,
        always_write_timestamps: bool = False,
        parent_container: Literal["acquisition", "processing/ophys"] = "acquisition",
    ) -> None:
        """Add this interface's ``FiberPhotometryResponseSeries`` (and, once, the shared containers).

        With the default metadata (see :meth:`get_metadata`) this writes only a bare
        ``FiberPhotometryResponseSeries`` — no devices, indicators, or ``FiberPhotometryTable`` are
        fabricated. When the full provenance chain is supplied in the metadata, the
        shared containers (devices, indicators, table, commanded voltage) are added through idempotent
        helpers: the first interface to run builds them and subsequent interfaces reuse them. Timing is
        written as ``starting_time`` + ``rate`` when the timestamps are regular, otherwise as an explicit
        timestamps array.

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
        parent_container : {"acquisition", "processing/ophys"}, default: "acquisition"
            The NWBFile container to add the ``FiberPhotometryResponseSeries`` to. Use
            ``"processing/ophys"`` when the series represents processed data rather than raw acquisition.
        """
        from ndx_fiber_photometry import FiberPhotometryResponseSeries

        metadata = metadata or self.get_metadata()
        fiber_photometry_metadata = metadata["FiberPhotometry"]
        self._validate_metadata(fiber_photometry_metadata)
        series_metadata = fiber_photometry_metadata[self.metadata_key]

        def stub(array: np.ndarray) -> np.ndarray:
            return array[: min(stub_samples, len(array))] if stub_test else array

        # The shared provenance chain (devices, indicators, table, commanded voltage) is written only when
        # the user supplies it; ``_validate_metadata`` guarantees the table and this series' table region are
        # provided together, so ``table_region`` stays None exactly when no ``FiberPhotometryTable`` is given.
        table_region = None
        if "FiberPhotometryTable" in fiber_photometry_metadata:
            add_fiber_photometry_devices(nwbfile=nwbfile, metadata=metadata)

            for commanded_voltage_metadata in fiber_photometry_metadata.get("CommandedVoltageSeries", {}).values():
                commanded_voltage_stream_name = commanded_voltage_metadata["stream_name"]
                commanded_voltage_data = np.asarray(self._get_stream_data(stream_name=commanded_voltage_stream_name))
                index = commanded_voltage_metadata.get("index")
                if index is not None and commanded_voltage_data.ndim == 2:
                    commanded_voltage_data = commanded_voltage_data[:, index]
                # This series reads its own stream rather than going through get_timestamps, so the
                # alignment offset has to be applied here: a shift is interface-wide, and a commanded
                # voltage left on its native times would drift from the response series it drove.
                commanded_voltage_timestamps = (
                    self._get_stream_timestamps(stream_name=commanded_voltage_stream_name) + self.alignment.offset
                )
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
                nwbfile=nwbfile,
                fiber_photometry_metadata=fiber_photometry_metadata,
                devices_metadata=metadata["Devices"],
            )
            table_region = get_fiber_photometry_table_region(
                fiber_photometry_table=fiber_photometry_table,
                table_rows_metadata=fiber_photometry_metadata["FiberPhotometryTable"]["rows"],
                row_metadata_keys=series_metadata["fiber_photometry_table_region"],
                description=series_metadata.get(
                    "fiber_photometry_table_region_description", "fiber_photometry_table_region"
                ),
            )

        # Add this interface's single response series.
        data = stub(self._read_response_data())
        timestamps = stub(self.alignment[self.metadata_key].get_times())
        timing_kwargs = self._timing_kwargs_from_timestamps(timestamps, always_write_timestamps)

        response_series = FiberPhotometryResponseSeries(
            name=series_metadata["name"],
            description=series_metadata.get("description", ""),
            comments=series_metadata.get("comments", "no comments"),
            data=data,
            unit="a.u.",
            fiber_photometry_table_region=table_region,
            **timing_kwargs,
        )
        if parent_container == "acquisition":
            nwbfile.add_acquisition(response_series)
        elif parent_container == "processing/ophys":
            ophys_module = get_module(nwbfile, name="ophys", description="contains optical physiology processed data")
            ophys_module.add(response_series)
