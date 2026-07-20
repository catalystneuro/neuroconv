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

from abc import abstractmethod

import numpy as np
from pynwb.file import NWBFile

from ...basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ...tools.fiber_photometry import (
    add_commanded_voltage_series,
    add_fiber_photometry_devices,
    add_fiber_photometry_lab_metadata,
    get_fiber_photometry_table_region,
)
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
        """Return metadata for a single ``FiberPhotometryResponseSeries`` (name, description, unit).

        Only the response series is described; no devices, indicators, or ``FiberPhotometryTable`` are
        included. Passing this metadata to :meth:`add_to_nwbfile` writes just the response series. To also
        record the optical hardware, indicator, and table, add that metadata under ``"FiberPhotometry"``,
        ``"Devices"``, and ``"DeviceModels"``; :meth:`get_example_metadata` returns a complete template.
        """
        metadata = super().get_metadata()
        series_metadata = dict(
            name="FiberPhotometryResponseSeries",
            description="Fiber photometry response series.",
            unit="a.u.",
        )
        return dict_deep_update(metadata, dict(FiberPhotometry={self.metadata_key: series_metadata}))

    def get_example_metadata(self) -> DeepDict:
        """Return a fully specified example of the metadata this interface consumes, with realistic values.

        This is a discovery aid: call it to see the complete provenance chain — device models, devices,
        an indicator, a ``FiberPhotometryTable`` row, and this interface's response series (referencing the
        row via ``fiber_photometry_table_region``) — filled with realistic illustrative values. Edit the
        fields you need, discard the rest, and pass the result to :meth:`add_to_nwbfile`. Each call returns
        an independent copy. Unlike :meth:`get_metadata`, nothing here is inferred from the source; the
        values are examples, not defaults.
        """
        metadata = self.get_metadata()
        device_models = dict(
            optical_fiber_model=dict(
                type="OpticalFiberModel",
                name="optical_fiber_model",
                manufacturer="Doric Lenses",
                numerical_aperture=0.48,
            ),
            excitation_source_model=dict(
                type="ExcitationSourceModel",
                name="excitation_source_model",
                manufacturer="Doric Lenses",
                source_type="LED",
                excitation_mode="one-photon",
            ),
            photodetector_model=dict(
                type="PhotodetectorModel",
                name="photodetector_model",
                manufacturer="Doric Lenses",
                detector_type="photodiode",
            ),
        )
        devices = dict(
            optical_fiber=dict(
                type="OpticalFiber",
                name="optical_fiber",
                device_model_metadata_key="optical_fiber_model",
                fiber_insertion=dict(depth_in_mm=4.0, insertion_position_ap_in_mm=3.0),
            ),
            excitation_source_calcium_signal=dict(
                type="ExcitationSource",
                name="excitation_source_calcium_signal",
                device_model_metadata_key="excitation_source_model",
            ),
            excitation_source_isosbestic_control=dict(
                type="ExcitationSource",
                name="excitation_source_isosbestic_control",
                device_model_metadata_key="excitation_source_model",
            ),
            photodetector=dict(
                type="Photodetector",
                name="photodetector",
                device_model_metadata_key="photodetector_model",
            ),
        )
        fiber_photometry = dict(
            FiberPhotometryIndicators=dict(indicator=dict(name="indicator", label="GCaMP6s")),
            FiberPhotometryTable=dict(
                name="fiber_photometry_table",
                description=(
                    "Each row describes a single fiber photometry channel, linking it to the optical fiber, "
                    "excitation source, photodetector, and indicator used to acquire it."
                ),
                rows=dict(
                    calcium_signal=dict(
                        location="VTA",
                        excitation_wavelength_in_nm=470.0,
                        emission_wavelength_in_nm=525.0,
                        indicator_metadata_key="indicator",
                        optical_fiber_metadata_key="optical_fiber",
                        excitation_source_metadata_key="excitation_source_calcium_signal",
                        photodetector_metadata_key="photodetector",
                    ),
                    isosbestic_control=dict(
                        location="VTA",
                        excitation_wavelength_in_nm=405.0,
                        emission_wavelength_in_nm=525.0,
                        indicator_metadata_key="indicator",
                        optical_fiber_metadata_key="optical_fiber",
                        excitation_source_metadata_key="excitation_source_isosbestic_control",
                        photodetector_metadata_key="photodetector",
                    ),
                ),
            ),
        )
        fiber_photometry[self.metadata_key] = dict(
            fiber_photometry_table_region=["calcium_signal", "isosbestic_control"],
            fiber_photometry_table_region_description=(
                "The calcium-dependent signal and isosbestic control channels recorded from the optical fiber."
            ),
        )
        example = dict(DeviceModels=device_models, Devices=devices, FiberPhotometry=fiber_photometry)
        return dict_deep_update(metadata, example)

    def get_metadata_schema(self) -> dict:
        """Return a permissive schema for the ``FiberPhotometry`` and top-level device metadata blocks."""
        metadata_schema = super().get_metadata_schema()
        for tag in ("FiberPhotometry", "Devices", "DeviceModels"):
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
                "(see get_example_metadata) or remove the table region for a bare response series."
            )
        if table_present and not region_present:
            raise ValueError(
                "A 'FiberPhotometryTable' is provided but response series "
                f"'{self.metadata_key}' has no 'fiber_photometry_table_region' referencing it. Add a "
                "'fiber_photometry_table_region' to the series metadata (see get_example_metadata)."
            )

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        stub_samples: int = 100,
        always_write_timestamps: bool = False,
    ) -> None:
        """Add this interface's ``FiberPhotometryResponseSeries`` (and, once, the shared containers).

        With the default metadata (see :meth:`get_metadata`) this writes only a bare
        ``FiberPhotometryResponseSeries`` — no devices, indicators, or ``FiberPhotometryTable`` are
        fabricated. When the full provenance chain is supplied (see :meth:`get_example_metadata`), the
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
                nwbfile=nwbfile,
                fiber_photometry_metadata=fiber_photometry_metadata,
                devices_metadata=metadata["Devices"],
            )
            table_region = get_fiber_photometry_table_region(
                fiber_photometry_table=fiber_photometry_table,
                table_rows_metadata=fiber_photometry_metadata["FiberPhotometryTable"]["rows"],
                row_metadata_keys=series_metadata["fiber_photometry_table_region"],
                description=series_metadata["fiber_photometry_table_region_description"],
            )

        # Add this interface's single response series.
        data = stub(self._read_response_data())
        timestamps = stub(self.get_timestamps())
        timing_kwargs = self._timing_kwargs_from_timestamps(timestamps, always_write_timestamps)

        response_series = FiberPhotometryResponseSeries(
            name=series_metadata["name"],
            description=series_metadata["description"],
            data=data,
            unit=series_metadata["unit"],
            fiber_photometry_table_region=table_region,
            **timing_kwargs,
        )
        nwbfile.add_acquisition(response_series)
