# Plan: generic channel removal + actionable messaging for heterogeneous offsets/units

## Goal

When a recording has channels that cannot share one series (heterogeneous offsets for `ElectricalSeries`, or heterogeneous units/gains/offsets for `TimeSeries`), neuroconv currently either hard-errors or silently degrades, with no actionable guidance. Give users a generic, documented way to act: a `remove_channels` method on the recording interface, plus error/warning messages and a how-to that point to it.

This is the deliberately small, no-new-feature slice. The offset escape hatch (`write_in_physical_units`) is **deferred on purpose** (let demand accumulate to strengthen the dedicated-biopotential-types case in nwb-schema #694 / #651). Do not add it here.

## Scope

In scope: one new interface method, two message edits, one how-to addition, one doc bug fix.
Out of scope (tracked elsewhere): `write_in_physical_units` escape hatch, `EDFConverter`, `stream_id`/`stream_name` passthrough, python-neo stream detection.

## Task 1 - add `remove_channels` to the base recording interface

File: `/home/heberto/development/work_repos/neuroconv/src/neuroconv/datainterfaces/ecephys/baserecordingextractorinterface.py`
(next to the existing `channel_ids` property, ~line 148)

```python
def remove_channels(self, channel_ids):
    """Drop the given channels from this interface's recording. Returns self."""
    self.recording_extractor = self.recording_extractor.remove_channels(remove_channel_ids=channel_ids)
    return self
```

Notes:
- Single method, drop-pattern only (users hit these errors because of a few offending channels; dropping is the common action and matches the existing `channels_to_skip`). We deliberately do NOT add `select_channels` to the public interface; the converter/internal code can call spikeinterface's `select_channels` directly.
- Param named `channel_ids` to match the `channel_ids` getter (spikeinterface's underlying kwarg is `remove_channel_ids`).
- In-place on `self.recording_extractor`, returns `self` for chaining.
- Keep EDF's construction-time `channels_to_skip` as-is (backward compat); this is the generic post-construction equivalent.
- Add a short test: build a `MockRecordingInterface`, `remove_channels([...])`, assert the channels are gone and the original count dropped.

## Task 2 - make the `ElectricalSeries` offset error actionable

File: `/home/heberto/development/work_repos/neuroconv/src/neuroconv/tools/spikeinterface/spikeinterface.py`
Function: `_report_variable_offset` (~line 1458; it builds `message_lines` and raises).

Keep the existing per-offset channel map, then append a generic, format-agnostic pointer (NO EDF-specific `channels_to_skip`, NO deferred escape hatch):

> A single ElectricalSeries can only store one scalar offset. Remove the channels that do not share the common offset (`interface.remove_channels(channel_ids=...)`) and write them as their own series. See <how-to link>.

## Task 3 - make the `TimeSeries` degradation warning actionable

File: same `spikeinterface.py`, in `add_recording_as_time_series_to_nwbfile` (~lines 1586-1598), the branch that sets `unit="n.a."` when units/gains/offsets are not homogeneous.

This path is silent (warning only) and produces a file whose physical values are not recoverable. Tighten the warning to say that explicitly and point at the same fix:

> The TimeSeries will be written without unit/conversion, so physical values will not be recoverable from the file. Make the channels consistent, or drop the inconsistent ones with `interface.remove_channels(channel_ids=...)` and write them as a separate TimeSeries. See <how-to link>.

(Keep the existing "set unit in metadata / set the scaling properties" advice.)

## Task 4 - how-to

File: `/home/heberto/development/work_repos/neuroconv/docs/how_to/add_behavioral_and_sensor_data.rst`

This guide already teaches splitting channels into separate series via channel selection. Add a short subsection, e.g. "Handling channels with heterogeneous offsets or units", that:
- names the two symptoms (the `ElectricalSeries` heterogeneous-offset error and the `TimeSeries` `unit="n.a."` warning), so people find it by keyword,
- shows `interface.remove_channels(channel_ids=[...])` to drop the offending channels,
- shows writing the dropped group as its own series (electrode group vs auxiliary group), linking the EDF gallery's "Combining Electrode and Auxiliary Channels" as the format-specific example.

Use this section's anchor as the `<how-to link>` in Tasks 2 and 3.

## Task 5 - fix the existing doc bug

File: `/home/heberto/development/work_repos/neuroconv/docs/conversion_examples_gallery/recording/edf.rst` (~lines 109/114)

In the "Combining Electrode and Auxiliary Channels" example, `all_non_electrical_channels` is defined but `all_auxiliary_channels` is passed to `channels_to_skip` (undefined -> `NameError`). Unify the variable name.

## Branch

Branch off `main` (name TBD). All five tasks are independent of the deferred/queued work.
