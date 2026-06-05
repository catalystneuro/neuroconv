"""Interface for intracellular electrophysiology recorded in Axon Binary Format (ABF)."""

from pathlib import PureWindowsPath
from typing import Literal

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.icephys import (
    CurrentClampSeries,
    CurrentClampStimulusSeries,
    IZeroClampSeries,
    VoltageClampSeries,
    VoltageClampStimulusSeries,
)

from ....basedatainterface import BaseDataInterface
from ....tools.icephys import _add_intracellular_electrode_to_nwbfile
from ....utils import (
    DeepDict,
    calculate_regular_series_rate,
    get_conversion_from_unit,
    to_camel_case,
)

# clamp mode -> NWB response / stimulus classes
_RESPONSE_CLASS = {
    "voltage_clamp": VoltageClampSeries,
    "current_clamp": CurrentClampSeries,
    "izero": IZeroClampSeries,
}
_STIMULUS_CLASS = {
    "voltage_clamp": VoltageClampStimulusSeries,
    "current_clamp": CurrentClampStimulusSeries,
}


def _recorded_channel_names(reader) -> list[str]:
    """
    Recorded analog-to-digital converter channel names (the `response_channel_name` / `stimulus_channel_name` options).

    neo builds each name by stripping spaces from the stored name, which can yield an empty string (see neo
    handoff Gap 4); fall back to ``ch{index}`` so every channel stays addressable by name.
    """
    names = []
    for index, channel in enumerate(reader.header["signal_channels"]):
        name = str(channel["name"]).strip()
        names.append(name or f"ch{index}")
    return names


def _dac_channel_names(reader) -> list[str]:
    """The protocol's DAC command channel names (the `stimulus_command` options); ``cmd{index}`` if blank."""
    dac_info = reader._axon_info.get("listDACInfo", [])
    names = []
    for index, dac in enumerate(dac_info):
        raw = dac["DACChNames"]
        name = (raw.decode(errors="replace") if hasattr(raw, "decode") else str(raw)).strip()
        names.append(name or f"cmd{index}")
    return names


class AxonIntracellularInterface(BaseDataInterface):
    """
    Interface for intracellular electrophysiology data recorded in Axon Binary Format (.abf).

    One interface instance corresponds to one electrode in one ABF file. It writes that electrode's
    response as a single continuous ``PatchClampSeries`` (optionally a paired stimulus series) and
    records each sweep through the NWB ``IntracellularRecordings`` table via ``(start_index, count)``
    ranges. It deliberately stops there: the upper icephys hierarchy tables (``SimultaneousRecordings``
    and above) are built only once the full set of channels and files is known, so a single interface
    stays composable with others (for example the two electrodes of a dual-patch recording).
    """

    display_name = "Axon Intracellular"
    keywords = ("intracellular electrophysiology", "patch clamp", "icephys", "axon", "abf")
    associated_suffixes = (".abf",)
    info = "Interface for intracellular electrophysiology recorded in Axon Binary Format (.abf)."

    # An ABF file is a single recording block with a single analog-signal stream (all ADC channels share one
    # sampling clock), so the neo block and stream indices are always 0.
    _BLOCK_INDEX = 0
    _STREAM_INDEX = 0

    @classmethod
    def get_extractor_class(cls):
        """Return the neo reader class used to parse ABF files."""
        from neo.rawio import AxonRawIO

        return AxonRawIO

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        response_channel_name: str,
        mode: Literal["voltage_clamp", "current_clamp", "izero"],
        stimulus_channel_name: str | None = None,
        stimulus_command: str | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the Axon Binary Format (.abf) file.
        response_channel_name : str
            The recorded analog-to-digital converter channel for this electrode's response, given as the
            channel name (for example ``"IN0"`` or ``"_Ipatch"``). See ``get_channel_names``.
        mode : {"voltage_clamp", "current_clamp", "izero"}
            The clamp mode, which selects the NWB series classes (VoltageClampSeries / CurrentClampSeries /
            IZeroClampSeries and the matching stimulus class). ABF clamp-mode metadata is unreliable, so it
            is required rather than inferred.
        stimulus_channel_name : str, optional
            A recorded analog-to-digital converter channel name holding the actual delivered stimulus (the
            amplifier's command monitor / secondary output), used as-is. Works for ABF v1 and v2. Mutually
            exclusive with ``stimulus_command``.
        stimulus_command : str, optional
            A digital-to-analog converter command channel name (for example ``"Cmd 0"``) whose waveform is
            reconstructed from the protocol and written as the stimulus. ABF v2 only. Mutually exclusive
            with ``stimulus_channel_name``. See ``get_command_names``.
        metadata_key : str, optional
            Identity of this interface's response ``PatchClampSeries`` in the metadata dict. Defaults to the
            file stem plus the response channel name (a plain identifier).
        verbose : bool, default: False
        """
        super().__init__(verbose=verbose)
        self._file_path = file_path
        self._mode = mode
        self.source_data = dict(
            file_path=file_path,
            response_channel_name=response_channel_name,
            mode=mode,
            stimulus_channel_name=stimulus_channel_name,
            stimulus_command=stimulus_command,
            metadata_key=metadata_key,
            verbose=verbose,
        )

        if stimulus_channel_name is not None and stimulus_command is not None:
            raise ValueError(
                "Provide at most one of 'stimulus_channel_name' (a recorded monitor) or 'stimulus_command' "
                "(a reconstructed command), not both."
            )
        if mode == "izero" and (stimulus_channel_name is not None or stimulus_command is not None):
            raise ValueError("mode='izero' has no stimulus; remove 'stimulus_channel_name' / 'stimulus_command'.")

        from neo.rawio import AxonRawIO

        reader = AxonRawIO(filename=str(file_path))
        # TODO: remove this error-wrapping once python-neo raises clear errors for corrupt / integer-overflow
        # ABF files (handoff: source_formats/axon_molecular_devies/ongoing_work/draft_issue_neo_axonrawio_robustness.md).
        try:
            reader.parse_header()
        except Exception as exception:
            raise ValueError(
                f"AxonIntracellularInterface could not parse '{file_path}' as an ABF file "
                f"(the header may be corrupt or an unsupported ABF variant). Underlying error: {exception}"
            ) from exception
        self._reader = reader
        self._signal_channels = reader.header["signal_channels"]
        self._channel_names = _recorded_channel_names(reader)

        # Map the response channel name to its position in neo's signal_channels list now, so a name that isn't a
        # recorded channel fails at construction (with the available names). The stimulus channel/command names are
        # kept as strings and mapped the same way later, in _build_stimulus_series, next to where they are used.
        self._response_channel_index = self._channel_name_to_index(response_channel_name)
        self._stimulus_channel_name = stimulus_channel_name
        self._stimulus_command = stimulus_command

        # A reconstructed command (stimulus_command) is rebuilt from the ABF version-2 protocol section, which
        # version-1 files don't have; reject that combination now rather than failing later at write time.
        if stimulus_command is not None and reader._axon_info["fFileVersionNumber"] < 2:
            raise ValueError(
                "stimulus_command (a reconstructed command) requires ABF version 2; this file is "
                "version 1, which has no protocol section. Use stimulus_channel_name (a recorded monitor) instead."
            )

        # Whether this interface has a paired stimulus at all (either source). Computed once instead of
        # re-deriving the `stimulus_channel_name or stimulus_command` condition at each use.
        self._has_stimulus = stimulus_channel_name is not None or stimulus_command is not None

        self._response_channel_name = self._channel_names[self._response_channel_index]

        # Metadata-dict keys, seeded once from the file stem: the device is per file, the electrode per response
        # channel, and the series key is the user's `metadata_key` if given, else the electrode key. Each series
        # entry links to its electrode key and each electrode to its device key (see get_metadata), and those links
        # are editable, so two series can be pointed at one electrode to share it. The bare stem is a fine default
        # for a single file; making these unique across several files is a combining converter's responsibility.
        self._device_metadata_key = self._file_path.stem
        self._electrode_metadata_key = f"{self._file_path.stem}_{self._response_channel_name}"
        self._series_metadata_key = metadata_key or self._electrode_metadata_key

        # Derived once from the parsed header.
        self._num_sweeps = int(reader.header["nb_segment"][0])
        self._sampling_rate = float(reader.get_signal_sampling_rate())

    # ------------------------------------------------------------------ metadata

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        info = self._reader._axon_info

        # neo already builds rec_datetime from the header (real date+time for v2, time-of-day placeholder for v1).
        start_time = info.get("rec_datetime")
        if start_time is not None:
            metadata["NWBFile"]["session_start_time"] = start_time

        # Amplifier model from the telegraph header (ABF File Support Pack nTelegraphInstrument constants). Absent
        # for ABF v1 (no telegraph block) or a manual/unknown instrument; we don't invent a model here, the
        # write-time placeholder supplies a generic device name instead.
        telegraph_device = {15: "Axopatch 200B", 24: "MultiClamp 700", 27: "Axoclamp 900"}
        adc_info = info.get("listADCInfo")
        instrument_code = int(adc_info[0].get("nTelegraphInstrument", 0)) if adc_info else 0
        amplifier_name = telegraph_device.get(instrument_code)

        # The metadata-dict keys were seeded at construction. Each series entry stores its electrode_metadata_key as
        # an editable link: repointing two series at one electrode key merges them onto a single electrode; distinct
        # is the default. `to_camel_case` is applied only here, the one place a key is composed into an NWB `name`.
        device_metadata_key = self._device_metadata_key
        electrode_metadata_key = self._electrode_metadata_key
        series_metadata_key = self._series_metadata_key
        electrode_name_suffix = to_camel_case(electrode_metadata_key)

        if amplifier_name is not None:
            device_metadata = {
                "name": amplifier_name,
                "description": "Axon Instruments amplifier (telegraph-reported model).",
            }
        else:
            # No telegraph model: don't invent a name (the write-time placeholder fills it); just describe the type.
            device_metadata = {"description": "Axon Instruments amplifier."}
        metadata["Devices"] = {device_metadata_key: device_metadata}
        metadata["Icephys"]["IntracellularElectrodes"] = {
            electrode_metadata_key: {
                "name": f"IntracellularElectrode{electrode_name_suffix}",
                "description": "Patch-clamp electrode.",
                "device_metadata_key": device_metadata_key,
            }
        }

        response_class = _RESPONSE_CLASS[self._mode].__name__
        patch_clamp_series = {
            series_metadata_key: {
                "name": f"{response_class}{electrode_name_suffix}",
                "description": f"Intracellular response ({self._mode}).",
                "electrode_metadata_key": electrode_metadata_key,
            }
        }
        if self._has_stimulus:
            stimulus_class = _STIMULUS_CLASS[self._mode].__name__
            patch_clamp_series[f"{series_metadata_key}_stimulus"] = {
                "name": f"{stimulus_class}{electrode_name_suffix}",
                "description": f"Intracellular stimulus ({self._mode}).",
                "electrode_metadata_key": electrode_metadata_key,
            }
        metadata["Icephys"]["PatchClampSeries"] = patch_clamp_series

        return metadata

    # ------------------------------------------------------------------ writing

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
    ) -> None:
        if metadata is None:
            metadata = self.get_metadata()

        # Locate this interface's entries by the series metadata key (resolved at construction), then follow the
        # links to the ancillary objects.
        series_metadata_key = self._series_metadata_key
        patch_clamp_series = metadata["Icephys"]["PatchClampSeries"]
        response_metadata = patch_clamp_series[series_metadata_key]
        stimulus_metadata = patch_clamp_series.get(f"{series_metadata_key}_stimulus")
        electrode = _add_intracellular_electrode_to_nwbfile(
            nwbfile, metadata, response_metadata["electrode_metadata_key"]
        )

        data, timestamps, sweep_sample_ranges = self._concatenate_channel_sweeps(
            self._reader, self._response_channel_index, self._num_sweeps, self._sampling_rate
        )
        # The series is written on this file's own clock (timestamps start at the ABF header's t_start). The
        # interface does not shift them: placing several files on one shared session timeline is a multi-file
        # concern that only something seeing all the files can resolve, so temporal alignment is deferred rather
        # than handled here with a per-interface offset.
        channel = self._signal_channels[self._response_channel_index]
        response_kwargs = dict(
            name=response_metadata["name"],
            data=data,
            electrode=electrode,
            conversion=float(channel["gain"]) * get_conversion_from_unit(channel["units"]),
            offset=float(channel["offset"]) * get_conversion_from_unit(channel["units"]),
            gain=np.nan,
            description=response_metadata["description"],
        )
        # Use a uniform rate when the timestamps are regular (a single sweep, or contiguous sweeps); fall back to
        # explicit timestamps only when inter-sweep gaps make them irregular.
        rate = calculate_regular_series_rate(series=timestamps)
        if rate is not None:
            response_kwargs.update(starting_time=float(timestamps[0]), rate=rate)
        else:
            response_kwargs.update(timestamps=timestamps)
        response_series = _RESPONSE_CLASS[self._mode](**response_kwargs)
        nwbfile.add_acquisition(response_series)

        stimulus_series = None
        if stimulus_metadata is not None:
            stimulus_series = self._build_stimulus_series(
                self._reader, stimulus_metadata, electrode, timestamps, self._sampling_rate, self._num_sweeps
            )
            nwbfile.add_stimulus(stimulus_series)

        self._add_intracellular_table_to_nwb(
            nwbfile,
            electrode=electrode,
            response_series=response_series,
            stimulus_series=stimulus_series,
            sweep_sample_ranges=sweep_sample_ranges,
        )

    def _add_intracellular_table_to_nwb(
        self, nwbfile, electrode, response_series, sweep_sample_ranges, stimulus_series=None
    ):
        """Write one IntracellularRecordings row per sweep, each addressing this electrode's continuous response
        series (and, when present, its stimulus series) by the sweep's ``(start_index, count)`` range, and tag
        every row with two run-level foreign-key columns:

        - ``sequence``: the run identity (the file stem; the whole file is one run, so every sweep shares it).
          This is the column an aggregator later groups on to build a SequentialRecordings entry.
        - ``stimulus_type``: what kind of run it was (gap-free, the protocol file name, or "not described").

        These carry the run information in denormalized form, so the file stays information-complete even though
        the upper tables are not built. Those tables (SimultaneousRecordings, SequentialRecordings, and above) are
        deliberately not built by the interface: constructing them is a terminal step that locks their membership,
        and a single interface cannot know whether it is the last contributor to the file (a future converter may
        combine it with another electrode in the same simultaneous recording). Building the hierarchy is left to
        whatever reaches the known-complete file; the per-sweep rows written here are always safe to append to, so
        this contribution stays composable.
        """
        columns = {
            "sequence": self._file_path.stem,
            "stimulus_type": self._extract_stimulus_type(),
        }
        column_descriptions = {
            "sequence": "Run identity grouping rows into a sequential recording (one run per source file).",
            "stimulus_type": "Stimulus type of the run, carried up to its sequential recording when aggregated.",
        }
        table = nwbfile.get_intracellular_recordings()
        for name in columns:
            if name not in table.colnames:
                table.add_column(name=name, description=column_descriptions[name])

        for start_index, count in sweep_sample_ranges:
            kwargs = dict(
                electrode=electrode,
                response=response_series,
                response_start_index=start_index,
                response_index_count=count,
            )
            if stimulus_series is not None:
                kwargs.update(stimulus=stimulus_series, stimulus_start_index=start_index, stimulus_index_count=count)
            kwargs.update(columns)
            nwbfile.add_intracellular_recording(**kwargs)

    # ------------------------------------------------------------------ discovery (call before constructing)

    @classmethod
    def get_channel_names(cls, file_path: FilePath) -> list[str]:
        """
        Names of the recorded channels in an ABF file: the options for ``response_channel_name`` and
        ``stimulus_channel_name``. Call this before constructing the interface to see what is available.

        Parameters
        ----------
        file_path : FilePath
            Path to the Axon Binary Format (.abf) file.

        Returns
        -------
        list of str
            The recorded (analog-to-digital converter) channel names.
        """
        reader = cls.get_extractor_class()(filename=str(file_path))
        reader.parse_header()
        return _recorded_channel_names(reader)

    @classmethod
    def get_command_names(cls, file_path: FilePath) -> list[str]:
        """
        Names of the DAC command channels in an ABF file: the options for ``stimulus_command``. Empty for
        ABF version 1 files, which have no reconstructable protocol (use ``stimulus_channel_name`` there instead).

        Parameters
        ----------
        file_path : FilePath
            Path to the Axon Binary Format (.abf) file.

        Returns
        -------
        list of str
            The DAC (digital-to-analog converter) command channel names, or ``[]`` for ABF version 1.
        """
        reader = cls.get_extractor_class()(filename=str(file_path))
        reader.parse_header()
        if reader._axon_info["fFileVersionNumber"] < 2:
            return []
        return _dac_channel_names(reader)

    # ------------------------------------------------------------------ helpers

    def _channel_name_to_index(self, name: str) -> int:
        """Resolve a recorded ADC channel name to its signal_channels index."""
        if name in self._channel_names:
            return self._channel_names.index(name)
        raise ValueError(
            f"Recorded channel '{name}' not found in '{self._file_path.name}'. "
            f"Available recorded channels: {self._channel_names}."
        )

    def _command_name_to_index(self, name: str) -> int:
        """Resolve a DAC command channel name to its index in the protocol's DAC list."""
        dac_names = _dac_channel_names(self._reader)
        if name in dac_names:
            return dac_names.index(name)
        raise ValueError(
            f"DAC command '{name}' not found in '{self._file_path.name}'. Available commands: {dac_names}."
        )

    # ------------------------------------------------------------------ writing helpers

    def _concatenate_channel_sweeps(self, reader, channel_index, num_sweeps, sampling_rate):
        """Read one ADC channel across all sweeps into preallocated arrays; return
        ``(data, timestamps, [(start_index, count), ...])``.

        Done in three passes: first the per-sweep ``(start_index, count)`` ranges (from the segment sample
        counts), then the data, then the timestamps. The outputs are sized up front and filled in place, so the
        full signal is materialized only once (no list of per-sweep chunks plus a concatenation copy, which
        would transiently hold the data twice). ``data`` keeps the channel's raw on-disk dtype, since the
        response / stimulus series carries the unit conversion; it is never widened to float.
        """
        # 1. Per-sweep (start_index, count) ranges within the concatenated arrays, from the segment sample counts.
        sweep_sample_ranges = []
        cursor = 0
        for segment_index in range(num_sweeps):
            num_sweep_samples = int(
                reader.get_signal_size(
                    block_index=self._BLOCK_INDEX, seg_index=segment_index, stream_index=self._STREAM_INDEX
                )
            )
            sweep_sample_ranges.append((cursor, num_sweep_samples))
            cursor += num_sweep_samples
        total_samples = cursor

        # 2. Data: read each sweep's chunk into its slice, keeping the raw on-disk dtype.
        data = np.empty(total_samples, dtype=self._signal_channels[channel_index]["dtype"])
        for segment_index, (start_index, count) in enumerate(sweep_sample_ranges):
            chunk = np.asarray(
                reader.get_analogsignal_chunk(
                    block_index=self._BLOCK_INDEX, seg_index=segment_index, channel_indexes=[channel_index]
                )
            ).reshape(-1)
            data[start_index : start_index + count] = chunk

        # 3. Timestamps: each sweep starts at its segment's t_start, then advances at the sampling rate.
        # neo makes one segment per ABF episode (sweep) from the file's SynchArray (one (offset, len) entry per
        # episode), and each segment's t_start is that recorded offset. So multiple segments reflect the episodic
        # protocol, not the presence of gaps: contiguous episode offsets give regular t_starts (-> a uniform rate
        # downstream), while inter-sweep intervals show up as gaps in t_start (-> explicit timestamps).
        timestamps = np.empty(total_samples, dtype="float64")
        for segment_index, (start_index, count) in enumerate(sweep_sample_ranges):
            segment_start_time = float(
                reader.get_signal_t_start(
                    block_index=self._BLOCK_INDEX, seg_index=segment_index, stream_index=self._STREAM_INDEX
                )
            )
            timestamps[start_index : start_index + count] = segment_start_time + np.arange(count) / sampling_rate

        return data, timestamps, sweep_sample_ranges

    def _build_stimulus_series(self, reader, stimulus_metadata, electrode, timestamps, sampling_rate, num_sweeps):
        if self._stimulus_command is not None:
            # Reconstructed command (DAC): resolve the command name to its DAC index, then synthesize the
            # waveform from the protocol epoch table.
            dac_index = self._command_name_to_index(self._stimulus_command)
            sigs_by_segment, _, units = reader.read_raw_protocol()
            data = np.concatenate(
                [np.asarray(sigs_by_segment[seg][dac_index]).reshape(-1) for seg in range(num_sweeps)]
            )
            conversion = get_conversion_from_unit(units[dac_index])
            offset = 0.0
        else:
            # Recorded monitor (ADC): resolve the monitor channel, then read it like the response.
            stimulus_channel_index = self._channel_name_to_index(self._stimulus_channel_name)
            data, _, _ = self._concatenate_channel_sweeps(reader, stimulus_channel_index, num_sweeps, sampling_rate)
            channel = self._signal_channels[stimulus_channel_index]
            conversion = float(channel["gain"]) * get_conversion_from_unit(channel["units"])
            offset = float(channel["offset"]) * get_conversion_from_unit(channel["units"])

        kwargs = dict(
            name=stimulus_metadata["name"],
            data=data,
            electrode=electrode,
            conversion=conversion,
            offset=offset,
            gain=np.nan,
            description=stimulus_metadata["description"],
        )
        # Same timing rule as the response: regular -> rate, irregular (inter-sweep gaps) -> timestamps.
        rate = calculate_regular_series_rate(series=timestamps)
        if rate is not None:
            kwargs.update(starting_time=float(timestamps[0]), rate=rate)
        else:
            kwargs.update(timestamps=timestamps)
        return _STIMULUS_CLASS[self._mode](**kwargs)

    def _extract_stimulus_type(self) -> str:
        info = self._reader._axon_info
        operation_mode = info.get("protocol", {}).get("nOperationMode", info.get("nOperationMode"))
        if operation_mode == 3:
            return "gap-free"
        protocol_path = info.get("sProtocolPath")
        if protocol_path:
            # neo returns `sProtocolPath` as bytes; decode it (as `_dac_channel_names` does for the DAC names) so
            # the `b'...'` repr never leaks into the label. It is a Windows path, so PureWindowsPath splits on `\`
            # (and `/`) on any host OS.
            protocol_path = (
                protocol_path.decode(errors="replace") if hasattr(protocol_path, "decode") else str(protocol_path)
            )
            protocol_name = PureWindowsPath(protocol_path).stem
            if protocol_name:
                return protocol_name
        return "not described"
