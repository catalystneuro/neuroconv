# Plan: Bruker PrairieView VoltageRecording icephys interface

## Goal

Convert the intracellular recordings PrairieView writes alongside two-photon imaging, closing issue #379 ("[New Format]: PrarieView icephys voltage traces (csv files)"), open since March 2023. This is the cheapest remaining icephys format: the fixtures are already on gin, a working reference implementation exists, and there is no binary reader to write.

## What the format actually is

Verified against the gin fixtures at `ephy_testing_data/bruker/voltage_recording/` (nine stubbed sessions from DANDI 001538, Zhai et al.).

A recording is a **pair of files per cycle**: `<stem>_Cycle<NNNNN>_VoltageRecording_<NNN>.csv` and a matching `.xml`.

The CSV is a plain table, `Time(ms), Primary`, with time in milliseconds and one column per enabled signal. Note the leading space in the `" Primary"` column name.

The XML (`VRecSessionEntry`) carries everything else:

- `Experiment/SignalList/VRecSignal` per signal, each with `Name`, `Gain`, `Enabled`, `Card`, `Channel` and a `Unit` block holding `UnitName`, `Multiplier`, `Divisor`, `PatchclampDevice` and `PatchclampChannel`.
- `Rate` (10000 in the fixtures), `AcquisitionTime`, `SamplesAcquired`, `DataFile` and a per-cycle `DateTime` with timezone offset.

Four facts drive the design:

1. **`Enabled` selects the columns.** Only signals with `Enabled=true` appear in the CSV. A typical session enables `Primary` and disables `Secondary`, `WF` and the wavelength channels.
2. **The clamp mode is in the file.** `Primary`'s `UnitName` is `mV` for current clamp and `pA` for voltage clamp. Unlike ABF, where Axon's clamp-mode metadata is unreliable and the mode must be passed explicitly, here it is derivable.
3. **Scaling is `raw * Multiplier / Divisor`**, then a unit conversion to volts or amperes. `Divisor` varies across sessions (0.01, 0.1, 0.005), which is why the fixture set includes divisor variants.
4. **One cycle is one sweep.** A session folder holds many `CycleNNNNN` files, each its own CSV/XML pair, each carrying its own `DateTime`.

## Design decisions

**One interface per cycle file, and the converter concatenates.** NWB wants one continuous `PatchClampSeries` addressed by `(start_index, count)` ranges per sweep, which is what `tools/icephys.py` builds the hierarchy and the `sweeps` table from. So the interface reads one cycle, and a `PrairieViewIntracellularConverter` concatenates the cycles of one cell into a single series and writes one `IntracellularRecordings` row per cycle. The alternative, one file to one series, is what the reference implementation does and it is simpler, but it produces a file where every sweep is a separate series and the icephys hierarchy has nothing to group.

**Cycles are placed on one timeline by their `DateTime`.** This mirrors what `AxonIntracellularConverter` already does with `rec_datetime` for multi-file ABF recordings, including the earliest file becoming the session origin, so the alignment code has a precedent to follow rather than a new mechanism.

**Infer the clamp mode from the `Primary` unit, with an explicit override.** Deriving it is right because the file states it, but a `mode` argument stays available for a rig that mislabels units.

**Reuse everything format-independent.** The electrode goes through `_add_intracellular_electrode_to_nwbfile`, the series class through `_RESPONSE_CLASS`, and the converter finalizes with `_build_icephys_hierarchical_tables` and `_add_sweep_time_intervals_to_nwbfile`. The interface writes only per-sweep rows tagged with `sequence` and `stimulus_type`, the same contract `MockIcephysInterface` encodes.

## Scope

1. `PrairieViewVoltageRecordingInterface` in `src/neuroconv/datainterfaces/icephys/prairieview/`, reading one CSV/XML pair, resolving the enabled signals, applying the multiplier and divisor, and writing the response series plus its recordings rows.
2. `PrairieViewIntracellularConverter`, grouping a cell's cycles into one series on one timeline and finalizing the icephys tables.
3. Dict-based metadata: top-level `Devices` keyed off `PatchclampDevice` (the fixtures give `Multiclamp700B Ch1`, `Multiclamp700B`, and an empty element on non-patch signals), plus the `Icephys` electrode and series registries cross-linked by `device_metadata_key` and `electrode_metadata_key`.
4. Tests on the nine gin fixtures, one per parsing edge case the README names: divisor variation, enabled-based channel selection, the 2016 XML schema, and the device-naming variants. Data-free tests for anything format-independent go through `MockIcephysInterface` instead.
5. A gallery page under `docs/conversion_examples_gallery/recording/`, following the ABF page's shape, leading with the converter for the multi-cycle case.

## Explicitly deferred

The non-patch signals (`WF`, and the wavelength channels such as `720nm`, all recorded in volts) are analog sync and stimulus-monitor traces, not icephys, and belong in a `TimeSeries` path rather than this interface. The `.env` protocol waveforms and any stimulus reconstruction are likewise out: unlike ABF, there is no protocol section to rebuild a command from, so `stimulus_type` will read `"not described"` until we decide what else to derive it from.

## Open questions

- **`Gain` is read but unused.** The reference implementation parses `Gain` (-0.5 in every fixture) and does not apply it, scaling only by multiplier and divisor. Either it is already folded into the divisor or it is a display setting. Worth settling against the PrairieView manual before shipping, since getting it wrong scales every trace.
- **Cell identity across cycles.** Nothing in the XML names the cell, so the electrode identity has to come from the directory layout. The fixture folders (`cell1-001`, `cell2-020`) suggest the stem carries it, which would make the run-label disambiguation in `tools/icephys.py` reusable here.
- **Whether `SamplesAcquired` and `AcquisitionTime` in the stubs match the truncated CSVs or the original recordings.** If they describe the original, the interface must trust the CSV length rather than the header.

## Touch points

- `src/neuroconv/datainterfaces/icephys/prairieview/` (new interface and converter)
- `src/neuroconv/datainterfaces/__init__.py` and `src/neuroconv/converters.py` (registration)
- `src/neuroconv/tools/icephys.py` (reused unchanged)
- `tests/test_on_data/icephys/` (fixture-driven tests)
- `docs/conversion_examples_gallery/recording/` (gallery page)
- Reference implementation to port from: `~/development/conversions/surmeier-lab-to-nwb/src/surmeier_lab_to_nwb/zhai2025/interfaces/intracellular_interfaces.py` (569 lines, `PrairieViewCurrentClampInterface` and `PrairieViewVoltageClampInterface`) and its `prairie_view_utils.py`
