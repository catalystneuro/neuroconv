"""Interface for intracellular electrophysiology recorded by Bruker PrairieView's VoltageRecording."""

from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ._bruker_voltage_recording_readers import (
    _CycleHeader,
    _read_cycle_header,
    _read_signal_column,
)
from ....basedatainterface import BaseDataInterface
from ....tools.icephys import (
    _RESPONSE_CLASS,
    _add_intracellular_electrode_to_nwbfile,
    _add_intracellular_recordings_to_nwbfile,
)
from ....utils import (
    DeepDict,
    calculate_regular_series_rate,
    get_conversion_from_unit,
    to_camel_case,
)

# The amplifier's primary output. It is the only signal whose unit identifies the clamp mode: `Secondary`
# carries whichever complementary signal the amplifier was configured to emit, and reads `pA` on some
# current-clamp rigs and `mV` on others.
_MODE_BEARING_SIGNAL_NAME = "Primary"

# What `Primary`'s unit says about the clamp mode. NWB's own definitions make this a reading rather than a
# guess: a CurrentClampSeries holds a recorded voltage and a VoltageClampSeries a recorded current.
_UNIT_TO_MODE = {"mV": "current_clamp", "pA": "voltage_clamp"}


class BrukerVoltageRecordingInterface(BaseDataInterface):
    """
    Interface for intracellular electrophysiology recorded by Bruker PrairieView's VoltageRecording.

    PrairieView writes one CSV/XML pair per cycle, a cycle being one trigger of the acquisition and so one
    sweep. One interface instance corresponds to one electrode's cycles, given as an explicit list: nothing in
    the format states which cycles belong to which cell, so the list is the caller's assertion rather than
    something inferred from a folder layout. Those cycles are concatenated into a single continuous
    ``PatchClampSeries``, placed on one timeline by each cycle's ``DateTime``, and each is recorded through the
    NWB ``IntracellularRecordings`` table via a ``(start_index, count)`` range.

    Like the other icephys interfaces it stops there: the upper hierarchy tables (``SimultaneousRecordings`` and
    above) are built only once the full set of electrodes is known, which is
    :class:`BrukerVoltageRecordingConverter`'s job.
    """

    display_name = "Bruker VoltageRecording"
    keywords = ("intracellular electrophysiology", "patch clamp", "icephys", "bruker", "prairie view")
    associated_suffixes = (".csv", ".xml")
    info = "Interface for intracellular electrophysiology recorded by Bruker PrairieView (VoltageRecording)."

    @validate_call
    def __init__(
        self,
        file_paths: list[FilePath],
        *,
        response_signal_name: str | None = None,
        mode: Literal["voltage_clamp", "current_clamp", "izero"] | None = None,
        stimulus_type: str | None = None,
        repetition: str | None = None,
        condition: str | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_paths : list of FilePath
            The cycle CSV files of one electrode, in acquisition order. Each must have its ``VoltageRecording``
            XML beside it, as PrairieView writes it. The list is explicit because nothing in the format states
            which cycles belong together; globbing a session folder belongs in the conversion script.
        response_signal_name : str, optional
            Which recorded signal is this electrode's response, given as its name in the CSV header and the
            XML ``SignalList`` (for example ``"Primary"``). Optional while only one signal was recorded, which
            is the common case. See ``get_signal_names``.
        mode : {"voltage_clamp", "current_clamp", "izero"}, optional
            The clamp mode, which selects the NWB series class. Derived from ``Primary``'s unit when it can be
            (``mV`` for current clamp, ``pA`` for voltage clamp), so this is needed only to record an
            ``izero`` run, which is indistinguishable from ordinary current clamp in the file, or when the
            response is a signal other than ``Primary``.
        stimulus_type : str, optional
            What kind of run this was, written to the ``stimulus_type`` column and carried up to the sequential
            recording. PrairieView records no protocol section, so there is nothing to derive it from; when no
            run in the file states one the column is omitted rather than filled with a placeholder, and when
            a sibling run states one this run's rows are left empty.
        repetition : str, optional
            Label grouping this run's sequential recording with others into a ``Repetitions`` entry (the same
            protocol repeated). Used only when combining interfaces in a converter; if set on any interface it
            must be set on all of them.
        condition : str, optional
            Label grouping this run's repetition with others into an ``ExperimentalConditions`` entry. Requires
            ``repetition`` (conditions group repetitions); if set on any interface it must be set on all.
        metadata_key : str, optional
            Identity of this interface's response ``PatchClampSeries`` in the metadata dict. Defaults to the
            acquisition stem the cycles share plus the response signal name.
        verbose : bool, default: False
        """
        super().__init__(verbose=verbose)
        self._file_paths = [Path(file_path) for file_path in file_paths]
        self._repetition = repetition
        self._condition = condition
        self._stimulus_type = stimulus_type
        self._metadata_key = metadata_key
        # Seconds added to this interface's series timestamps; a converter sets it for multi-electrode
        # alignment. Default 0 leaves single-interface output unchanged.
        self._starting_time_shift = 0.0
        self.source_data = dict(
            file_paths=file_paths,
            response_signal_name=response_signal_name,
            mode=mode,
            stimulus_type=stimulus_type,
            repetition=repetition,
            condition=condition,
            metadata_key=metadata_key,
            verbose=verbose,
        )

        if not self._file_paths:
            raise ValueError("file_paths is empty; give at least one cycle CSV.")

        # Sorted by acquisition time, not by the order given. The samples are concatenated in this order and
        # timestamped from each cycle's DateTime, so the two would otherwise diverge whenever the caller's
        # list is not chronological, silently producing a non-monotonic timestamps array. `Path.glob` returns
        # filesystem order, so that is the ordinary case rather than a pathological one.
        self._cycle_headers = sorted(
            (_read_cycle_header(file_path) for file_path in self._file_paths),
            key=lambda header: header.start_datetime,
        )
        self._response_signal_name = self._resolve_response_signal_name(self._cycle_headers[0], response_signal_name)
        self._check_cycles_agree()

        self._response_signal = self._cycle_headers[0].signals[self._response_signal_name]
        self._mode = mode if mode is not None else self._derive_mode(self._response_signal)

        # The earliest cycle is this electrode's own origin, and the session's when it converts alone. A
        # converter combining electrodes reads it to place them all against the earliest of the set.
        self._recording_start_datetime = min(header.start_datetime for header in self._cycle_headers)

        # The run identity: the handle `sequence` and the electrode / series keys derive from. Defaults to the
        # acquisition stem the cycles share, which PrairieView writes into the XML's `DataFile`; a converter
        # combining electrodes overrides it with a disambiguated label, since that stem collides across
        # session folders. It is a label, not a claim about which cell this is.
        self._run_identity = self._cycle_headers[0].stem

    # Registry keys derive from the run identity so a converter that overrides `_run_identity` propagates to
    # all of them. The electrode is per run rather than per signal, because `Primary` and `Secondary` are two
    # outputs of one amplifier channel and so one electrode, unlike ABF where two response channels are two
    # electrodes. The device is the exception: it identifies the amplifier, which runs share.
    @property
    def _device_metadata_key(self) -> str:
        return self._response_signal.patchclamp_device.lower().replace(" ", "_")

    @property
    def _electrode_metadata_key(self) -> str:
        return self._run_identity

    @property
    def _series_metadata_key(self) -> str:
        return self._metadata_key or f"{self._run_identity}_{self._response_signal_name}"

    # ------------------------------------------------------------------ construction helpers

    @staticmethod
    def _resolve_response_signal_name(header: _CycleHeader, response_signal_name: str | None) -> str:
        """
        Decide which recorded signal is the response, and refuse anything that is not a patch signal.

        What was recorded comes from the XML's ``Enabled`` flags, not from the CSV header's names. The header
        names cannot be trusted: on a whole recording day of the Zhai et al. 2025 deposit they read
        ``Time(ms), Secondary, LED`` on files whose enabled signals are ``Primary`` and ``Secondary``, and a
        reader that believes them writes the membrane potential as a current. The column count is checked
        against the enabled count when the header is parsed, so the positional mapping is safe by then.

        A signal whose ``PatchclampDevice`` is empty was never routed through an amplifier (the sync,
        photodiode and wavelength channels all read that way) and is not intracellular data, so it is rejected
        here rather than written in the wrong container.
        """
        recorded_names = [signal.name for signal in header.recorded_signals]
        if response_signal_name is None:
            if len(recorded_names) != 1:
                raise ValueError(
                    f"'{header.file_path}' recorded {len(recorded_names)} signals ({', '.join(recorded_names)}), "
                    "so which one is this electrode's response is ambiguous. Pass response_signal_name."
                )
            response_signal_name = recorded_names[0]
        elif response_signal_name not in recorded_names:
            known = header.signals.get(response_signal_name)
            if known is not None:
                raise ValueError(
                    f"Signal '{response_signal_name}' is declared in '{header.xml_file_path.name}' but not "
                    f"enabled, so it was not recorded. Recorded signals: {', '.join(recorded_names)}."
                )
            raise ValueError(
                f"Signal '{response_signal_name}' does not appear in '{header.xml_file_path.name}' at all. "
                f"Recorded signals: {', '.join(recorded_names)}."
            )

        signal = header.signals[response_signal_name]
        if not signal.patchclamp_device:
            raise ValueError(
                f"Signal '{response_signal_name}' carries no PatchclampDevice, so it is not an intracellular "
                "signal but one of PrairieView's analog channels (sync, photodiode, wavelength). Those belong "
                "in a TimeSeries rather than this interface."
            )
        return response_signal_name

    @staticmethod
    def _derive_mode(signal) -> str:
        """Read the clamp mode off the response signal's unit, or raise naming the argument to pass."""
        if signal.name != _MODE_BEARING_SIGNAL_NAME:
            raise ValueError(
                f"Cannot derive the clamp mode from signal '{signal.name}' (unit '{signal.unit_name}'): only the "
                f"amplifier's '{_MODE_BEARING_SIGNAL_NAME}' output identifies the mode, since '{signal.name}' "
                "carries whichever complementary signal the amplifier was configured to emit. Pass "
                "mode='voltage_clamp' or mode='current_clamp' explicitly."
            )
        if signal.unit_name not in _UNIT_TO_MODE:
            raise ValueError(
                f"Cannot derive the clamp mode from '{signal.name}' unit '{signal.unit_name}': expected "
                "'mV' (current clamp) or 'pA' (voltage clamp). Pass mode= explicitly."
            )
        return _UNIT_TO_MODE[signal.unit_name]

    def _check_cycles_agree(self) -> None:
        """
        Fail loudly when the cycles do not describe one continuous recording of one electrode.

        They are about to become a single series with a single ``conversion``, so a change of unit, scaling,
        amplifier or sampling rate partway through cannot be represented and must not be silently averaged over.
        """
        first = self._cycle_headers[0]
        reference = first.signals[self._response_signal_name]
        reference_column = first.column_index(self._response_signal_name)
        for header in self._cycle_headers[1:]:
            recorded_names = [signal.name for signal in header.recorded_signals]
            if self._response_signal_name not in recorded_names:
                raise ValueError(
                    f"'{header.file_path}' did not record '{self._response_signal_name}' "
                    f"(it recorded {', '.join(recorded_names)}), so it is not a cycle of the same run "
                    f"as '{first.file_path}'."
                )
            # The signal must also occupy the same column, since the enabled set can be reordered between
            # cycles and a shifted column would put two different physical signals in one series.
            if header.column_index(self._response_signal_name) != reference_column:
                raise ValueError(
                    f"'{header.file_path.name}' records '{self._response_signal_name}' in column "
                    f"{header.column_index(self._response_signal_name)} while '{first.file_path.name}' has it "
                    f"in column {reference_column}. These cycles do not share one signal layout."
                )
            signal = header.signals[self._response_signal_name]
            differences = {
                "sampling rate": (first.rate, header.rate),
                "unit": (reference.unit_name, signal.unit_name),
                "multiplier": (reference.multiplier, signal.multiplier),
                "divisor": (reference.divisor, signal.divisor),
                "amplifier": (reference.patchclamp_device, signal.patchclamp_device),
            }
            for label, (expected, found) in differences.items():
                if expected != found:
                    raise ValueError(
                        f"Cycle '{header.file_path.name}' disagrees with '{first.file_path.name}' on the "
                        f"{label} of '{self._response_signal_name}' ({found!r} against {expected!r}). These "
                        "cycles cannot be one continuous series; convert them as separate interfaces."
                    )

    # ------------------------------------------------------------------ metadata

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = self._recording_start_datetime

        # The metadata-dict keys were resolved at construction. Each series entry stores its
        # electrode_metadata_key as an editable link: repointing two series at one electrode key merges them
        # onto a single electrode. `to_camel_case` is applied only here, the one place a key becomes an NWB name.
        device_metadata_key = self._device_metadata_key
        electrode_metadata_key = self._electrode_metadata_key
        series_metadata_key = self._series_metadata_key
        electrode_name_suffix = to_camel_case(electrode_metadata_key)

        # The amplifier model as PrairieView records it, kept verbatim ("Multiclamp700B Ch1") rather than
        # recased, since it is the manufacturer's own string and the same rule Axon follows for the model its
        # telegraph header reports.
        metadata["Devices"] = {
            device_metadata_key: {
                "name": self._response_signal.patchclamp_device,
                "description": "Patch-clamp amplifier (model as named by PrairieView).",
            }
        }
        metadata["Icephys"]["IntracellularElectrodes"] = {
            electrode_metadata_key: {
                "name": f"IntracellularElectrode{electrode_name_suffix}",
                "description": "Patch-clamp electrode.",
                "device_metadata_key": device_metadata_key,
            }
        }
        response_type_name = {
            "voltage_clamp": "VoltageClampSeries",
            "current_clamp": "CurrentClampSeries",
            "izero": "IZeroClampSeries",
        }[self._mode]
        metadata["Icephys"]["PatchClampSeries"] = {
            series_metadata_key: {
                "name": f"{response_type_name}{to_camel_case(series_metadata_key)}",
                "description": f"Intracellular response ({self._mode}).",
                "electrode_metadata_key": electrode_metadata_key,
            }
        }
        return metadata

    # ------------------------------------------------------------------ writing

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
    ) -> None:
        if metadata is None:
            metadata = self.get_metadata()

        response_metadata = metadata["Icephys"]["PatchClampSeries"][self._series_metadata_key]
        electrode = _add_intracellular_electrode_to_nwbfile(
            nwbfile, metadata, response_metadata["electrode_metadata_key"]
        )

        data, timestamps, sweep_sample_ranges = self._concatenate_cycles()
        # The series is written on this electrode's own clock (its earliest cycle is time zero). A lone
        # interface leaves _starting_time_shift at 0; a converter combining electrodes sets it so they share
        # one session timeline, since that resolution needs sight of all of them.
        timestamps = timestamps + self._starting_time_shift

        # The whole scale chain lives in `conversion` rather than being multiplied into the samples, so the
        # data stays exactly what PrairieView wrote: raw times Multiplier / Divisor gives the signal in its
        # stated unit, and the unit factor takes that to volts or amperes.
        signal = self._response_signal
        conversion = (signal.multiplier / signal.divisor) * get_conversion_from_unit(signal.unit_name)
        response_kwargs = dict(
            name=response_metadata["name"],
            data=data,
            electrode=electrode,
            conversion=float(conversion),
            gain=np.nan,
            description=response_metadata["description"],
        )
        # Use a uniform rate when the timestamps are regular (a single cycle, or cycles that happen to abut);
        # fall back to explicit timestamps once the intervals between cycles make them irregular.
        rate = calculate_regular_series_rate(series=timestamps)
        if rate is not None:
            response_kwargs.update(starting_time=float(timestamps[0]), rate=rate)
        else:
            response_kwargs.update(timestamps=timestamps)
        response_series = _RESPONSE_CLASS[self._mode](**response_kwargs)
        nwbfile.add_acquisition(response_series)

        self._add_intracellular_table_to_nwb(
            nwbfile,
            electrode=electrode,
            response_series=response_series,
            sweep_sample_ranges=sweep_sample_ranges,
        )

    def _add_intracellular_table_to_nwb(self, nwbfile, electrode, response_series, sweep_sample_ranges):
        """Write one IntracellularRecordings row per cycle, each addressing this electrode's continuous
        response series by the cycle's ``(start_index, count)`` range, and tag every row with the run-level
        foreign-key columns:

        - ``sequence``: the run identity, shared by every cycle, which is what an aggregator groups on to build
          a SequentialRecordings entry.
        - ``stimulus_type``: what kind of run it was, only when the caller said. PrairieView records no
          protocol, so there is nothing to derive; the column is omitted when no run in the file states one
          (:func:`~neuroconv.tools.icephys._build_icephys_hierarchical_tables` supplies the one NWB insists on
          at the sequential level).
        - ``repetition`` and ``condition``: only when the user gave them (when combining several electrodes in
          a converter), so the runs group into repetitions and experimental conditions.

        The upper tables are deliberately not built here, for the reason the other icephys interfaces give:
        constructing them is a terminal step that locks their membership, and a single interface cannot know
        whether it is the last contributor to the file.
        """
        _add_intracellular_recordings_to_nwbfile(
            nwbfile,
            electrode=electrode,
            response_series=response_series,
            sweep_sample_ranges=sweep_sample_ranges,
            sequence=self._run_identity,
            stimulus_type=self._stimulus_type,
            repetition=self._repetition,
            condition=self._condition,
        )

    # ------------------------------------------------------------------ discovery (call before constructing)

    @classmethod
    def get_signal_names(cls, file_path: FilePath) -> list[str]:
        """
        Names of the signals recorded in a cycle CSV: the options for ``response_signal_name``. Call this
        before constructing the interface to see what is available.

        Parameters
        ----------
        file_path : FilePath
            Path to one cycle's ``VoltageRecording`` CSV.

        Returns
        -------
        list of str
            The recorded signal names, in the order their columns appear. Taken from the XML's enabled
            signals rather than the CSV header, whose names are unreliable.
        """
        return [signal.name for signal in _read_cycle_header(Path(file_path)).recorded_signals]

    # ------------------------------------------------------------------ writing helpers

    def _concatenate_cycles(self):
        """Read the response signal across every cycle and lay them end to end on one timeline; return
        ``(data, timestamps, [(start_index, count), ...])``.

        Each cycle is placed at its own ``DateTime``, the earliest being this electrode's origin, which is the
        direct analogue of reading each segment's start time out of an ABF file: the intervals between cycles
        are real dead time, so they show up as gaps in the timestamps rather than being closed up.
        """
        origin = self._recording_start_datetime
        cycle_arrays = [_read_signal_column(header, self._response_signal_name) for header in self._cycle_headers]

        sweep_sample_ranges = []
        cursor = 0
        for values in cycle_arrays:
            sweep_sample_ranges.append((cursor, len(values)))
            cursor += len(values)
        total_samples = cursor

        data = np.concatenate(cycle_arrays) if len(cycle_arrays) > 1 else cycle_arrays[0]

        timestamps = np.empty(total_samples, dtype="float64")
        for header, (start_index, count) in zip(self._cycle_headers, sweep_sample_ranges):
            cycle_start_time = (header.start_datetime - origin).total_seconds()
            timestamps[start_index : start_index + count] = cycle_start_time + np.arange(count) / header.rate

        return data, timestamps, sweep_sample_ranges
