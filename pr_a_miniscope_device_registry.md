# PR A: Miniscope onto the unified device registry

Work plan. The full end state lives in commit `cff97f54e` ("draft") on `fix_miniscope`; this PR is the
subset of it that stands alone, with no dependency on the converter migration. Delete this file once
the pull request is published.

## What lands

A `Miniscope` device is built by the shared registry from a typed `metadata["Devices"]` entry, instead
of being written by a direct `add_miniscope_device` call with only its name. That closes two defects at
once: the modern interface dropped every configuration field except `name` and `model_name` (defect 3),
and real values crashed the device construction (defect 4), since `ewl` is not in the ndx-miniscope
schema while `gain` and `frameRate` are typed as text there and files carry `gain: 3.5`, `gain: 16`,
`frameRate: 50`.

Only the dict-based branch changes. The list-based path is untouched, and no converter emits dict-based
metadata yet, so nothing in the tree writes differently after this merges. It is a metadata-shape change
in practice, which is why it can go first.

## Files

**`src/neuroconv/tools/nwb_helpers/_device_types.py`**
Add one entry to `_DEVICE_TYPE_SOURCES`: `"Miniscope": ("ndx_miniscope", "pip install ndx-miniscope")`.
That is what lets `_add_device_to_nwbfile` resolve `type: "Miniscope"` and build the extension class.

**`src/neuroconv/datainterfaces/ophys/miniscope/_miniscope_readers.py`**
Add the shared mapping and its field tables:

- `_MINISCOPE_DEVICE_TEXT_FIELDS = ("compression", "deviceType", "frameRate", "gain")`
- `_MINISCOPE_DEVICE_INT_FIELDS = ("excitation", "framesPerFile", "led0", "msCamExposure")`
- `_MINISCOPE_DEVICE_IGNORED_FIELDS = ("deviceDirectory", "deviceID", "deviceName")`
- `_config_to_miniscope_device_metadata(miniscope_config)`

It coerces each field to the dtype the schema declares, turns the `ROI` dict into the `[height, width]`
list the spec wants, and names anything the schema has no field for in the device description rather
than dropping it. `ewl` is the one every V4 file carries.

Do **not** bring `_get_device_folder_timestamps` across; it belongs to the behavior-camera PR.

**`src/neuroconv/datainterfaces/ophys/miniscope/miniscopeimagingdatainterface.py`**
Four hunks:

1. Import `_config_to_miniscope_device_metadata`.
2. `__init__`: `self._device_metadata_key = metadata_key`, and hoist `miniscope_config = None` above the
   `if device_metadata_path.exists()` block so the dict branch can see it.
3. `get_metadata(use_new_metadata_format=True)`: build the `Devices` entry from the mapping, key it by
   `self._device_metadata_key`, and give the plane and series a `name` (and the series a `unit`) so the
   metadata is complete enough to write standalone.
4. `add_to_nwbfile`: call `add_miniscope_device` only on the list path, guarded by
   `_is_dict_based_metadata`. On the dict path the imaging plane resolves the device through
   `device_metadata_key` and the registry builds it.

The `_device_metadata_key` split is the part a reviewer will ask about, since nothing in this PR sets it
to anything but `metadata_key`. It is the interface-side half of a cardinality problem: one Miniscope
recorded over several sessions is one device and one imaging plane but one series per session, so the
device key has to be separable from the series key. The converter PR is what sets it. If you would
rather not carry it here, it can move to that PR at the cost of touching this file twice.

## Tests

- `tests/test_on_data/ophys/test_imaging_interfaces.py`: update `check_extracted_metadata` in
  `TestMiniscopeImagingInterface` to the typed entry (`type`, `compression`, `deviceType`, `frameRate`,
  `gain`, `framesPerFile`, `led0`) and to the plane and series names. Already written in the draft.
- **Still to write:** a unit test for `_config_to_miniscope_device_metadata` covering the three things
  the mapping exists for, since none of them is visible in the interface test: `gain: 3.5` coerced to
  `"3.5"`, the `ROI` dict flattened to `[height, width]`, and `ewl` reported in the description. The
  behavior-camera fixture is the one with the numeric gain, so build the input dict inline rather than
  reading a file.

Verify with:

```
pytest tests/test_on_data/ophys/test_imaging_interfaces.py tests/test_on_data/ophys/test_miniscope_converter.py
```

The converter suite is the regression check that matters: it still runs list-based after this PR, so it
should pass untouched.

## CHANGELOG

The bullet is already drafted in the commit, under Bug Fixes:

> Fixed `MiniscopeImagingInterface` losing the device configuration and crashing on real values.
> `Miniscope` is now a registered device type built by the shared registry from a single
> config-to-device mapping, so `gain`, `led0`, `frameRate`, `framesPerFile`, `compression` and `ROI`
> reach the device instead of only its name, values are coerced to the dtype the ndx-miniscope schema
> declares (`gain: 3.5` and `frameRate: 50` are real values that raised `TypeError`), and a setting the
> schema has no field for (`ewl`) is named in the device description rather than dropped.

## Description draft

# Build the Miniscope device through the unified device registry

`MiniscopeImagingInterface` wrote its device with a direct `add_miniscope_device` call carrying only the
device name, so every acquisition setting the DAQ recorded was lost, and the fields that did reach the
`Miniscope` constructor crashed on real files: `ewl` is not in the ndx-miniscope schema at all, and
`gain` and `frameRate` are typed as text there while the software writes `gain: 3.5`, `gain: 16` and
`frameRate: 50`. This registers `Miniscope` as a resolvable device type and routes it through
`_add_device_to_nwbfile` like every other device, so the whole configuration reaches the file.

The values are mapped in one place, coercing each field to the dtype the schema declares and turning the
`ROI` dict into the `[height, width]` list the spec wants. I chose to name a setting the schema has no
field for in the device description rather than drop it, so nothing the DAQ recorded disappears
silently; `ewl` is the one every V4 file carries, and the proper fix is an ndx-miniscope proposal for it
along with the `gain` and `frameRate` dtypes. Only the dict-based metadata branch changes, so no
conversion writes differently today.
