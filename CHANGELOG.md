## v0.7.4 (Upcoming)

## Deprecations and Changes
* Drop support for python 3.9 [PR #1313](https://github.com/catalystneuro/neuroconv/pull/1313)
* Updated type hints to take advantage of the | operator [PR #1316](https://github.com/catalystneuro/neuroconv/pull/1313)
* Deprecated the following ScanImage interfaces: `ScanImageMultiFileImagingInterface`, `ScanImageMultiPlaneImagingInterface`, `ScanImageMultiPlaneMultiFileImagingInterface`, `ScanImageSinglePlaneImagingInterface`, and `ScanImageSinglePlaneMultiFileImagingInterface`. These interfaces will be removed in or after October 2025. Use `ScanImageImagingInterface` for all those cases instead. [PR #1330](https://github.com/catalystneuro/neuroconv/pull/1330) [PR #1331](https://github.com/catalystneuro/neuroconv/pull/1331)
* Set minimum version requirement for `ndx-pose` to 0.2.0 [PR #1322](https://github.com/catalystneuro/neuroconv/pull/1322)
* Set minimum version for roiextractors as 0.5.13 [PR #1339](https://github.com/catalystneuro/neuroconv/pull/1339)
* ndx-events is now a required dependency by spikeglx [PR #1353](https://github.com/catalystneuro/neuroconv/pull/1353)

## Bug Fixes
* Fix `AudioInterface` to correctly handle WAV filenames with multiple dots by validating only the last suffix. [PR #1327](https://github.com/catalystneuro/neuroconv/pull/1327)

## Features
* Add metadata support for `DeepLabCutInterface` [PR #1319](https://github.com/catalystneuro/neuroconv/pull/1319)
* `AudioInterface` Adding support for IEEE float in WAV format [PR #1325](https://github.com/catalystneuro/neuroconv/pull/1325)
* Added a RecordingInterface for WhiteMatter ephys data [PR #1297](https://github.com/catalystneuro/neuroconv/pull/1297) [PR #1333](https://github.com/catalystneuro/neuroconv/pull/1333)
* Improved `ScanImageInteface` to support both single and multi-file data [PR #1330](https://github.com/catalystneuro/neuroconv/pull/1330)
* `DeepDict` now behaves as a python dict when printed in notebooks [PR #1351](https://github.com/catalystneuro/neuroconv/pull/1351)
* Enable chunking for `InternalVideoInterface` [PR #1338](https://github.com/catalystneuro/neuroconv/pull/1338)
* `ImageSeries` and `TwoPhotonSeries` now are chunked by default even if the data is passed as a plain array [PR #1338](https://github.com/catalystneuro/neuroconv/pull/1338)
* Added support for 'I;16' mode in `ImageInterface`. This mode is mapped to `GrayscaleImage` in NWB [PR #1365](https://github.com/catalystneuro/neuroconv/pull/1365)

## Improvements
* Make metadata optional in `NWBConverter.add_to_nwbfile` [PR #1309](https://github.com/catalystneuro/neuroconv/pull/1309)
* Add installation instructions on the documentation for `neuroconv` [PR #1344](https://github.com/catalystneuro/neuroconv/pull/1344)
* Separate dailies and dev-dailies workflows [PR #1343](https://github.com/catalystneuro/neuroconv/pull/1343)
* Added support for renaming Skeletons with DeepLabCutInterface [PR #1359](https://github.com/catalystneuro/neuroconv/pull/1359)
* Updated pose_estimation series names [PR #1363](https://github.com/catalystneuro/neuroconv/pull/1363)
* Testing dependencies include only testing packages (.e.g pytest, pytest-cov) [PR #1357](https://github.com/catalystneuro/neuroconv/pull/1357)
* Testing modalities now run in their separated environment to avoid sequence contamination of dependencies [PR #1357](https://github.com/catalystneuro/neuroconv/pull/1357)
* Reorganized tests for external cloud services into a dedicated `remote_transfer_services` directory to improve test organization and prevent automatic collection by pytest [PR #TBD](https://github.com/catalystneuro/neuroconv/pull/TBD)

# v0.7.3 (April 25, 2025)

## Deprecations and Changes
* Release pydantic ceiling [PR #1273](https://github.com/catalystneuro/neuroconv/pull/1273)
* `write_scaled` behavior on `add_electrical_series_to_nwbfile` is deprecated and will be removed in or after October 2025 [PR #1292](https://github.com/catalystneuro/neuroconv/pull/1292)
* `add_electrical_series_to_nwbfile` now requires both gain and offsets to write scaling factor for voltage conversion when writing to NWB [PR #1292](https://github.com/catalystneuro/neuroconv/pull/1292)
* `add_electrical_series_to_nwbfile`, `add_units_table_to_nwbfile` and `add_electrodes_to_nwbfile` and `add_electrode_groups_to_nwbfile` are becoming private methods. Use `add_recording_to_nwbfile`, `add_sorting_to_nwbfile` and `add_recording_metadata_to_nwbfile` instead [PR #1298](https://github.com/catalystneuro/neuroconv/pull/1298)
* Set a new minimal dependency for `hdmf` to 4.0.0, `pynwb` to 3.0.0 and `hdmf-zarr` 0.11 [PR #1303](https://github.com/catalystneuro/neuroconv/pull/1303)

## Bug Fixes
* Fixed import errors in main modules caused by non-lazy dependencies. Added tests to prevent regressions. [PR #1305](https://github.com/catalystneuro/neuroconv/pull/1305)

## Features
* Added a new `add_recording_as_time_series_to_nwbfile` function to add recording extractors from SpikeInterface as recording extractors to an nwbfile as time series [PR #1296](https://github.com/catalystneuro/neuroconv/pull/1296)
* Added `OpenEphysBinaryAnalogInterface` for converting OpenEphys analog channels data similar to the SpikeGLX NIDQ interface [PR #1237](https://github.com/catalystneuro/neuroconv/pull/1237)
* Expose iterative write options on `BaseImagingExtractorInterface` [PR #1307](https://github.com/catalystneuro/neuroconv/pull/1307)

## Improvements
* Add documentation for conversion options with `NWBConverter` [PR #1301](https://github.com/catalystneuro/neuroconv/pull/1301)
* Support roiextractors 0.5.12 [PR #1306](https://github.com/catalystneuro/neuroconv/pull/1306)
* `configure_backend` is now exposed to be imported as `from neuroconv.tools import configure_and_write_nwbfile` [PR #1287](https://github.com/catalystneuro/neuroconv/pull/1287)
* Added metadata section to video conversion gallery [PR #1276](https://github.com/catalystneuro/neuroconv/pull/1276)
* `DeepLabCutInterface` now calculates whether the timestamps come from a constant sampling rate and adds that instead if detected [PR #1293](https://github.com/catalystneuro/neuroconv/pull/1293)
* Fixed a bug in the extractor interfaces where segmentation and sorting interfaces were initialized twice [PR #1288](https://github.com/catalystneuro/neuroconv/pull/1288)
* Support python 3.13 [PR #1117](https://github.com/catalystneuro/neuroconv/pull/1117)
* Added *how to* documentation on how to set a probe to a recording interfaces [PR #1300](https://github.com/catalystneuro/neuroconv/pull/1300)
* Fix API docs for `OpenEphysRecordingInterface` [PR #1302](https://github.com/catalystneuro/neuroconv/pull/1302)

# v0.7.2 (April 4, 2025)

## Deprecations and Changes
* Split VideoInterface (now deprecated) into ExternalVideoInterface and InternalVideoInterface [PR #1251](https://github.com/catalystneuro/neuroconv/pull/1251) [PR #1256](https://github.com/catalystneuro/neuroconv/pull/1256) [PR #1278](https://github.com/catalystneuro/neuroconv/pull/1278)
* `output_filepath` deprecated on `configure_and_write_nwbfile` use `nwbfile_path` instead [PR #1270](https://github.com/catalystneuro/neuroconv/pull/1270)
* Temporary set a ceiling on pydantic `<2.11` [PR #1275](https://github.com/catalystneuro/neuroconv/pull/1275)

## Bug Fixes
* Fixed a check in `_configure_backend` on neurodata_object ndx_events.Events to work only when ndx-events==0.2.0 is used. [PR #998](https://github.com/catalystneuro/neuroconv/pull/998)
* Added an `append_on_disk_nwbfile` argumento to `run_conversion`. This changes the semantics of the overwrite parameter from assuming append mode when a file exists to a more conventional `safe writing` mode where confirmation is required to overwrite an existing file. Append mode now is controlled with the `append_on_disk_nwbfile`. [PR #1256](https://github.com/catalystneuro/neuroconv/pull/1256)

## Features
* Added `SortedRecordingConverter` to convert sorted recordings to NWB with correct metadata mapping between units and electrodes [PR #1132](https://github.com/catalystneuro/neuroconv/pull/1132)
* Support roiextractors 0.5.11 [PR #1236](https://github.com/catalystneuro/neuroconv/pull/1236)
* Added stub_test option to TDTFiberPhotometryInterface [PR #1242](https://github.com/catalystneuro/neuroconv/pull/1242)
* Added ThorImagingInterface for Thor TIFF files with OME metadata [PR #1238](https://github.com/catalystneuro/neuroconv/pull/1238)
* Added `always_write_timestamps` parameter to ExternalVideoInterface and InternalVideoInterface to force writing timestamps even when they are regular [#1279](https://github.com/catalystneuro/neuroconv/pull/1279)

## Improvements
* Filter out warnings for missing timezone information in continuous integration [PR #1240](https://github.com/catalystneuro/neuroconv/pull/1240)
* `FilePathType` is deprecated, use `FilePath` from pydantic instead [PR #1239](https://github.com/catalystneuro/neuroconv/pull/1239)
* Change `np.NAN` to `np.nan` to support numpy 2.0 [PR #1245](https://github.com/catalystneuro/neuroconv/pull/1245)
* Re activate Plexon tests on Mac. Testing this for a while as they are unreliable tests [PR #1195](https://github.com/catalystneuro/neuroconv/pull/1195)
* Testing: only run tests for oldest and newest versions of python [PR #1249](https://github.com/catalystneuro/neuroconv/pull/1249)
* Improve error display on scan image interfaces [PR #1246](https://github.com/catalystneuro/neuroconv/pull/1246)
* Added concurrency to live-service-testing GitHub Actions workflow to prevent simultaneous write to the dandiset. [PR #1252](https://github.com/catalystneuro/neuroconv/pull/1252)
* Updated GitHub Actions workflows to use Environment Files instead of the deprecated `set-output` command [PR #1259](https://github.com/catalystneuro/neuroconv/pull/1259)
* Propagate `verbose` parameter from Converters to Interfaces [PR #1253](https://github.com/catalystneuro/neuroconv/issues/1253)
* Replace uses of scipy load_mat and h5storage loadmat with pymat_reader read_mat in `CellExplorerSortingInterface` [PR #1254](https://github.com/catalystneuro/neuroconv/pull/1254)
* Added camera device support for ExternalVideoInterface and InternalVideoInterface: [PR #1282](https://github.com/catalystneuro/neuroconv/pull/1282)


# v0.7.1 (March 5, 2025)

## Deprecations and Changes

## Bug Fixes
* Fix parsing of group_names in `tools.spikeinterface` [PR #1234](https://github.com/catalystneuro/neuroconv/pull/1234)

## Features

## Improvements
* Testing suite now supports numpy 2.0. [PR #1235](https://github.com/catalystneuro/neuroconv/pull/1235)

# v0.7.0 (March 3, 2025)

## Deprecations and Changes
* Interfaces and converters now have `verbose=False` by default [PR #1153](https://github.com/catalystneuro/neuroconv/pull/1153)
* Added `metadata` and `conversion_options` as arguments to `NWBConverter.temporally_align_data_interfaces` [PR #1162](https://github.com/catalystneuro/neuroconv/pull/1162)
* Deprecations in the ecephys pipeline: compression options, old iterator options, methods that did not end up in *to_nwbfile and the `get_schema_from_method_signature` function [PR #1207](https://github.com/catalystneuro/neuroconv/pull/1207)
* Removed all deprecated functions from the roiextractors module: `add_fluorescence_traces`, `add_background_fluorescence_traces`, `add_summary_images`, `add_segmentation`, and `write_segmentation` [PR #1233](https://github.com/catalystneuro/neuroconv/pull/1233)

## Bug Fixes
* `run_conversion` does not longer trigger append mode when `nwbfile_path` points to a faulty file [PR #1180](https://github.com/catalystneuro/neuroconv/pull/1180)
* `DatasetIOConfiguration` now recommends `chunk_shape = (len(candidate_dataset),)` for datasets with compound dtypes as used by hdmf >= 3.14.6. [PR #1146](https://github.com/catalystneuro/neuroconv/pull/1146)
* `OpenEphysBinaryRecordingInterface` no longer stores analog data as an `ElectricalSeries` [PR #1179](https://github.com/catalystneuro/neuroconv/pull/1179)

## Features
* Added `PlexonLFPInterface` for converting Plexon `FPl-Low Pass Filtered` stream data [PR #1209](https://github.com/catalystneuro/neuroconv/pull/1209)
* Added `ImageInterface` for writing large collection of images to NWB and automatically map the images to the correct NWB data types [PR #1190](https://github.com/catalystneuro/neuroconv/pull/1190)
* Fixed AudioInterface to properly handle 24-bit WAV files by disabling memory mapping for 24-bit files [PR #1226](https://github.com/catalystneuro/neuroconv/pull/1226)
* Use the latest version of ndx-pose for `DeepLabCutInterface` and `LightningPoseDataInterface` [PR #1128](https://github.com/catalystneuro/neuroconv/pull/1128)
* Added a first draft of `.clinerules` [PR #1229](https://github.com/catalystneuro/neuroconv/pull/1229)
* Support for pynwb 3.0 [PR #1231](https://github.com/catalystneuro/neuroconv/pull/1231)
* Support for hdmf 4.0 [PR #1204](https://github.com/catalystneuro/neuroconv/pull/1204)
* Support for numpy 2.0 [PR #1206](https://github.com/catalystneuro/neuroconv/pull/1206)
* Support Spikeinterface 0.102 [PR #1194](https://github.com/catalystneuro/neuroconv/pull/1194)

## Improvements
* Simple writing no longer uses a context manager [PR #1180](https://github.com/catalystneuro/neuroconv/pull/1180)
* Added Returns section to all getter docstrings [PR #1185](https://github.com/catalystneuro/neuroconv/pull/1185)
* ElectricalSeries have better chunking defaults when data is passed as plain array [PR #1184](https://github.com/catalystneuro/neuroconv/pull/1184)
* Ophys interfaces now call `get_metadata` by default when no metadata is passed [PR #1200](https://github.com/catalystneuro/neuroconv/pull/1200) and [PR #1232](https://github.com/catalystneuro/neuroconv/pull/1232)

# v0.6.7 (January 20, 2025)

## Deprecations and Changes

## Bug Fixes
* Temporary set a ceiling for hdmf to avoid a chunking bug  [PR #1175](https://github.com/catalystneuro/neuroconv/pull/1175)

## Features
* Add description to inter-sample-shift for `SpikeGLXRecordingInterface` [PR #1177](https://github.com/catalystneuro/neuroconv/pull/1177)

## Improvements
* `get_json_schema_from_method_signature` now throws a more informative error when an untyped parameter is passed [#1157](https://github.com/catalystneuro/neuroconv/pull/1157)
* Improve the naming of ElectrodeGroups in the `SpikeGLXRecordingInterface` when multi probes are present [PR #1177](https://github.com/catalystneuro/neuroconv/pull/1177)
* Detect mismatch errors between group and group names when writing ElectrodeGroups [PR #1165](https://github.com/catalystneuro/neuroconv/pull/1165)
* Fix metadata bug in `IntanRecordingInterface` where extra devices were added incorrectly if the recording contained multiple electrode groups or names [#1166](https://github.com/catalystneuro/neuroconv/pull/1166)
* Source validation is no longer performed when initializing interfaces or converters [PR #1168](https://github.com/catalystneuro/neuroconv/pull/1168)


# v0.6.6 (December 20, 2024)

## Deprecations and Changes
* Removed use of `jsonschema.RefResolver` as it will be deprecated from the jsonschema library [PR #1133](https://github.com/catalystneuro/neuroconv/pull/1133)
* Completely removed compression settings from most places[PR #1126](https://github.com/catalystneuro/neuroconv/pull/1126)
* Completely removed compression settings from most places [PR #1126](https://github.com/catalystneuro/neuroconv/pull/1126)
* Soft deprecation for `file_path` as an argument of  `SpikeGLXNIDQInterface` and `SpikeGLXRecordingInterface` [PR #1155](https://github.com/catalystneuro/neuroconv/pull/1155)
* `starting_time` in RecordingInterfaces has given a soft deprecation in favor of time alignment methods [PR #1158](https://github.com/catalystneuro/neuroconv/pull/1158)

## Bug Fixes
* datetime objects now can be validated as conversion options [PR #1139](https://github.com/catalystneuro/neuroconv/pull/1126)
* Make `NWBMetaDataEncoder` public again [PR #1142](https://github.com/catalystneuro/neuroconv/pull/1142)
* Fix a bug where data in `DeepLabCutInterface` failed to write when `ndx-pose` was not imported. [#1144](https://github.com/catalystneuro/neuroconv/pull/1144)
* `SpikeGLXConverterPipe` converter now accepts multi-probe structures with multi-trigger and does not assume a specific folder structure [#1150](https://github.com/catalystneuro/neuroconv/pull/1150)
* `SpikeGLXNIDQInterface` is no longer written as an ElectricalSeries [#1152](https://github.com/catalystneuro/neuroconv/pull/1152)
* Fix a bug on ecephys interfaces where extra electrode group and devices were written if the property of the "group_name" was set in the recording extractor [#1164](https://github.com/catalystneuro/neuroconv/pull/1164)


## Features
* Propagate the `unit_electrode_indices` argument from the spikeinterface tools to `BaseSortingExtractorInterface`. This allows users to map units to the electrode table when adding sorting data [PR #1124](https://github.com/catalystneuro/neuroconv/pull/1124)
* Imaging interfaces have a new conversion option `always_write_timestamps` that can be used to force writing timestamps even if neuroconv's heuristics indicates regular sampling rate [PR #1125](https://github.com/catalystneuro/neuroconv/pull/1125)
* Added .csv support to DeepLabCutInterface [PR #1140](https://github.com/catalystneuro/neuroconv/pull/1140)
* `SpikeGLXRecordingInterface` now also accepts `folder_path` making its behavior equivalent to SpikeInterface [#1150](https://github.com/catalystneuro/neuroconv/pull/1150)
* Added the `rclone_transfer_batch_job` helper function for executing Rclone data transfers in AWS Batch jobs. [PR #1085](https://github.com/catalystneuro/neuroconv/pull/1085)
* Added the `deploy_neuroconv_batch_job` helper function for deploying NeuroConv AWS Batch jobs. [PR #1086](https://github.com/catalystneuro/neuroconv/pull/1086)
* YAML specification files now accepts an outer keyword `upload_to_dandiset="< six-digit ID >"` to automatically upload the produced NWB files to the DANDI archive [PR #1089](https://github.com/catalystneuro/neuroconv/pull/1089)
*`SpikeGLXNIDQInterface` now handdles digital demuxed channels (`XD0`) [#1152](https://github.com/catalystneuro/neuroconv/pull/1152)

## Improvements
* Use mixing tests for ecephy's mocks [PR #1136](https://github.com/catalystneuro/neuroconv/pull/1136)
* Use pytest format for dandi tests to avoid window permission error on teardown [PR #1151](https://github.com/catalystneuro/neuroconv/pull/1151)
* Added many docstrings for public functions [PR #1063](https://github.com/catalystneuro/neuroconv/pull/1063)
* Clean up warnings and deprecations in the testing framework for the ecephys pipeline [PR #1158](https://github.com/catalystneuro/neuroconv/pull/1158)
* Enhance the typing of the signature on the `NWBConverter` by adding zarr as a literal option on the backend and backend configuration [PR #1160](https://github.com/catalystneuro/neuroconv/pull/1160)


# v0.6.5 (November 1, 2024)

## Bug Fixes
* Fixed formatwise installation from pipy [PR #1118](https://github.com/catalystneuro/neuroconv/pull/1118)
* Fixed dailies [PR #1113](https://github.com/catalystneuro/neuroconv/pull/1113)

## Deprecations

## Features
* Using in-house `GenericDataChunkIterator` [PR #1068](https://github.com/catalystneuro/neuroconv/pull/1068)
* Data interfaces now perform source (argument inputs) validation with the json schema  [PR #1020](https://github.com/catalystneuro/neuroconv/pull/1020)
* Improve the error message when writing a recording extractor with multiple offsets [PR #1111](https://github.com/catalystneuro/neuroconv/pull/1111)
* Added `channels_to_skip` to `EDFRecordingInterface` so the user can skip non-neural channels [PR #1110](https://github.com/catalystneuro/neuroconv/pull/1110)

## Improvements
* Remove dev test from PR  [PR #1092](https://github.com/catalystneuro/neuroconv/pull/1092)
* Run only the most basic testing while a PR is on draft  [PR #1082](https://github.com/catalystneuro/neuroconv/pull/1082)
* Test that zarr backend_configuration works in gin data tests  [PR #1094](https://github.com/catalystneuro/neuroconv/pull/1094)
* Consolidated weekly workflows into one workflow and added email notifications [PR #1088](https://github.com/catalystneuro/neuroconv/pull/1088)
* Avoid running link test when the PR is on draft  [PR #1093](https://github.com/catalystneuro/neuroconv/pull/1093)
* Centralize gin data preparation in a github action  [PR #1095](https://github.com/catalystneuro/neuroconv/pull/1095)

# v0.6.4 (September 17, 2024)

## Bug Fixes
* Fixed a setup bug introduced in `v0.6.2` where installation process created a directory instead of a file for test configuration file  [PR #1070](https://github.com/catalystneuro/neuroconv/pull/1070)
* The method `get_extractor` now works for `MockImagingInterface`  [PR #1076](https://github.com/catalystneuro/neuroconv/pull/1076)
* Updated opencv version for security [PR #1087](https://github.com/catalystneuro/neuroconv/pull/1087)
* Solved a bug of `PlexonRecordingInterface` where data with multiple streams could not be opened [PR #989](https://github.com/catalystneuro/neuroconv/pull/989)

## Deprecations

## Features
* Added chunking/compression for string-only compound objects: [PR #1042](https://github.com/catalystneuro/neuroconv/pull/1042)
* Added automated EFS volume creation and mounting to the `submit_aws_job` helper function. [PR #1018](https://github.com/catalystneuro/neuroconv/pull/1018)
* Added a mock for segmentation extractors interfaces in ophys: `MockSegmentationInterface` [PR #1067](https://github.com/catalystneuro/neuroconv/pull/1067)
* Added a `MockSortingInterface` for testing purposes. [PR #1065](https://github.com/catalystneuro/neuroconv/pull/1065)
* BaseRecordingInterfaces have a new conversion options `always_write_timestamps` that can be used to force writing timestamps even if neuroconv heuristic indicates regular sampling rate [PR #1091](https://github.com/catalystneuro/neuroconv/pull/1091)


## Improvements
* Testing on mac sillicon [PR #1061](https://github.com/catalystneuro/neuroconv/pull/1061)
* Add writing to zarr test for to the test on data [PR #1056](https://github.com/catalystneuro/neuroconv/pull/1056)
* Modified the CI to avoid running doctests twice [PR #1077](https://github.com/catalystneuro/neuroconv/pull/#1077)
* Consolidated daily workflows into one workflow and added email notifications [PR #1081](https://github.com/catalystneuro/neuroconv/pull/1081)
* Added zarr tests for the test on data with checking equivalent backends [PR #1083](https://github.com/catalystneuro/neuroconv/pull/1083)

# v0.6.3

# v0.6.2 (September 10, 2024)

## Bug Fixes
* Fixed a bug where `IntanRecordingInterface` added two devices [PR #1059](https://github.com/catalystneuro/neuroconv/pull/1059)
* Fix a bug in `add_sorting_to_nwbfile` where `unit_electrode_indices` was only propagated if `waveform_means` was passed [PR #1057](https://github.com/catalystneuro/neuroconv/pull/1057)

## Deprecations
* The following classes and objects are now private `NWBMetaDataEncoder`, `NWBMetaDataEncoder`, `check_if_imaging_fits_into_memory`, `NoDatesSafeLoader` [PR #1050](https://github.com/catalystneuro/neuroconv/pull/1050)

## Features
* Make `config_file_path` optional in `DeepLabCutInterface`[PR #1031](https://github.com/catalystneuro/neuroconv/pull/1031)
* Added `get_stream_names` to `OpenEphysRecordingInterface`: [PR #1039](https://github.com/catalystneuro/neuroconv/pull/1039)
* Most data interfaces and converters now use Pydantic to validate their inputs, including existence of file and folder paths. [PR #1022](https://github.com/catalystneuro/neuroconv/pull/1022)
* All remaining data interfaces and converters now use Pydantic to validate their inputs, including existence of file and folder paths. [PR #1055](https://github.com/catalystneuro/neuroconv/pull/1055)


## Improvements
* Using ruff to enforce existence of public classes' docstrings [PR #1034](https://github.com/catalystneuro/neuroconv/pull/1034)
* Separated tests that use external data by modality [PR #1049](https://github.com/catalystneuro/neuroconv/pull/1049)
* Added Unit Table descriptions for phy and kilosort: [PR #1053](https://github.com/catalystneuro/neuroconv/pull/1053)
* Using ruff to enforce existence of public functions's docstrings [PR #1062](https://github.com/catalystneuro/neuroconv/pull/1062)
* Improved device metadata of `IntanRecordingInterface` by adding the type of controller used [PR #1059](https://github.com/catalystneuro/neuroconv/pull/1059)




# v0.6.1 (August 30, 2024)

## Bug fixes
* Fixed the JSON schema inference warning on excluded fields; also improved error message reporting of which method triggered the error. [PR #1037](https://github.com/catalystneuro/neuroconv/pull/1037)



# v0.6.0 (August 27, 2024)

## Deprecations
