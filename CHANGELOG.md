# v0.9.2 (Upcoming)

## Removals, Deprecations and Changes
* Deprecated using `write_imaging_to_nwbfile` and `write_segmentation_to_nwbfile` without `nwbfile_path`. Use `add_imaging_to_nwbfile` and `add_segmentation_to_nwbfile` instead for adding data to in-memory NWBFile objects. Will be removed on or after June 2026. [PR #1649](https://github.com/catalystneuro/neuroconv/pull/1649)
* Deprecated returning NWBFile when using `append_on_disk_nwbfile=True` in `write_imaging_to_nwbfile` and `write_segmentation_to_nwbfile`. Will return None on or after June 2026. [PR #1649](https://github.com/catalystneuro/neuroconv/pull/1649)

## Bug Fixes
* Fixed bug in `write_imaging_to_nwbfile` where `nwbfile` was incorrectly passed to `add_imaging_to_nwbfile` instead of the created/loaded nwbfile. [PR #1649](https://github.com/catalystneuro/neuroconv/pull/1649)
* Fixed bug in `write_segmentation_to_nwbfile` where invalid `plane_num` parameter was passed to `add_segmentation_to_nwbfile`. [PR #1649](https://github.com/catalystneuro/neuroconv/pull/1649)
* Fixed `get_json_schema_from_method_signature` to skip `*args` (VAR_POSITIONAL) parameters, which was causing schema validation errors when methods used the `*args` pattern for deprecating positional arguments. [PR #1647](https://github.com/catalystneuro/neuroconv/pull/1647)

## Features
* Added `backend`, `backend_configuration`, and `append_on_disk_nwbfile` parameters to `write_imaging_to_nwbfile` and `write_segmentation_to_nwbfile` for better control over file writing, matching the pattern from spikeinterface write functions. [PR #1649](https://github.com/catalystneuro/neuroconv/pull/1649)
* Added support for stream_name to TDT recording interface [#1645](https://github.com/catalystneuro/neuroconv/pull/1645)
* Added `backend`, `backend_configuration`, and `append_on_disk_nwbfile` parameters to `write_imaging_to_nwbfile` and `write_segmentation_to_nwbfile` for better control over file writing, matching the pattern from spikeinterface write functions. [PR #1649](https://github.com/catalystneuro/neuroconv/pull/1649)
* Added `backend`, `backend_configuration`, and `append_on_disk_nwbfile` support to `LightningPoseConverter`. [PR #1652](https://github.com/catalystneuro/neuroconv/pull/1652)

## Improvements
* Added `backend`, `backend_configuration`, and `append_on_disk_nwbfile` parameters to `write_imaging_to_nwbfile` and `write_segmentation_to_nwbfile` for better control over file writing, matching the pattern from spikeinterface write functions. [PR #1649](https://github.com/catalystneuro/neuroconv/pull/1649)
* Renamed test variables `values_dic` to `electrode_row_kwargs` and `unit_row_kwargs` in SpikeInterface tests for improved clarity. [PR #1651](https://github.com/catalystneuro/neuroconv/pull/1651)
* Removed cap on NumPy version for ecephys and icephys formats now that python-quantities v0.16.4 supports NumPy 2.4. [#1648](https://github.com/catalystneuro/neuroconv/pull/1648)


# v0.9.1 (January 28, 2026)

## Removals, Deprecations and Changes
* Deprecated `_VideoInterface` in `LightningPoseConverter` with migration to `ExternalVideoInterface` [#1596](https://github.com/catalystneuro/neuroconv/pull/1596)
* Deprecated `waveform_means` and `waveform_sds` parameters in `add_sorting_to_nwbfile`. Use the new `waveform_data_dict` parameter instead, which bundles waveform data with associated metadata. Will be removed on or after July 2026. [PR #1628](https://github.com/catalystneuro/neuroconv/pull/1628)

## Bug Fixes
* Fixed `add_electrodes_to_nwbfile` and `add_sorting_to_nwbfile` functions to only compute null values for existing table properties when new rows will actually be added. Previously, null values were computed preemptively even when no new electrodes/units needed to be added, causing errors when properties lacked sensible defaults. [#1633](https://github.com/catalystneuro/neuroconv/pull/1633), [#1640](https://github.com/catalystneuro/neuroconv/pull/1640)
* Added cap on NumPy version for all ecephys formats. [#1626](https://github.com/catalystneuro/neuroconv/pull/1626)
* Added Numba as a dependency of the sorting_analyzer environment. [#1627](https://github.com/catalystneuro/neuroconv/pull/1627), [#1635](https://github.com/catalystneuro/neuroconv/pull/1635)
* Added cap on NumPy version for all icephys formats. [#1634](https://github.com/catalystneuro/neuroconv/pull/1634)
* Updated DANDI instance names to fix Ember DANDI upload. [#1631](https://github.com/catalystneuro/neuroconv/pull/1631)
* Added cap on OpenCV version for Mac OS Intel. [#1637](https://github.com/catalystneuro/neuroconv/pull/1637)
* Replaced pytz with zoneinfo [#1638](https://github.com/catalystneuro/neuroconv/pull/1638)
* Removed deprecated `exclude_channel_comparison` parameter from `check_imaging_equal` call in imaging interface tests to fix compatibility with updated roiextractors. [#1642](https://github.com/catalystneuro/neuroconv/pull/1642)

## Features
* Added `waveform_data_dict` keyword-only parameter to `add_sorting_to_nwbfile` and `BaseSortingExtractorInterface.add_to_nwbfile` for passing waveform data with associated metadata (`means`, `sds`, `sampling_rate`, `unit`). The Units table now properly sets `waveform_rate`, `waveform_unit`, and `resolution` attributes, enabling proper HDF5 attribute propagation for downstream tools like MatNWB. [PR #1628](https://github.com/catalystneuro/neuroconv/pull/1628)

## Improvements
* Improved warning message in `get_module` to show both existing and new (ignored) descriptions when there's a mismatch, making it easier to debug processing module conflicts. [PR #1620](https://github.com/catalystneuro/neuroconv/pull/1620)
* Corrected `MiniscopeImagingInterface` documentation and docstrings: `timeStamps.csv` is now correctly documented as required (an error is raised if missing), and removed inaccurate statement about automatic timestamp generation from sampling frequency. [PR #1621](https://github.com/catalystneuro/neuroconv/pull/1621)
* `null_values_for_properties` is exposed to more functions in `spikeinterface` tools allowing user to manually specify the default properties. This is especially helpful when there exists properties which it has no default value when using any adding function related to `add_electrodes_to_nwbfile`. [PR #1624](https://github.com/catalystneuro/neuroconv/pull/1624)
* Made `dichroic_mirror` optional in `TDTFiberPhotometryInterface` to match latest version of `ndx-fiber-photometry` where this field is not required. [PR #1636](https://github.com/catalystneuro/neuroconv/pull/1636)
* Fixed multiple errors in backend configuration documentation: removed unused imports, corrected NWBHDF5IO parameter name from `nwbfile_path` to `path`, fixed undefined `nwbfile` variable in streamlined example, corrected compression options key from `clevel` to `compression_opts`, and removed non-existent `export` parameter. Updated examples to use `read_nwb` for cleaner code. [PR #1641](https://github.com/catalystneuro/neuroconv/pull/1641)

# v0.9.0 (December 4, 2025)

## Removals, Deprecations and Changes
* Removed  `VideoInterface` class scheduled for removal in September 2025. The class is now private (`_VideoInterface`) and used internally by `LightningPoseConverter`. Users should use `ExternalVideoInterface` or `InternalVideoInterface` instead. [PR #1589](https://github.com/catalystneuro/neuroconv/pull/1589)
* Removed deprecated ScanImage interfaces that were scheduled for removal in October 2025: `ScanImageMultiFileImagingInterface`, `ScanImageMultiPlaneImagingInterface`, `ScanImageMultiPlaneMultiFileImagingInterface`, `ScanImageSinglePlaneImagingInterface`, and `ScanImageSinglePlaneMultiFileImagingInterface`. Use `ScanImageImagingInterface` instead. [PR #1576](https://github.com/catalystneuro/neuroconv/pull/1576)
* Removed deprecated SpikeInterface functions scheduled for removal in October 2025: `add_electrical_series_to_nwbfile`, `check_if_recording_traces_fit_into_memory`, `add_electrodes_info_to_nwbfile`, and `add_units_table_to_nwbfile`. Use `add_recording_to_nwbfile`, `add_recording_metadata_to_nwbfile`, and `add_sorting_to_nwbfile` instead. [PR #1583](https://github.com/catalystneuro/neuroconv/pull/1583)
* Removed deprecated `BaseRecordingExtractorInterface.subset_recording()` method scheduled for removal in October 2025. [PR #1583](https://github.com/catalystneuro/neuroconv/pull/1583)
* Removed deprecated `write_electrical_series` parameter from `add_recording_to_nwbfile` scheduled for removal in October 2025. Use `add_recording_metadata_to_nwbfile` if only metadata addition is desired. [PR #1583](https://github.com/catalystneuro/neuroconv/pull/1583)
* Removed deprecated `write_scaled` parameter from `add_recording_to_nwbfile` and `write_recording_to_nwbfile` scheduled for removal in October 2025. The functions now automatically handle channel conversion and offsets. [PR #1583](https://github.com/catalystneuro/neuroconv/pull/1583)
* Removed deprecated `num_frames` parameter from `MockImagingInterface` and `MockSegmentationInterface` scheduled for removal in February 2025. Use `num_samples` instead. [PR #1583](https://github.com/catalystneuro/neuroconv/pull/1583)
* Removed deprecated `output_filepath` parameter from `configure_and_write_nwbfile`. Use `nwbfile_path` instead. [PR #1582](https://github.com/catalystneuro/neuroconv/pull/1582)
* Deprecated `configuration_file_path` parameter in `MiniscopeImagingInterface` and will be removed on or after May 2026. Use `folder_path` instead for standard folder structures. [PR #1593](https://github.com/catalystneuro/neuroconv/pull/1593)
* Deprecated `get_device_metadata` function in `spikeglx_utils` and will be removed on or after May 2026. Use `SpikeGLXRecordingInterface._get_device_metadata_from_probe()` instead, which extracts device metadata directly from probe information. [PR #1599](https://github.com/catalystneuro/neuroconv/pull/1599)
* Deprecated `iterator_opts` parameter in favor of `iterator_options` across all SpikeInterface conversion functions and data interfaces. The deprecated parameter will be removed on or after May 2026. This change improves consistency with naming conventions. [PR #1603](https://github.com/catalystneuro/neuroconv/pull/1603)
* Deprecated `es_key` parameter in `SpikeGLXNIDQInterface` and will be removed on or after May 2026. This parameter has no effect as the interface writes analog data as TimeSeries and digital data as LabeledEvents, not ElectricalSeries. [PR #1615](https://github.com/catalystneuro/neuroconv/pull/1615)
* Removed deprecated `file_path` parameter from `SpikeGLXRecordingInterface` and `SpikeGLXNIDQInterface`. Use `folder_path` and `stream_id` instead. [PR #1616](https://github.com/catalystneuro/neuroconv/pull/1616)

## Bug Fixes
* Fixed bug with TDTFiberPhotometryInterface tests by swapping out test_all_conversion_checks_stub_test_invalid with test_check_run_conversion_stub_test_invalid (avoiding unittest.TestCase.subTests).  [PR #1579](https://github.com/catalystneuro/neuroconv/pull/1579)
* Fixed DANDI live service tests to support dandi-cli 0.73.2 instance-specific API key environment variables (`DANDI_SANDBOX_API_KEY`, `EMBER_SANDBOX_API_KEY`, etc.). Updated all workflows and test files to use the appropriate API key for each DANDI instance. [PR #1588](https://github.com/catalystneuro/neuroconv/pull/1588)

## Features
* Miniscope converter now uses the configuration file to read general folder structures [PR #1528](https://github.com/catalystneuro/neuroconv/pull/1528) [PR #1604](https://github.com/catalystneuro/neuroconv/pull/1604)
* Added a workflow to repack nwbfiles that have already been written to disk with desired chunking and compression settings: [PR #1003](https://github.com/catalystneuro/neuroconv/pull/1003) [PR #1592](https://github.com/catalystneuro/neuroconv/pull/1592)
* Enhanced `TiffImagingInterface` to support multi-file TIFF datasets using `MultiTIFFMultiPageExtractor` from roiextractors. Added support for configurable dimension orders (`dimension_order`), multi-channel data (`num_channels`, `channel_name`), and volumetric imaging (`num_planes`). Both `file_path` (single file) and `file_paths` (multiple files) parameters are now supported for backward compatibility. [PR #1577](https://github.com/catalystneuro/neuroconv/pull/1577) [PR #1578](https://github.com/catalystneuro/neuroconv/pull/1578)
* Added `add_recording_as_spatial_series_to_nwbfile` function to write SpikeInterface recordings as `SpatialSeries` for behavioral tracking data (e.g., position, head direction, gaze tracking). [PR #1574](https://github.com/catalystneuro/neuroconv/pull/1574)
* Enhanced `SpikeGLXNIDQInterface` to support custom metadata for digital channels, enabling users to specify semantic labels, descriptions, and names for NIDQ digital events. Added `metadata_key` parameter to support multiple NIDQ interfaces in the same conversion. Added `digital_channel_groups` parameter for init-time configuration of digital channels, matching the pattern used by `analog_channel_groups`. [PR #1580](https://github.com/catalystneuro/neuroconv/pull/1580) [PR #1615](https://github.com/catalystneuro/neuroconv/pull/1615)
* Enhanced `SpikeGLXNIDQInterface` to support custom metadata for analog channels, enabling users to split NIDQ analog channels into multiple TimeSeries objects with custom groupings via the new `analog_channel_groups` parameter. Users can now organize analog channels semantically (e.g., audio, accelerometer, temperature sensors). The default behavior (single TimeSeries for all analog channels) remains unchanged. [PR #1601](https://github.com/catalystneuro/neuroconv/pull/1601) [PR #1615](https://github.com/catalystneuro/neuroconv/pull/1615)
* Added ADC multiplexing properties (`adc_group` and `adc_sample_order`) to SpikeGLX recordings. These properties preserve hardware provenance information about which ADC each electrode is connected to and its sampling order, enabling downstream computation of inter-sample shifts even when channels are sliced. Requires probeinterface >= 0.3.1. [PR #1597](https://github.com/catalystneuro/neuroconv/pull/1597) [PR #1609](https://github.com/catalystneuro/neuroconv/pull/1609)
* Added `SpikeGLXSyncChannelInterface` for converting Neuropixel synchronization channels from SpikeGLX recordings. [PR #1600](https://github.com/catalystneuro/neuroconv/pull/1600)
* The `SpikeGLXConverterPipe` now includes sync channels. [PR #1600](https://github.com/catalystneuro/neuroconv/pull/1600)
* Added `MiniscopeHeadOrientationInterface` for converting Miniscope head orientation data from BNO055 IMU sensor.[PR #1610](https://github.com/catalystneuro/neuroconv/pull/1610)

## Improvements
* Improved metadata handling in `add_recording_as_spatial_series_to_nwbfile` to no longer modify input and copies are avoided of metadata dictionaries. Made required field defaults explicit. [PR #1605](https://github.com/catalystneuro/neuroconv/pull/1605)
* Improved SpikeGLX device metadata extraction to use probe information from probeinterface instead of parsing meta files. Device metadata now includes serial number as a separate field and enriched description with part number, port, slot, model name, and manufacturer from probe annotations. [PR #1599](https://github.com/catalystneuro/neuroconv/pull/1599)
* Added comprehensive how-to guide "How to Add Behavioral and Sensor Data from Acquisition Systems" documenting usage of `add_recording_as_time_series_to_nwbfile` and `add_recording_as_spatial_series_to_nwbfile` for adding behavioral data from any SpikeInterface-supported format. [PR #1575](https://github.com/catalystneuro/neuroconv/pull/1575)
* Enhanced CSV interface documentation with comprehensive tutorial-style examples showing CSV format requirements, basic usage with column descriptions, customization options for storage location (trials/epochs/custom intervals), and advanced reading options. Fixed in-memory access to `nwbfile.trials` and `nwbfile.epochs`. Improved docstrings across `TimeIntervalsInterface` and `convert_df_to_time_intervals`. [PR #1572](https://github.com/catalystneuro/neuroconv/pull/1572)
* Enhanced live service testing CI to fail explicitly with clear error messages when repository secrets are unavailable for external contributors. Added validation step in workflow to check required credentials and updated documentation to explain the workflow for external contributors (maintainers fork PRs to run live tests). [PR #1590](https://github.com/catalystneuro/neuroconv/pull/1590) [PR #1598](https://github.com/catalystneuro/neuroconv/pull/1598)

# v0.8.3 (November 6, 2025)

## Removals, Deprecations and Changes
* Ophys: Low-level helper functions `add_background_plane_segmentation_to_nwbfile`, `add_fluorescence_traces_to_nwbfile`, `add_background_fluorescence_traces_to_nwbfile`, and `add_summary_images_to_nwbfile` are deprecated and will be removed on or after March 2026. These are low-level functions that should not be called directly. [PR #1559](https://github.com/catalystneuro/neuroconv/pull/1559)
* Refactored extractor interfaces to use explicit `_initialize_extractor` method instead of implicit string-based initialization, improving code clarity and maintainability across all recording, sorting, imaging, and segmentation interfaces [PR #1515](https://github.com/catalystneuro/neuroconv/pull/1515)
* SpikeInterface tools: Using `write_recording_to_nwbfile`, `write_sorting_to_nwbfile`, or `write_sorting_analyzer_to_nwbfile` without `nwbfile_path` to only add data to an in-memory nwbfile is deprecated and will be removed in or after March 2026. Use the corresponding `add_*_to_nwbfile` functions instead. [PR #1565](https://github.com/catalystneuro/neuroconv/pull/1565)
* SpikeInterface tools: Returning an NWBFile object from `write_recording_to_nwbfile`, `write_sorting_to_nwbfile`, and `write_sorting_analyzer_to_nwbfile` in append mode is deprecated and will return None in or after March 2026. This matches the pattern used in `BaseDataInterface.run_conversion[PR #1565](https://github.com/catalystneuro/neuroconv/pull/1565)
* Extractor interfaces: The `extractor` attribute and `get_extractor()` method are deprecated and will be removed on or after March 2026. These were confusingly named as they return extractor classes, not instances. Use the private `_extractor_class` attribute or access the instance directly via `_extractor_instance` [PR #1515](https://github.com/catalystneuro/neuroconv/pull/1515)

## Bug Fixes
* Excluded `contact_ids` property from being added as a duplicate column in the electrodes table. This property is already represented via the `electrode_name` column which uses probe contact identifiers. [PR #1560](https://github.com/catalystneuro/neuroconv/pull/1560)
* Fixed `DeepLabCutInterface` to support output files without 'DLC' in the filename by extracting scorer from CSV/H5 header instead of parsing filename. This improves compatibility with DeepLabCut outputs that don't follow the typical naming convention while maintaining backward compatibility. [PR #1573](https://github.com/catalystneuro/neuroconv/pull/1573)

## Features
* Support roiextractors 0.7.2 [PR #1566](https://github.com/catalystneuro/neuroconv/pull/1566)

## Improvements
* SpikeInterface tools: Enhanced `write_recording_to_nwbfile`, `write_sorting_to_nwbfile`, and `write_sorting_analyzer_to_nwbfile` to support backend configuration parameters (`backend`, `backend_configuration`) for controlling HDF5/Zarr compression and chunking settings, matching the pattern used in `BaseDataInterface.run_conversion`. [PR #1565](https://github.com/catalystneuro/neuroconv/pull/1565)
* Added citation information to README, documentation, and CITATION.cff with reference to the SciPy 2025 conference paper [PR #1569](https://github.com/catalystneuro/neuroconv/pull/1569)


# v0.8.2 (October 17, 2025)

## Removals, Deprecations and Changes
* Ophys: Low-level helper functions `add_imaging_plane_to_nwbfile`, `add_image_segmentation_to_nwbfile`, `add_photon_series_to_nwbfile`, and `add_plane_segmentation_to_nwbfile` are deprecated and will be removed on or after March 2026. These are low-level functions that should not be called directly. [PR #1552](https://github.com/catalystneuro/neuroconv/pull/1552)
* Ophys: Passing `pynwb.device.Device` objects in `metadata['Ophys']['Device']` to `add_devices_to_nwbfile` now issues a `FutureWarning` and is deprecated. This feature will be removed on or after March 2026. Pass device definitions as dictionaries instead (e.g., `{ "name": "Microscope" }`). . [PR #1513](https://github.com/catalystneuro/neuroconv/pull/1513)
* Ecephys: The `iterator_opts` parameter is deprecated across all ecephys interfaces and will be removed on or after March 2026. Use `iterator_options` instead for consistent naming with ophys and behavior interfaces. [PR #1546](https://github.com/catalystneuro/neuroconv/pull/1546)
* Ophys: The `iterator_type='v1'` option for imaging data is deprecated and will be removed on or after March 2026. Use `iterator_type='v2'`or `None` (no chunking). This aligns ophys with ecephys, which only supports 'v2' and None. [PR #1546](https://github.com/catalystneuro/neuroconv/pull/1546)
* Bump minimal python-neo version to 0.14.3 [PR #1550](https://github.com/catalystneuro/neuroconv/pull/1550)
* Add macos-15 intel to CI testing matrix. We no longer support macos 13 and 14 with intel as there is no free runner available [PR #1555](https://github.com/catalystneuro/neuroconv/pull/1555)
* Ophys: Passing `rate` in trace metadata (e.g., `metadata['Ophys']['Fluorescence']['PlaneSegmentation']['raw']['rate']`) is deprecated and will be removed on or after March 2026. [PR #1543](https://github.com/catalystneuro/neuroconv/pull/1543)

## Bug Fixes
* Capped h5py to <3.15 for macOS to prevent compatibility issues [PR #1551](https://github.com/catalystneuro/neuroconv/pull/1551)
* Temporary ceiling on hdmf-zarr (<0.12) to retain compatibility with existing code that uses read_io.file.store [PR #1547](https://github.com/catalystneuro/neuroconv/pull/1547)
* Fixed `append_on_disk_nwbfile=True` raising ValueError when file exists. Replaced `make_or_load_nwbfile` with direct pynwb `NWBHDF5IO` usage in append mode and improved code organization with private helper methods `_write_nwbfile` and `_append_nwbfile` in both `BaseDataInterface` and `NWBConverter` [PR #1540](https://github.com/catalystneuro/neuroconv/pull/1540)
* Refactored `_is_dataset_written_to_file` to use path comparison with public `source` attribute instead of protected `_file` attribute, avoiding dependency on hdmf-zarr internal APIs. Now uses `pathlib.Path.resolve()` for robust cross-platform path comparison. [PR #1545](https://github.com/catalystneuro/neuroconv/pull/1545)
* Enhanced SpikeGLX interface to set `channel_name` property showing all available streams (e.g., "AP0,LF0") for multi-stream deduplication, properly handling cases where AP and LF bands record from the same physical electrodes. [PR #1553](https://github.com/catalystneuro/neuroconv/pull/1553)

## Features
* Support NIDQ analog streams in `OpenEphysBinaryAnalogInterface` [PR #1503](https://github.com/catalystneuro/neuroconv/pull/1503)
* Added `MiniscopeImagingInterface` for single Miniscope acquisition folders with automatic session_start_time extraction, improved docstrings, and comprehensive documentation showing `MiniscopeConverter` for multi-acquisition data, `MiniscopeImagingInterface` for individual folders, and `ConverterPipe` for custom multi-acquisition workflows [PR #1524](https://github.com/catalystneuro/neuroconv/pull/1524)
* Added `iterator_options` parameter to `InternalVideoInterface` to support tqdm progress bars and custom chunking options during video write operations. [PR #1546](https://github.com/catalystneuro/neuroconv/pull/1546)
* Added EMBER support via the new `instance` option for `neuroconv.tools.data_transfers.automatic_dandi_upload`. [PR #1486](https://github.com/catalystneuro/neuroconv/pull/1486)

## Improvements
* Refactored electrode table infrastructure to add `electrode_name` column for probe-based recordings. The electrode table now uses `(group_name, electrode_name, channel_name)` as the unique identifier, enabling channel-specific metadata storage while `electrode_name` indicates which channels share physical electrodes. This supports multi-band recordings (e.g., AP/LF in Neuropixels) and multi-probe setups. [PR #1548](https://github.com/catalystneuro/neuroconv/pull/1548)
* Refactored `_add_fluorescence_traces_to_nwbfile` and `_create_roi_table_region` to remove `deepcopy(metadata)` and `dict_deep_update` patterns. Now extracts DfOverF and Fluorescence metadata separately from user or defaults, checks user metadata first before falling back to defaults for each trace, and passes unmodified metadata to dependencies without mutation. [PR #1543](https://github.com/catalystneuro/neuroconv/pull/1543)
* Aligned iterator type support across ecephys and ophys modules. Both now support only `iterator_type='v2'` and `None`. Fixed misleading error message in spikeinterface that incorrectly mentioned 'v1' support. [PR #1546](https://github.com/catalystneuro/neuroconv/pull/1546)
* Standardized iterator parameter naming across the codebase by introducing `iterator_options` as the preferred parameter name. Updated `BaseRecordingExtractorInterface` and `add_recording_to_nwbfile` to accept both `iterator_options` (new) and `iterator_opts` (deprecated) for backward compatibility. Improved documentation with comprehensive iterator options descriptions including tqdm progress bar support. [PR #1546](https://github.com/catalystneuro/neuroconv/pull/1546)
* Refactored `add_imaging_plane_to_nwbfile` to avoid `dict_deep_update` and metadata mutation, applying targeted defaults only for required fields at point of object creation (issue #1511) [PR #1530](https://github.com/catalystneuro/neuroconv/pull/1530)
* Refactored `add_devices_to_nwbfile` and `add_imaging_plane_to_nwbfile` to avoid `dict_deep_update` and metadata mutation, using defaults directly from single source of truth `_get_default_ophys_metadata()` [PR #1527](https://github.com/catalystneuro/neuroconv/pull/1527)
* Refactored ecephys metadata functions to use a single source of truth pattern, eliminating hardcoded duplications and improving maintainability [PR #1522](https://github.com/catalystneuro/neuroconv/pull/1522)
* Refactored ophys metadata functions to use a single source of truth pattern, preventing accidental mutation of global state and improving maintainability [PR #1521](https://github.com/catalystneuro/neuroconv/pull/1521)
* Add ruff-rule to detect non-pep585 annotation [PR #1520](https://github.com/catalystneuro/roiextractors/pull/1520)
* Replaced deprecated `frame_to_time()` method calls with `get_timestamps()` in optical physiology interfaces [PR #1513](https://github.com/catalystneuro/neuroconv/pull/1513)
* Added SpikeGLXNIDQ interface to conversion gallery with documentation on how different channel types (XA, MA, MD, XD) are converted to NWB [PR #1505](https://github.com/catalystneuro/neuroconv/pull/1505)
* Refactored extractor interfaces to use explicit `_initialize_extractor` method instead of implicit string-based initialization, improving code clarity and maintainability across all recording, sorting, imaging, and segmentation interfaces [PR #1513](https://github.com/catalystneuro/neuroconv/pull/1513)
* Updated `TDTFiberPhotometryInterface` to support the latest version of `ndx-fiber-photometry` (v0.2.1) [PR #1430](https://github.com/catalystneuro/neuroconv/pull/1430)
* Updated ophys roiextractors tests to use only public APIs instead of accessing private attributes, improving compatibility with roiextractors segmentation model changes [PR #1526](https://github.com/catalystneuro/neuroconv/pull/1526)
* Refactored `add_photon_series_to_nwbfile` to remove `get_nwb_imaging_metadata` middleman and inline extractor derivation. Now only derives `dimension` from imaging extractor when user doesn't provide it, ensuring user-provided values are always respected. Passes unmodified metadata to dependencies without mutation. [PR #1537](https://github.com/catalystneuro/neuroconv/pull/1537)
* Refactored `_add_plane_segmentation` to remove `deepcopy(metadata)` and `dict_deep_update` patterns. Now extracts user plane segmentation metadata directly, fills missing required fields with defaults, and passes unmodified metadata to dependencies without mutation. Tracks user intent to provide clear error messages when custom plane segmentation names are not found. [PR #1539](https://github.com/catalystneuro/neuroconv/pull/1539)
* Refactored `add_summary_images_to_nwbfile` to remove `deepcopy(metadata)` and `dict_deep_update` patterns. Now uses `_get_default_ophys_metadata()` directly and extracts SegmentationImages metadata from user or uses defaults. Changed error handling from `AssertionError` to `ValueError` for invalid plane segmentation names. [PR #1540](https://github.com/catalystneuro/neuroconv/pull/1540)


# v0.8.1 (September 16, 2025)

## Removals, Deprecations and Changes
* Changed `automatic_dandi_upload()` function parameter from `staging: bool = False` to `sandbox: bool = False` to align with DANDI Archive's server name change from "staging" to "sandbox". The old `staging` parameter is deprecated and will be removed in February 2026. [PR #1437](https://github.com/catalystneuro/neuroconv/pull/1437)

## Bug Fixes
* Fixed `write/add_sorting_analyzer_to_nwbfile` docstring for requirements of the recording object [PR #1506](https://github.com/catalystneuro/neuroconv/pull/1506)
* Fixed deprecated SpikeInterface extractor imports to use `spikeinterface.extractors.extractor_classes` and updated docstring references to wrapper functions for compatibility with SpikeInterface changes [PR #1490](https://github.com/catalystneuro/neuroconv/pull/1490)
* Fixed documentation version switcher not properly distinguishing between stable and development versions [PR #1483](https://github.com/catalystneuro/neuroconv/pull/1483)
* Fixed sleap-io compatibility by updating to version 0.5.2 and adjusting import path for `append_nwb_data` function [PR #1496](https://github.com/catalystneuro/neuroconv/pull/1496)

## Features
* Added `SortedSpikeGLXConverter` for handling multiple SpikeGLX streams with their corresponding sorting data, enabling proper unit-to-electrode linkage across multiple probes [PR #1449](https://github.com/catalystneuro/neuroconv/pull/1449)
* Added `EDFAnalogInterface` for converting non-electrode/analog channels from EDF files to NWB TimeSeries and a conversion gallery example showing how to combine `EDFRecordingInterface` and `EDFAnalogInterface` to handle mixed EDF files. [PR #1487](https://github.com/catalystneuro/neuroconv/pull/1487)

## Improvements
* Added test to mimic bad channel removal in `write_sorting_analyzer_to_nwbfile` [PR #1506](https://github.com/catalystneuro/neuroconv/pull/1506)
* Enhanced `SortedRecordingConverter` documentation with detailed explanation of the timing problem it solves when linking units to electrodes, and moved electrode linking guide from user guide to how-to section [PR #1479](https://github.com/catalystneuro/neuroconv/pull/1479)
* Use attestation instead of token for publish action [PR #1497](https://github.com/catalystneuro/neuroconv/pull/1497)


# v0.8.0 (August 21, 2025)

## Removals, Deprecations and Changes
* Segmentation writing pipeline no longer supports writing segmentation data without image or pixel masks [PR #1400](https://github.com/catalystneuro/neuroconv/pull/1400)
* Removed deprecated arguments: `load_sync_channel` in `SpikeGLXNIDQInterface` initialization and `start_time`, `write_as` and `write_electrical_series` in `SpikeGLXNIDQInterface.add_to_nwbfile()`. [PR #1378](https://github.com/catalystneuro/neuroconv/pull/1378)
* Removed `starting_time` as an argument from the recording interfaces `add_to_nwbfile` method and the stand alone  `add_recording_segment` utility [PR #1378](https://github.com/catalystneuro/neuroconv/pull/1378)
* Deprecated the `container_name` parameter in `ImageInterface.add_to_nwbfile()` method. Use `metadata_key` in `__init__` instead. This parameter will be removed on or after February 2026. [PR #1439](https://github.com/catalystneuro/neuroconv/pull/1439)
* Removed deprecated type aliases `FolderPathType`, `FilePath`, `OptionalFilePath`, and `OptionalFolderPathType` from utils. Use `pydantic.DirectoryPath`, `pydantic.FilePath`, or their optional variants directly. [PR #1442](https://github.com/catalystneuro/neuroconv/pull/1442)

## Bug Fixes
* Fixed SpikeInterface physical unit properties being incorrectly included in electrodes table [PR #1406](https://github.com/catalystneuro/neuroconv/pull/1406)
* Fixed deprecated ROI extractor method calls: replaced `get_image_size()` with `get_frame_shape()`, `get_num_frames()` with `get_num_samples()`, and `frame_slice()` with `slice_samples()` in ophys interfaces [PR #1443](https://github.com/catalystneuro/neuroconv/pull/1443)
* Fixed logic bug in `get_package` function where boolean check was incorrectly compared to `None` [PR #1477](https://github.com/catalystneuro/neuroconv/pull/1477)
* Fixed docstring typos: corrected "default: Falsee" to "default: False" in multiple datainterface files [PR #1472](https://github.com/catalystneuro/neuroconv/pull/1472)

## Features
* Segmentation interfaces now support roi ids that are strings [PR #1390](https://github.com/catalystneuro/neuroconv/pull/1390)
* Added `MinianSegmentationInterface` for converting Minian segmentation stream data [PR #1107](https://github.com/catalystneuro/neuroconv/pull/1107)
* Added `InscopixImagingInterface` for converting Inscopix imaging data. [PR #1361](https://github.com/catalystneuro/neuroconv/pull/1361)
* Added `InscopixSegmentationInterface` for converting Inscopix segmentation data. [PR #1364](https://github.com/catalystneuro/neuroconv/pull/1364)
* Added `AxonRecordingInterface` for converting extracellular electrophysiology data from Axon Binary Format (ABF) files with automatic session start time extraction [PR #1413](https://github.com/catalystneuro/neuroconv/pull/1413)
* Added `FemtonicsImagingInterface`for converting Femtonics imaging data. [PR #1408](https://github.com/catalystneuro/neuroconv/pull/1408)
* Added `get_available_subjects` static method to `DeepLabCutInterface` for extracting subject names from DeepLabCut output files [PR #1425](https://github.com/catalystneuro/neuroconv/pull/1425)
* Added `MockPoseEstimationInterface` for testing pose estimation workflows with deterministic Lissajous figure motion patterns [PR #1435](https://github.com/catalystneuro/neuroconv/pull/1435)
* Added `IntanAnalogInterface` for converting non-amplifier analog streams from Intan data files, supporting RHD2000 auxiliary input channels, RHD2000 supply voltage channels, USB board ADC input channels, and DC amplifier channels (RHS system only) [PR #1440](https://github.com/catalystneuro/neuroconv/pull/1440)
* Added `metadata_key` parameter to `ImageInterface` to allow custom naming and organization of image containers in NWB files. This enables multiple image interfaces to coexist with distinct container names. [PR #1439](https://github.com/catalystneuro/neuroconv/pull/1439)
* Added per-image metadata support to `ImageInterface` allowing users to specify individual `resolution` (pixels/cm), name and `description` for each image through metadata structure. [PR #1441](https://github.com/catalystneuro/neuroconv/pull/1441)
* Added `rename_unit_ids()` method to `BaseSortingExtractorInterface` for dictionary-based unit ID renaming, enabling clean handling of multiple sorting interfaces with overlapping unit IDs [PR #1451](https://github.com/catalystneuro/neuroconv/pull/1451)
* Added support for setting ProbeGroup objects in `BaseRecordingExtractorInterface.set_probe()` method[PR #1464](https://github.com/catalystneuro/neuroconv/pull/1464)
* Added comprehensive tests for `set_probe` method in `BaseRecordingExtractorInterface` to verify probe and probe group functionality with proper electrode group organization in NWB files [PR #1464](https://github.com/catalystneuro/neuroconv/pull/1464)
* Added PyData Sphinx Theme version switcher to documentation navbar, enabling users to switch between stable (latest release) and main (development) versions [PR #1478](https://github.com/catalystneuro/neuroconv/pull/1478)

## Improvements
* Added comprehensive FFmpeg video conversion how-to guide for converting bespoke video formats to DANDI-compatible formats [PR #1426](https://github.com/catalystneuro/neuroconv/pull/1426)
* Refactored Femtonics Imaging Interface session, munit and channel selection logic. [PR #1433](https://github.com/catalystneuro/roiextractors/pull/1433)
* Implemented PEP 735 dependency groups for test, docs, and dev dependencies [PR #1434](https://github.com/catalystneuro/neuroconv/pull/1434)
* Expanded test coverage for `CaimanSegmentationInterface` to include all stub files and added quality metrics properties (r_values, SNR_comp, cnn_preds) to the PlaneSegmentation table as segmentation_extractor_properties [PR #1436](https://github.com/catalystneuro/neuroconv/pull/1436)
* Added comprehensive how-to guide "Adding Multiple Sorting Interfaces" documenting approaches for handling multiple spike sorting outputs, including unit renaming strategies, separate processing tables, and adding custom properties for provenance tracking [PR #1451](https://github.com/catalystneuro/neuroconv/pull/1451) [PR #1473](https://github.com/catalystneuro/neuroconv/pull/1473)
* The copy button no longer copies the prompt (>>>) in the conversion gallery [PR 1467](https://github.com/catalystneuro/neuroconv/pull/1467)


# v0.7.5 (June 11, 2025)

## Removals, Deprecations and Changes
* Removed automatic subject addition for DeepLabCutInterface. A link is now created only if the skeleton metadata matches the subject ID.  [PR #1362](https://github.com/catalystneuro/neuroconv/pull/1362)

## Bug Fixes
* Fix a bug for avoiding loading the sync stream in `SpikeGLXConverterPipe` [PR #1373](https://github.com/catalystneuro/neuroconv/pull/1373)
* Fixed a bug in the `BrukerTiffSinglePlaneImagingInterface` where the criteria to identify frames belonging to a specific stream relied on the file name instead of the stream name. [PR #1375](https://github.com/catalystneuro/neuroconv/pull/1375)
* Fixed a bug with the Docker dev build [PR #1376](https://github.com/catalystneuro/neuroconv/pull/1376)

## Features
* Added `apply_global_compression` method to `BackendConfiguration` classes to apply compression settings globally across all datasets in a backend configuration. This method allows users to easily configure compression options for all datasets at once rather than setting them individually. [PR #1379](https://github.com/catalystneuro/neuroconv/pull/1379)
* Extra optional kwargs to `BlackrockRecordingInterface` and `BlackrockSortingInterface` for finer control of the neo reader [PR #1290](https://github.com/catalystneuro/neuroconv/pull/1290)



## Improvements
* Add a `how to` documentation for adding extracellular electrophysiology metadata [PR #1311](https://github.com/catalystneuro/neuroconv/pull/1311)
* Improved the docker dailies [PR #1372](https://github.com/catalystneuro/neuroconv/pull/1372)
* Re-enable and improve conversion gallery testing [PR #1380](https://github.com/catalystneuro/neuroconv/pull/1380)
* Implemented cross-OS caches in GitHub Actions load-data action to enable cache sharing between Ubuntu, Windows, and macOS runners, reducing cache storage usage and improving CI efficiency [PR #1385](https://github.com/catalystneuro/neuroconv/pull/1385)
* `MedPC` format is now tested on the conversion gallery [PR #1382](https://github.com/catalystneuro/neuroconv/pull/1382)
* Added conversion gallery testing to daily workflows [PR #1387](https://github.com/catalystneuro/neuroconv/pull/1387)
* Added full metadata support for PoseEstimation container in DeepLabCutInterface [PR #1392](https://github.com/catalystneuro/neuroconv/pull/1392).

# v0.7.4 (May 23, 2025)

## Removals, Deprecations and Changes
* Drop support for python 3.9 [PR #1313](https://github.com/catalystneuro/neuroconv/pull/1313)
* Updated type hints to take advantage of the | operator [PR #1316](https://github.com/catalystneuro/neuroconv/pull/1313)
* Deprecated the following ScanImage interfaces: `ScanImageMultiFileImagingInterface`, `ScanImageMultiPlaneImagingInterface`, `ScanImageMultiPlaneMultiFileImagingInterface`, `ScanImageSinglePlaneImagingInterface`, and `ScanImageSinglePlaneMultiFileImagingInterface`. These interfaces will be removed in or after October 2025. Use `ScanImageImagingInterface` for all those cases instead. [PR #1330](https://github.com/catalystneuro/neuroconv/pull/1330) [PR #1331](https://github.com/catalystneuro/neuroconv/pull/1331)
* Set minimum version requirement for `ndx-pose` to 0.2.0 [PR #1322](https://github.com/catalystneuro/neuroconv/pull/1322)
* Set minimum version for roiextractors as 0.5.13. [PR #1339](https://github.com/catalystneuro/neuroconv/pull/1339)
* ndx-events is now a required dependency by spikeglx [PR #1353](https://github.com/catalystneuro/neuroconv/pull/1353)

## Bug Fixes
* Fix `AudioInterface` to correctly handle WAV filenames with multiple dots by validating only the last suffix. [PR #1327](https://github.com/catalystneuro/neuroconv/pull/1327)
* Fix a stubbing bug in `SpikeGLXNIDQInterface` and `OpenEphysBinaryAnalogInterface` [PR #1360](https://github.com/catalystneuro/neuroconv/pull/1360)

## Features
* Add metadata support for `DeepLabCutInterface`. [PR #1319](https://github.com/catalystneuro/neuroconv/pull/1319)
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
* Added support for renaming Skeletons with `DeepLabCutInterface` [PR #1359](https://github.com/catalystneuro/neuroconv/pull/1359)
* Updated default `PoseEstimationSeries` names in `DeepLabCutInterface` [PR #1363](https://github.com/catalystneuro/neuroconv/pull/1363)
* Testing dependencies include only testing packages (.e.g pytest, pytest-cov) [PR #1357](https://github.com/catalystneuro/neuroconv/pull/1357)
* Testing modalities now run in their separated environment to avoid sequence contamination of dependencies [PR #1357](https://github.com/catalystneuro/neuroconv/pull/1357)


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
* Deprecated  `WaveformExtractor` usage. [PR #821](https://github.com/catalystneuro/neuroconv/pull/821)
* Changed the `tools.spikeinterface` functions (e.g. `add_recording`, `add_sorting`) to have `_to_nwbfile` as suffix  [PR #1015](https://github.com/catalystneuro/neuroconv/pull/1015)
* Deprecated use of `compression` and `compression_options` in `VideoInterface` [PR #1005](https://github.com/catalystneuro/neuroconv/pull/1005)
* `get_schema_from_method_signature` has been deprecated; please use `get_json_schema_from_method_signature` instead. [PR #1016](https://github.com/catalystneuro/neuroconv/pull/1016)
* `neuroconv.utils.FilePathType` and `neuroconv.utils.FolderPathType` have been deprecated; please use `pydantic.FilePath` and `pydantic.DirectoryPath` instead. [PR #1017](https://github.com/catalystneuro/neuroconv/pull/1017)
* Changed the `tools.roiextractors` function (e.g. `add_imaging` and `add_segmentation`) to have the `_to_nwbfile` suffix [PR #1017](https://github.com/catalystneuro/neuroconv/pull/1027)


## Features
* Added `MedPCInterface` for operant behavioral output files. [PR #883](https://github.com/catalystneuro/neuroconv/pull/883)
* Support `SortingAnalyzer` in the `SpikeGLXConverterPipe`. [PR #821](https://github.com/catalystneuro/neuroconv/pull/821)
* Added `TDTFiberPhotometryInterface` data interface, for converting fiber photometry data from TDT file formats. [PR #920](https://github.com/catalystneuro/neuroconv/pull/920)
* Add argument to `add_electrodes` that grants fine control of what to do with the missing values. As a side effect this drops the implicit casting to int when writing int properties to the electrodes table [PR #985](https://github.com/catalystneuro/neuroconv/pull/985)
* Add Plexon2 support [PR #918](https://github.com/catalystneuro/neuroconv/pull/918)
* Converter working with multiple `VideoInterface` instances [PR #914](https://github.com/catalystneuro/neuroconv/pull/914)
* Added helper function `neuroconv.tools.data_transfers.submit_aws_batch_job` for basic automated submission of AWS batch jobs. [PR #384](https://github.com/catalystneuro/neuroconv/pull/384)
* Data interfaces `run_conversion` method now performs metadata validation before running the conversion. [PR #949](https://github.com/catalystneuro/neuroconv/pull/949)
* Introduced `null_values_for_properties` to `add_units_table` to give user control over null values behavior [PR #989](https://github.com/catalystneuro/neuroconv/pull/989)


## Bug fixes
* Fixed the default naming of multiple electrical series in the `SpikeGLXConverterPipe`. [PR #957](https://github.com/catalystneuro/neuroconv/pull/957)
* Write new properties to the electrode table use the global identifier channel_name, group [PR #984](https://github.com/catalystneuro/neuroconv/pull/984)
* Removed a bug where int64 was casted lossy to float [PR #989](https://github.com/catalystneuro/neuroconv/pull/989)

## Improvements
* The `OpenEphysBinaryRecordingInterface` now uses `lxml` for extracting the session start time from the settings.xml file and does not depend on `pyopenephys` anymore. [PR #971](https://github.com/catalystneuro/neuroconv/pull/971)
* Swap the majority of package setup and build steps to `pyproject.toml` instead of `setup.py`. [PR #955](https://github.com/catalystneuro/neuroconv/pull/955)
* The `DeeplabcutInterface` now skips inferring timestamps from movie when timestamps are specified, running faster. [PR #967](https://github.com/catalystneuro/neuroconv/pull/967)
* Improve metadata writing for SpikeGLX data interface. Added contact ids, shank ids and, remove references to shanks for neuropixels 1.0. Also deprecated the previous neuroconv exclusive property "electrode_shank_number` [PR #986](https://github.com/catalystneuro/neuroconv/pull/986)
* Add tqdm with warning to DeepLabCut interface [PR #1006](https://github.com/catalystneuro/neuroconv/pull/1006)
* `BaseRecordingInterface` now calls default metadata when metadata is not passing mimicking `run_conversion` behavior. [PR #1012](https://github.com/catalystneuro/neuroconv/pull/1012)
* Added `get_json_schema_from_method_signature` which constructs Pydantic models automatically from the signature of any function with typical annotation types used throughout NeuroConv. [PR #1016](https://github.com/catalystneuro/neuroconv/pull/1016)
* Replaced all interface annotations with Pydantic types. [PR #1017](https://github.com/catalystneuro/neuroconv/pull/1017)
* Changed typehint collections (e.g. `List`) to standard collections (e.g. `list`). [PR #1021](https://github.com/catalystneuro/neuroconv/pull/1021)
* Testing now is only one dataset per test [PR #1026](https://github.com/catalystneuro/neuroconv/pull/1026)




## v0.5.0 (July 17, 2024)

### Deprecations
* The usage of `compression_options` directly through the `neuroconv.tools.audio` submodule is now deprecated - users should refer to the new `configure_backend` method for a general approach for setting compression. [PR #939](https://github.com/catalystneuro/neuroconv/pull/939)
* The usage of `compression` and `compression_opts` directly through the `FicTracDataInterface` is now deprecated - users should refer to the new `configure_backend` method for a general approach for setting compression. [PR #941](https://github.com/catalystneuro/neuroconv/pull/941)
* The usage of `compression` directly through the `neuroconv.tools.neo` submodule is now deprecated - users should refer to the new `configure_backend` method for a general approach for setting compression. [PR #943](https://github.com/catalystneuro/neuroconv/pull/943)
* The usage of `compression_options` directly through the `neuroconv.tools.ophys` submodule is now deprecated - users should refer to the new `configure_backend` method for a general approach for setting compression. [PR #940](https://github.com/catalystneuro/neuroconv/pull/940)
* Removed the option of running `interface.run_conversion` without `nwbfile_path` argument . [PR #951](https://github.com/catalystneuro/neuroconv/pull/951)

### Features
* Added docker image and tests for an automated Rclone configuration (with file stream passed via an environment variable). [PR #902](https://github.com/catalystneuro/neuroconv/pull/902)

### Bug fixes
* Fixed the conversion option schema of a `SpikeGLXConverter` when used inside another `NWBConverter`. [PR #922](https://github.com/catalystneuro/neuroconv/pull/922)
* Fixed a case of the `NeuroScopeSortingExtractor` when the optional `xml_file_path` is not specified. [PR #926](https://github.com/catalystneuro/neuroconv/pull/926)
* Fixed `Can't specify experiment type when converting .abf to .nwb with Neuroconv`. [PR #609](https://github.com/catalystneuro/neuroconv/pull/609)
* Remove assumption that the ports of the Intan acquisition system correspond to electrode groupings in `IntanRecordingInterface`  [PR #933](https://github.com/catalystneuro/neuroconv/pull/933)
* Add ValueError for empty metadata in  `make_or_load_nwbfile` when an nwbfile needs to be created [PR #948](https://github.com/catalystneuro/neuroconv/pull/948)

### Improvements
* Make annotations from the raw format available on `IntanRecordingInterface`. [PR #934](https://github.com/catalystneuro/neuroconv/pull/943)
* Add an option to suppress display the progress bar (tqdm) in `VideoContext`  [PR #937](https://github.com/catalystneuro/neuroconv/pull/937)
* Automatic compression of data in the `LightnignPoseDataInterface` has been disabled - users should refer to the new `configure_backend` method for a general approach for setting compression. [PR #942](https://github.com/catalystneuro/neuroconv/pull/942)
* Port over `dlc2nwb` utility functions for ease of maintenance. [PR #946](https://github.com/catalystneuro/neuroconv/pull/946)



## v0.4.11 (June 14, 2024)

### Bug fixes
* Added a skip condition in `get_default_dataset_io_configurations` for datasets with any zero-length axis in their `full_shape`. [PR #894](https://github.com/catalystneuro/neuroconv/pull/894)
* Added `packaging` explicitly to minimal requirements. [PR #904](https://github.com/catalystneuro/neuroconv/pull/904)
* Fixed bug when using `make_or_load_nwbfile` with `overwrite=True` on an existing (but corrupt) HDF5 file. [PR #911](https://github.com/catalystneuro/neuroconv/pull/911)
* Change error trigger with warning trigger when adding both `OnePhotonSeries` and `TwoPhotonSeries` to the same file ([Issue #906](https://github.com/catalystneuro/neuroconv/issues/906)). [PR #907](https://github.com/catalystneuro/neuroconv/pull/907)

### Improvements
* Propagated `photon_series_type` to `BaseImagingExtractorInterface` init instead of passing it as an argument of `get_metadata()` and `get_metadata_schema()`. [PR #847](https://github.com/catalystneuro/neuroconv/pull/847)
* Converter working with multiple VideoInterface instances [PR 914](https://github.com/catalystneuro/neuroconv/pull/914)



## v0.4.10 (June 6, 2024)

### Bug fixes
* Fixed bug causing overwrite of NWB GUIDE watermark. [PR #890](https://github.com/catalystneuro/neuroconv/pull/890)


## v0.4.9 (June 5, 2024)

### Deprecations
* Removed `stream_id` as an argument from `IntanRecordingInterface`. [PR #794](https://github.com/catalystneuro/neuroconv/pull/794)
* The usage of `compression` and `compression_opts` directly through the `neuroconv.tools.spikeinterface` submodule are now deprecated - users should refer to the new `configure_backend` method for a general approach for setting compression. [PR #805](https://github.com/catalystneuro/neuroconv/pull/805)
* Dropped the testing of Python 3.8 on the CI. Dropped support for Python 3.8 in setup. [PR #853](https://github.com/catalystneuro/neuroconv/pull/853)
* Deprecated skip_features argument in `add_sorting`. [PR #872](https://github.com/catalystneuro/neuroconv/pull/872)
* Deprecate old (v1) iterator from the ecephys pipeline. [PR #876](https://github.com/catalystneuro/neuroconv/pull/876)

### Features
* Added `backend` control to the `make_or_load_nwbfile` helper method in `neuroconv.tools.nwb_helpers`. [PR #800](https://github.com/catalystneuro/neuroconv/pull/800)
* Released the first official Docker images for the package on the GitHub Container Repository (GHCR). [PR #383](https://github.com/catalystneuro/neuroconv/pull/383)
* Support "one-file-per-signal" and "one-file-per-channel" mode with `IntanRecordingInterface`. [PR #791](https://github.com/catalystneuro/neuroconv/pull/791)
* Added `get_default_backend_configuration` method to all `DataInterface` classes. Also added HDF5 `backend` control to all standalone `.run_conversion(...)` methods for those interfaces. [PR #801](https://github.com/catalystneuro/neuroconv/pull/801)
* Added `get_default_backend_configuration` method to all `NWBConverter` classes. Also added HDF5 `backend` control to `.run_conversion(...)`. [PR #804](https://github.com/catalystneuro/neuroconv/pull/804)
* Released the first official Docker images for the package on the GitHub Container Repository (GHCR). [PR #383](https://github.com/catalystneuro/neuroconv/pull/383)
* Added `ScanImageMultiFileImagingInterface` for multi-file (buffered) ScanImage format and changed `ScanImageImagingInterface` to be routing classes for single and multi-plane imaging. [PR #809](https://github.com/catalystneuro/neuroconv/pull/809)
* Added a function to generate ogen timestamps and data from onset times and parameters to `tools.optogenetics`. [PR #832](https://github.com/catalystneuro/neuroconv/pull/832)
* Added `configure_and_write_nwbfile` and optimized imports in `tools.nwb_helpers` module. [PR #848](https://github.com/catalystneuro/neuroconv/pull/848)
* `configure_backend` may now apply a `BackendConfiguration` to equivalent in-memory `pynwb.NWBFile` objects that have different address in RAM. [PR #848](https://github.com/catalystneuro/neuroconv/pull/848)
* Add support for doubled ragged arrays in `add_units_table` [PR #879](https://github.com/catalystneuro/neuroconv/pull/879)
* Add support for doubled ragged arrays in `add_electrodes` [PR #881](https://github.com/catalystneuro/neuroconv/pull/881)
* Propagate `ignore_integrity_checks` from neo to IntanRecordingInterface [PR #887](https://github.com/catalystneuro/neuroconv/pull/887)


### Bug fixes
* Remove JSON Schema `definitions` from the `properties` field. [PR #818](https://github.com/catalystneuro/neuroconv/pull/818)
* Fixed writing waveforms directly to file. [PR #799](https://github.com/catalystneuro/neuroconv/pull/799)
* Avoid in-place modification of the metadata in the `VideoInterface` and on neo tools. [PR #814](https://github.com/catalystneuro/neuroconv/pull/814)
* Replaced `waveform_extractor.is_extension` with `waveform_extractor.has_extension`. [PR #799](https://github.com/catalystneuro/neuroconv/pull/799)
* Fixed an issue with `set_aligned_starting_time` for all `SortingInterface`'s that did not have an initial segment start set (and no recording attached). [PR #823](https://github.com/catalystneuro/neuroconv/pull/823)
* Fixed a bug with `parameterized` and `pytest-xdist==3.6.1` in the `ScanImageImagingInterface` tests. [PR #829](https://github.com/catalystneuro/neuroconv/pull/829)
* Added `XX` and `XO` to the base metadata schema. [PR #833](https://github.com/catalystneuro/neuroconv/pull/833)
* `BaseImagingExtractor.add_to_nwbfile()` is fixed in the case where metadata is not supplied. [PR #849](https://github.com/catalystneuro/neuroconv/pull/849)
* Prevent `SpikeGLXConverterPipe` from setting false properties on the sub-`SpikeGLXNIDQInterface`. [PR #860](https://github.com/catalystneuro/neuroconv/pull/860)
* Fixed a bug when adding ragged arrays to the electrode and units table. [PR #870](https://github.com/catalystneuro/neuroconv/pull/870)
* Fixed a bug where `write_recording` will call an empty nwbfile when passing a path. [PR #877](https://github.com/catalystneuro/neuroconv/pull/877)
* Fixed a bug that failed to properly include time alignment information in the output NWB file for objects added from any `RecordingInterface` in combination with `stub_test=True`. [PR #884](https://github.com/catalystneuro/neuroconv/pull/884)
* Fixed a bug that prevented passing `nwbfile=None` and a `backend_configuration` to `NWBConverter.run_conversion`. [PR #885](https://github.com/catalystneuro/neuroconv/pull/885)

### Improvements
* Added soft deprecation warning for removing `photon_series_type` from `get_metadata()` and `get_metadata_schema()` (in [PR #847](https://github.com/catalystneuro/neuroconv/pull/847)). [PR #866](https://github.com/catalystneuro/neuroconv/pull/866)
* Fixed docstrings related to backend configurations for various methods. [PR #822](https://github.com/catalystneuro/neuroconv/pull/822)
* Added automatic `backend` detection when a `backend_configuration` is passed to an interface or converter. [PR #840](https://github.com/catalystneuro/neuroconv/pull/840)
* Improve printing of bytes. [PR #831](https://github.com/catalystneuro/neuroconv/pull/831)
* Support for pathlib in source data schema validation. [PR #854](https://github.com/catalystneuro/neuroconv/pull/854)
* Use `ZoneInfo` instead of `dateutil.tz` in the conversion gallery. [PR #858](https://github.com/catalystneuro/neuroconv/pull/858)
* Exposed `progress_bar_class` to ecephys and ophys data iterators. [PR #861](https://github.com/catalystneuro/neuroconv/pull/861)
* Unified the signatures between `add_units`, `add_sorting` and `write_sorting`. [PR #875](https://github.com/catalystneuro/neuroconv/pull/875)
* Improved descriptions of all folder and file paths in the source schema, useful for rendering in the GUIDE. [PR #886](https://github.com/catalystneuro/neuroconv/pull/886)
* Added watermark via `source_script` field of `NWBFile` metadata. `source_script_file_name` is also required to be specified in this case to avoid invalidation. [PR #888](https://github.com/catalystneuro/neuroconv/pull/888)
* Remove parsing xml parsing from the `__init__` of `BrukerTiffSinglePlaneImagingInterface` [PR #895](https://github.com/catalystneuro/neuroconv/pull/895)

### Testing
* Add general test for metadata in-place modification by interfaces. [PR #815](https://github.com/catalystneuro/neuroconv/pull/815)



# v0.4.8 (March 20, 2024)

### Bug fixes
* Fixed writing the `electrodes` field in `add_electrical_series` when multiple groups are present. [PR #784](https://github.com/catalystneuro/neuroconv/pull/784)

### Improvements
* Upgraded Pydantic support to `>v2.0.0`. [PR #767](https://github.com/catalystneuro/neuroconv/pull/767)
* Absorbed the `DatasetInfo` model into the `DatasetIOConfiguration` model. [PR #767](https://github.com/catalystneuro/neuroconv/pull/767)
* Keyword argument `field_name` of the `DatasetIOConfiguration.from_neurodata_object` method has been renamed to `dataset_name` to be more consistent with its usage. This only affects direct initialization of the model; usage via the `BackendConfiguration` constructor and its associated helper functions in `neuroconv.tools.nwb_helpers` is unaffected. [PR #767](https://github.com/catalystneuro/neuroconv/pull/767)
* Manual construction of a `DatasetIOConfiguration` now requires the field `dataset_name`, and will be validated to match the final path of `location_in_file`. Usage via the automated constructors is unchanged. [PR #767](https://github.com/catalystneuro/neuroconv/pull/767)
* Enhance `get_schema_from_method_signature` to extract descriptions from the method docval. [PR #771](https://github.com/catalystneuro/neuroconv/pull/771)
* Avoid writing `channel_to_uV` and `offset_to_uV` in `add_electrodes`  [PR #803](https://github.com/catalystneuro/neuroconv/pull/803)
* `BaseSegmentationExtractorInterface` now supports optional background plane segmentations and associated fluorescence traces [PR #783](https://github.com/catalystneuro/neuroconv/pull/783)



# v0.4.7 (February 21, 2024)

### Deprecation
* Removed `.get_electrode_table_json()` on the `BaseRecordingExtractorInterface` in favor of GUIDE specific interactions. [PR #431](https://github.com/catalystneuro/neuroconv/pull/431)
* Removed the `SIPickleRecordingInterface` and `SIPickleSortingInterface` interfaces. [PR #757](https://github.com/catalystneuro/neuroconv/pull/757)
* Removed the `SpikeGLXLFPInterface` interface. [PR #757](https://github.com/catalystneuro/neuroconv/pull/757)

### Bug fixes
* LocalPathExpander matches only `folder_paths` or `file_paths` if that is indicated in the passed specification. [PR #679](https://github.com/catalystneuro/neuroconv/pull/675) and [PR #675](https://github.com/catalystneuro/neuroconv/pull/679
* Fixed depth consideration in partial chunking pattern for the ROI data buffer. [PR #677](https://github.com/catalystneuro/neuroconv/pull/677)
* Fix mapping between channel names and the electrode table when writing more than one `ElectricalSeries` to the NWBFile. This fixes an issue when the converter pipeline of `SpikeGLXConverterPipe` was writing the electrode table region of the NIDQ stream incorrectly. [PR #678](https://github.com/catalystneuro/neuroconv/pull/678)
* Fix `configure_backend` when applied to `TimeSeries` contents that leverage internal links for `data` or `timestamps`. [PR #732](https://github.com/catalystneuro/neuroconv/pull/732)

### Features
* Changed the `Suite2pSegmentationInterface` to support multiple plane segmentation outputs. The interface now has a `plane_name` and `channel_name` arguments to determine which plane output and channel trace add to the NWBFile. [PR #601](https://github.com/catalystneuro/neuroconv/pull/601)
* Added `create_path_template` and corresponding tests [PR #680](https://github.com/catalystneuro/neuroconv/pull/680)
* Added tool function `configure_datasets` for configuring all datasets of an in-memory `NWBFile` to be backend specific. [PR #571](https://github.com/catalystneuro/neuroconv/pull/571)
* Added `LightningPoseConverter` to add pose estimation data and the original and the optional labeled video added as ImageSeries to NWB. [PR #633](https://github.com/catalystneuro/neuroconv/pull/633)
* Added gain as a required `__init__` argument for `TdtRecordingInterface`. [PR #704](https://github.com/catalystneuro/neuroconv/pull/704)
* Extract session_start_time from Plexon `plx` recording file. [PR #723](https://github.com/catalystneuro/neuroconv/pull/723)

### Improvements
* `nwbinspector` has been removed as a minimal dependency. It becomes an extra (optional) dependency with `neuroconv[dandi]`. [PR #672](https://github.com/catalystneuro/neuroconv/pull/672)
* Added a `from_nwbfile` class method constructor to all `BackendConfiguration` models. [PR #673](https://github.com/catalystneuro/neuroconv/pull/673)
* Added compression to `FicTracDataInterface`. [PR #678](https://github.com/catalystneuro/neuroconv/pull/678)
* Exposed `block_index` to all OpenEphys interfaces. [PR #695](https://github.com/catalystneuro/neuroconv/pull/695)
* Added support for `DynamicTable` columns in the `configure_backend` tool function. [PR #700](https://github.com/catalystneuro/neuroconv/pull/700)
* Refactored `ScanImagingInterface` to reference ROIExtractors' version of `extract_extra_metadata`. [PR #731](https://github.com/catalystneuro/neuroconv/pull/731)
* Added support for Long NHP probe types for the `SpikeGLXRecorddingInterfacce`. [PR #701](https://github.com/catalystneuro/neuroconv/pull/701)
* Remove unnecessary duplication of probe setting in `SpikeGLXRecordingInterface`. [PR #696](https://github.com/catalystneuro/neuroconv/pull/696)
* Added associated suffixes to all interfaces and converters. [PR #734](https://github.com/catalystneuro/neuroconv/pull/734)
* Added convenience function `get_format_summaries` to `tools.importing` (and exposed at highest level). [PR #734](https://github.com/catalystneuro/neuroconv/pull/734)

### Testing
* `RecordingExtractorInterfaceTestMixin` now compares either `group_name`, `group` or a default value of  `ElectrodeGroup` to the `group` property in the `NWBRecordingExtractor` instead of comparing `group` to `group` as it was done before [PR #736](https://github.com/catalystneuro/neuroconv/pull/736)
* `TestScanImageImagingInterfaceRecent` now checks metadata against new roiextractors implementation [PR #741](https://github.com/catalystneuro/neuroconv/pull/741).
* Removed editable installs from the CI workflow. [PR #756](https://github.com/catalystneuro/neuroconv/pull/756)


# v0.4.6 (November 30, 2023)

### Features
* Added Pydantic data models of `BackendConfiguration` for both HDF5 and Zarr datasets (container/mapper of all the `DatasetConfiguration`s for a particular file). [PR #568](https://github.com/catalystneuro/neuroconv/pull/568)
* Changed the metadata schema for `Fluorescence` and `DfOverF` where the traces metadata can be provided as a dict instead of a list of dicts.
  The name of the plane segmentation is used to determine which traces to add to the `Fluorescence` and `DfOverF` containers. [PR #632](https://github.com/catalystneuro/neuroconv/pull/632)
* Modify the filtering of traces to also filter out traces with empty values. [PR #649](https://github.com/catalystneuro/neuroconv/pull/649)
* Added tool function `get_default_dataset_configurations` for identifying and collecting all fields of an in-memory `NWBFile` that could become datasets on disk; and return instances of the Pydantic dataset models filled with default values for chunking/buffering/compression. [PR #569](https://github.com/catalystneuro/neuroconv/pull/569)
* Added tool function `get_default_backend_configuration` for conveniently packaging the results of `get_default_dataset_configurations` into an easy-to-modify mapping from locations of objects within the file to their correseponding dataset configuration options, as well as linking to a specific backend DataIO. [PR #570](https://github.com/catalystneuro/neuroconv/pull/570)
* Added `set_probe()` method to `BaseRecordingExtractorInterface`. [PR #639](https://github.com/catalystneuro/neuroconv/pull/639)
* Changed default chunking of `ImagingExtractorDataChunkIterator` to select `chunk_shape` less than the chunk_mb threshold while keeping the original image size. The default `chunk_mb` changed to 10MB. [PR #667](https://github.com/catalystneuro/neuroconv/pull/667)

### Fixes
* Fixed GenericDataChunkIterator (in hdmf.py) in the case where the number of dimensions is 1 and the size in bytes is greater than the threshold of 1 GB. [PR #638](https://github.com/catalystneuro/neuroconv/pull/638)
* Changed `np.floor` and `np.prod` usage to `math.floor` and `math.prod` in various files. [PR #638](https://github.com/catalystneuro/neuroconv/pull/638)
* Updated minimal required version of DANDI CLI; updated `run_conversion_from_yaml` API function and tests to be compatible with naming changes. [PR #664](https://github.com/catalystneuro/neuroconv/pull/664)

### Improvements
 * Change metadata extraction library from `fparse` to `parse`. [PR #654](https://github.com/catalystneuro/neuroconv/pull/654)
 * The `dandi` CLI/API is now an optional dependency; it is still required to use the `tool` function for automated upload as well as the YAML-based NeuroConv CLI. [PR #655](https://github.com/catalystneuro/neuroconv/pull/655)



# v0.4.5 (November 6, 2023)

### Back-compatibility break
* The `CEDRecordingInterface` has now been removed; use the `Spike2RecordingInterface` instead. [PR #602](https://github.com/catalystneuro/neuroconv/pull/602)

### Features
* Added support for python 3.12 [PR #626](https://github.com/catalystneuro/neuroconv/pull/626)
* Added `session_start_time` extraction to `FicTracDataInterface`. [PR #598](https://github.com/catalystneuro/neuroconv/pull/598)
* Added `imaging_plane_name` keyword argument to `add_imaging_plane` function to determine which imaging plane to add from the metadata by name instead of `imaging_plane_index`.
* Added reference for `imaging_plane` to default plane segmentation metadata. [PR #594](https://github.com/catalystneuro/neuroconv/pull/594)
* Changed Compass container for Position container in the `FicTracDataInterface`.  [PR #606](https://github.com/catalystneuro/neuroconv/pull/605)
* Added option to write units in meters by providing a radius in `FicTracDataInterface`. [PR #606](https://github.com/catalystneuro/neuroconv/pull/605)
* Added `parent_container` keyword argument to `add_photon_series` that defines whether to add the photon series to acquisition or 'ophys' processing module. [PR #587](https://github.com/catalystneuro/neuroconv/pull/587)
* Added Pydantic data models of `DatasetInfo` (immutable summary of core dataset values such as maximum shape and dtype) and `DatasetConfiguration` for both HDF5 and Zarr datasets (the optional layer that specifies chunk/buffering/compression). [PR #567](https://github.com/catalystneuro/neuroconv/pull/567)
* Added alignment methods to `FicTracDataInterface`.  [PR #607](https://github.com/catalystneuro/neuroconv/pull/607)
* Added alignment methods support to `MockRecordingInterface` [PR #611](https://github.com/catalystneuro/neuroconv/pull/611)
* Added `NeuralynxNvtInterface`, which can read position tracking NVT files. [PR #580](https://github.com/catalystneuro/neuroconv/pull/580)
* Adding radius as a conversion factor in `FicTracDataInterface`.  [PR #619](https://github.com/catalystneuro/neuroconv/pull/619)
* Coerce `FicTracDataInterface` original timestamps to start from 0.  [PR #619](https://github.com/catalystneuro/neuroconv/pull/619)
* Added configuration metadata to `FicTracDataInterface`.  [PR #618](https://github.com/catalystneuro/neuroconv/pull/618)
* Expose number of jobs to `automatic_dandi_upload`. [PR #624](https://github.com/catalystneuro/neuroconv/pull/624)
* Added `plane_segmentation_name` keyword argument to determine which plane segmentation to add from the metadata by name instead of `plane_segmentation_index`.
  `plane_segmentation_name` is exposed at `BaseSegmentationExtractorInterface.add_to_nwbfile()` function to support adding segmentation output from multiple planes. [PR #623](https://github.com/catalystneuro/neuroconv/pull/623)
* Added `SegmentationImages` to metadata_schema in `BaseSegmentationExtractorInterface` to allow for the modification of the name and description of Images container and description of the summary images. [PR #622](https://github.com/catalystneuro/neuroconv/pull/622)
* Default chunking pattern of RecordingInterfaces now attempts to use as many channels as possible up to 64 total, and fill with as much time as possible up to the `chunk_mb`. This also required raising the lower HDMF version to 3.11.0 (which introduced 10 MB default chunk sizes). [PR #630](https://github.com/catalystneuro/neuroconv/pull/630)

### Fixes
* Remove `starting_time` reset to default value (0.0) when adding the rate and updating the `photon_series_kwargs` or `roi_response_series_kwargs`, in `add_photon_series` or `add_fluorescence_traces`. [PR #595](https://github.com/catalystneuro/neuroconv/pull/595)
* Changed the date parsing in `OpenEphysLegacyRecordingInterface` to `datetime.strptime` with the expected date format explicitly set to `"%d-%b-%Y %H%M%S"`. [PR #577](https://github.com/catalystneuro/neuroconv/pull/577)
* Pin lower bound HDMF version to `3.10.0`. [PR #586](https://github.com/catalystneuro/neuroconv/pull/586)

### Deprecation
* Removed `use_times` and `buffer_size` from `add_photon_series`. [PR #600](https://github.com/catalystneuro/neuroconv/pull/600)

### Testing
* Adds `MockImagingInterface` as a general testing mechanism for ophys imaging interfaces [PR #604](https://github.com/catalystneuro/neuroconv/pull/604).



# v0.4.4

### Features

* `DeepLabCutInterface` now allows using custom timestamps via `set_aligned_timestamps` method before running conversion. [PR #531](https://github.com/catalystneuro/neuroconv/pull/532)

### Fixes

* Reorganize timeintervals schema to reside in `schemas/` dir to ensure its inclusion in package build. [PR #573](https://github.com/catalystneuro/neuroconv/pull/573)



# v0.4.3

### Fixes

* The `sonpy` package for the Spike2 interface no longer attempts installation on M1 Macs. [PR #563](https://github.com/catalystneuro/neuroconv/pull/563)
* Fixed `subset_sorting` to explicitly cast `end_frame` to int to avoid SpikeInterface frame slicing edge case. [PR #565](https://github.com/catalystneuro/neuroconv/pull/565)



# v0.4.2

### Fixes

* Exposed `es_key` argument to users where it was previously omitted on `MaxOneRecordingInterface`, `OpenEphysLegacyRecordingInterface`, and `OpenEphysRecordingInterface`. [PR #542](https://github.com/catalystneuro/neuroconv/pull/542)
* Added deepcopy for metadata in `make_nwbfile_from_metadata`. [PR #545](https://github.com/catalystneuro/neuroconv/pull/545)
* Fixed edge case in `subset_sorting` where `end_frame` could exceed recording length. [PR #551](https://github.com/catalystneuro/neuroconv/pull/551)
* Alter `add_electrodes` behavior,  no error is thrown if a property is present in the metadata but not in the recording extractors. This allows the combination of recording objects that have different properties. [PR #558](https://github.com/catalystneuro/neuroconv/pull/558)

### Features

* Added converters for Bruker TIF format to support multiple streams of imaging data.
  Added `BrukerTiffSinglePlaneConverter` for single plane imaging data which initializes a `BrukerTiffSinglePlaneImagingInterface` for each data stream.
  The available data streams can be checked by `BrukerTiffSinglePlaneImagingInterface.get_streams(folder_path)` method.
  Added `BrukerTiffMultiPlaneConverter` for volumetric imaging data with `plane_separation_type` argument that defines
  whether to load the imaging planes as a volume (`"contiguous"`) or separately (`"disjoint"`).
  The available data streams for the defined  `plane_separation_type`  can be checked by `BrukerTiffMultiPlaneImagingInterface.get_streams(folder_path, plane_separation_type)` method.
* Added FicTrac data interface. [PR #517](https://github.com/catalystneuro/neuroconv/pull/#517)

### Documentation and tutorial enhancements

* Added FicTrac to the conversion gallery and docs API. [PR #560](https://github.com/catalystneuro/neuroconv/pull/#560)



# v0.4.1

### Fixes

* Propagated additional arguments, such as `cell_id`, from the `metadata["Icephys"]["Electrodes"]` dictionary used in `tools.neo.add_icephys_electrode`. [PR #538](https://github.com/catalystneuro/neuroconv/pull/538)
* Fixed mismatch between expected `Electrodes` key in `tools.neo.add_icephys_electrode` and the metadata automatically generated by the `AbfInterface`. [PR #538](https://github.com/catalystneuro/neuroconv/pull/538)



# v0.4.0

### Back-compatibility break

* Create separate `.add_to_nwbfile` method for all DataInterfaces. This is effectively the previous `.run_conversion` method but limited to operations on an in-memory `nwbfile`: pynwb.NWBFile` object and does not handle any I/O. [PR #455](https://github.com/catalystneuro/neuroconv/pull/455)

### Fixes

* Set gzip compression by default on spikeinterface based interfaces `run_conversion`. [PR #499](https://github.com/catalystneuro/neuroconv/pull/#499)

* Temporarily disabled filtering for all-zero traces in `add_fluorescence_traces` as the current implementation is very slow for nearly all zero traces (e.g. suite2p deconvolved traces). [PR #527](https://github.com/catalystneuro/neuroconv/pull/527)

### Features

* Added stream control with the `stream_name` argument to the `NeuralynxRecordingExtractor`. [PR #369](https://github.com/catalystneuro/neuroconv/pull/369)

* Added a common `.temporally_align_data_interfaces` method to the `NWBConverter` class to use as a specification of the protocol for temporally aligning the data interfaces of the converter. [PR #362](https://github.com/catalystneuro/neuroconv/pull/362)

* Added `CellExplorerRecordingInterface` for adding data raw and lfp data from the CellExplorer format. CellExplorer's new format contains a `basename.session.mat` file containing
    rich metadata about the session which can be used to extract the recording information such as sampling frequency and type and channel metadata such as
    groups, location and brain area [#488](https://github.com/catalystneuro/neuroconv/pull/488)

* `CellExplorerSortingInterface` now supports extracting sampling frequency from the new data format. CellExplorer's new format contains a `basename.session.mat` file containing
    rich metadata including the sorting sampling frequency [PR #491](https://github.com/catalystneuro/neuroconv/pull/491) and [PR #502](https://github.com/catalystneuro/neuroconv/pull/502)
* Added `MiniscopeBehaviorInterface` for Miniscope behavioral data. The interface uses `ndx-miniscope` extension to add a `Miniscope` device with the behavioral camera metadata,
  and an `ImageSeries` in external mode that is linked to the device. [PR #482](https://github.com/catalystneuro/neuroconv/pull/482)
  * `CellExplorerSortingInterface` now supports adding channel metadata to the nwbfile with `write_ecephys_metadata=True` as a conversion option [PR #494](https://github.com/catalystneuro/neuroconv/pull/494)

* Added `MiniscopeImagingInterface` for Miniscope imaging data stream. The interface uses `ndx-miniscope` extension to add a `Miniscope` device with the microscope device metadata,
  and the imaging data as `OnePhotonSeries`. [PR #468](https://github.com/catalystneuro/neuroconv/pull/468)

* Added `MiniscopeConverter` for combining the conversion of Miniscope imaging and behavioral data streams. [PR #498](https://github.com/catalystneuro/neuroconv/pull/498)

### Improvements

* Avoid redundant timestamp creation in `add_eletrical_series` for recording objects without time vector. [PR #495](https://github.com/catalystneuro/neuroconv/pull/495)

* Avoid modifying the passed `metadata` structure via `deep_dict_update` in `make_nwbfile_from_metadata`.  [PR #476](https://github.com/catalystneuro/neuroconv/pull/476)

### Testing

* Added gin test for `CellExplorerRecordingInterface`. CellExplorer's new format contains a `basename.session.mat` file containing
    rich metadata about the session which can be used to extract the recording information such as sampling frequency and type and channel metadata such as
    groups, location and brain area [#488](https://github.com/catalystneuro/neuroconv/pull/488).
  * Added gin test for `CellExplorerSortingInterface`. CellExplorer's new format contains a `basename.session.mat` file containing
  rich metadata about the session which can be used to extract the recording information such as sampling frequency and type and channel metadata such as
  groups, location and brain area [PR #494](https://github.com/catalystneuro/neuroconv/pull/494).




# v0.3.0 (June 7, 2023)

### Back-compatibility break
* `ExtractorInterface` classes now access their extractor with the classmethod `cls.get_extractor()` instead of the attribute `self.Extractor`. [PR #324](https://github.com/catalystneuro/neuroconv/pull/324)
* The `spikeextractor_backend` option was removed for all `RecordingExtractorInterface` classes. ([PR #324](https://github.com/catalystneuro/neuroconv/pull/324), [PR #309](https://github.com/catalystneuro/neuroconv/pull/309)]
* The `NeuroScopeMultiRecordingExtractor` has been removed. If your conversion required this, please submit an issue requesting instructions for how to implement it. [PR #309](https://github.com/catalystneuro/neuroconv/pull/309)
* The `SIPickle` interfaces have been removed. [PR #309](https://github.com/catalystneuro/neuroconv/pull/309)
* The previous conversion option `es_key` has been moved to the `__init__` of all `BaseRecordingExtractorInterface` classes. It is no longer possible to use this argument in the `run_conversion` method. [PR #318](https://github.com/catalystneuro/neuroconv/pull/318)
* Change `BaseDataInterface.get_conversion_options_schema` from `classmethod` to object method. [PR #353](https://github.com/catalystneuro/neuroconv/pull/353)
* Removed `utils.json_schema.get_schema_for_NWBFile` and moved base metadata schema to external json file. Added constraints to Subject metadata to match DANDI. [PR #376](https://github.com/catalystneuro/neuroconv/pull/376)
* Duplicate video file paths in the VideoInterface and AudioInterface are no longer silently resolved; please explicitly remove duplicates when initializing the interfaces. [PR #403](https://github.com/catalystneuro/neuroconv/pull/403)
* Duplicate audio file paths in the AudioInterface are no longer silently resolved; please explicitly remove duplicates when initializing the interfaces. [PR #402](https://github.com/catalystneuro/neuroconv/pull/402)

### Features
* The `OpenEphysRecordingInterface` is now a wrapper for `OpenEphysBinaryRecordingInterface`. [PR #294](https://github.com/catalystneuro/neuroconv/pull/294)
* Swapped the backend for `CellExplorerSortingInterface` from `spikeextactors` to `spikeinterface`. [PR #267](https://github.com/catalystneuro/neuroconv/pull/267)
* In the conversion YAML, `DataInterface` classes must now be specified as a dictionary instead of a list. [PR #311](https://github.com/catalystneuro/neuroconv/pull/311)
* In the conversion YAML, conversion_options can be specified on the global level. [PR #312](https://github.com/catalystneuro/neuroconv/pull/312)
* The `OpenEphysRecordingInterface` now redirects to legacy or binary interface depending on the file format.
  It raises NotImplementedError until the interface for legacy format is added. [PR #296](https://github.com/catalystneuro/neuroconv/pull/296)
* Added the `OpenEphysLegacyRecordingInterface` to support Open Ephys legacy format (`.continuous` files). [PR #295](https://github.com/catalystneuro/neuroconv/pull/295)
* Added `PlexonSortingInterface` to support plexon spiking data. [PR #316](https://github.com/catalystneuro/neuroconv/pull/316)
* Changed `SpikeGLXRecordingInterface` to accept either the AP or LF bands as file paths. Each will automatically set the correseponding `es_key` and corresponding metadata for each band or probe. [PR #298](https://github.com/catalystneuro/neuroconv/pull/298)
* The `OpenEphysRecordingInterface` redirects to `OpenEphysLegacyRecordingInterface` for legacy format files instead of raising NotImplementedError. [PR #349](https://github.com/catalystneuro/neuroconv/pull/349)
* Added a `SpikeGLXConverter` for easy combination of multiple IMEC and NIDQ data streams. [PR #292](https://github.com/catalystneuro/neuroconv/pull/292)
* Added an `interfaces_by_category` lookup table to `neuroconv.datainterfaces` to make searching for interfaces by modality and format easier. [PR #352](https://github.com/catalystneuro/neuroconv/pull/352)
* `neuroconv.utils.jsonschema.get_schema_from_method_signature` can now support the `Dict[str, str]` typehint, which allows `DataInterface.__init__` and `.run_conversion` to handle dictionary arguments. [PR #360](https://github.com/catalystneuro/neuroconv/pull/360)
* Added `neuroconv.tools.testing.data_interface_mixins` module, which contains test suites for different types of
  DataInterfaces [PR #357](https://github.com/catalystneuro/neuroconv/pull/357)
* Added `keywords` to `DataInterface` classes. [PR #375](https://github.com/catalystneuro/neuroconv/pull/375)
* Uses `open-cv-headless` instead of open-cv, making the package lighter [PR #387](https://github.com/catalystneuro/neuroconv/pull/387).
* Adds `MockRecordingInterface` as a general testing mechanism for ecephys interfaces [PR #395](https://github.com/catalystneuro/neuroconv/pull/395).
* `metadata` returned by `DataInterface.get_metadata()` is now a `DeepDict` object, making it easier to add and adjust metadata. [PR #404](https://github.com/catalystneuro/neuroconv/pull/404).
* The `OpenEphysLegacyRecordingInterface` is now extracts the `session_start_time` in `get_metadata()` from `Neo` (`OpenEphysRawIO`) and does not depend on `pyopenephys` anymore. [PR #410](https://github.com/catalystneuro/neuroconv/pull/410)
* Added `expand_paths`. [PR #377](https://github.com/catalystneuro/neuroconv/pull/377)
* Added basic temporal alignment methods to ecephys, ophys, and icephys DataInterfaces. These are `get_timestamps`, `align_starting_time`, `align_timestamps`, and `align_by_interpolation`. Added tests that serve as a first demonstration of the intended uses in a variety of cases. [PR #237](https://github.com/catalystneuro/neuroconv/pull/237) [PR #283](https://github.com/catalystneuro/neuroconv/pull/283) [PR #400](https://github.com/catalystneuro/neuroconv/pull/400)
* Added basic temporal alignment methods to the SLEAPInterface. Added holistic per-interface, per-method unit testing for ecephys and ophys interfaces. [PR #401](https://github.com/catalystneuro/neuroconv/pull/401)
* Added `expand_paths`. [PR #377](https://github.com/catalystneuro/neuroconv/pull/377), [PR #448](https://github.com/catalystneuro/neuroconv/pull/448)
* Added `.get_electrode_table_json()` to the `BaseRecordingExtractorInterface` as a convenience helper for the GUIDE project. [PR #431](https://github.com/catalystneuro/neuroconv/pull/431)
* Added `BrukerTiffImagingInterface` to support Bruker TIF imaging data. This format consists of individual TIFFs (each file contains a single frame) in OME-TIF format (.ome.tif files) and metadata in XML format (.xml file). [PR #390](https://github.com/catalystneuro/neuroconv/pull/390)
* Added `MicroManagerTiffImagingInterface` to support Micro-Manager TIF imaging data. This format consists of multipage TIFFs in OME-TIF format (.ome.tif files) and configuration settings in JSON format ('DisplaySettings.json' file). [PR #423](https://github.com/catalystneuro/neuroconv/pull/423)
* Added a `TemporallyAlignedDataInterface` definition for convenience when creating a custom interface for pre-aligned data. [PR #434](https://github.com/catalystneuro/neuroconv/pull/434)
* Added `write_as`, `units_name`, `units_description` to `BaseSortingExtractorInterface` `run_conversion` method to be able to modify them in conversion options. [PR #438](https://github.com/catalystneuro/neuroconv/pull/438)
* Added basic temporal alignment methods to the VideoInterface. These are `align_starting_time` is split into `align_starting_times` (list of times, one per video file) and `align_global_starting_time` (shift all by a scalar amount). `align_by_interpolation` is not yet implemented for this interface. [PR #283](https://github.com/catalystneuro/neuroconv/pull/283)
* Added stream control for the `OpenEphysBinaryRecordingInterface`. [PR #445](https://github.com/catalystneuro/neuroconv/pull/445)
* Added the `BaseTemporalAlignmentInterface` to serve as the new base class for all new temporal alignment methods. [PR #442](https://github.com/catalystneuro/neuroconv/pull/442)
* Added direct imports for all base classes from the outer level; you may now call `from neuroconv import BaseDataInterface, BaseTemporalAlignmentInterface, BaseExtractorInterface`. [PR #442](https://github.com/catalystneuro/neuroconv/pull/442)
* Added basic temporal alignment methods to the AudioInterface. `align_starting_time` is split into `align_starting_times` (list of times, one per audio file) and `align_global_starting_time` (shift all by a scalar amount). `align_by_interpolation` and other timestamp-based approaches is not yet implemented for this interface. [PR #402](https://github.com/catalystneuro/neuroconv/pull/402)
* Changed the order of recording properties extraction in `NeuroscopeRecordingInterface` and `NeuroScopeLFPInterface` to make them consistent with each other [PR #466](https://github.com/catalystneuro/neuroconv/pull/466)
* The `ScanImageImagingInterface` has been updated to read metadata from more recent versions of ScanImage [PR #457](https://github.com/catalystneuro/neuroconv/pull/457)
* Refactored `add_two_photon_series()` to `add_photon_series()` and added `photon_series_type` optional argument which can be either `"OnePhotonSeries"` or `"TwoPhotonSeries"`.
  Changed `get_default_ophys_metadata()` to add `Device` and `ImagingPlane` metadata which are both used by imaging and segmentation.
  Added `photon_series_type` to `get_nwb_imaging_metadata()` to fill metadata for `OnePhotonSeries` or `TwoPhotonSeries`. [PR #462](https://github.com/catalystneuro/neuroconv/pull/462)
* Split `align_timestamps` and `align_starting_times` into `align_segment_timestamps` and `align_segment_starting_times` for API consistency for multi-segment `RecordingInterface`s. [PR #463](https://github.com/catalystneuro/neuroconv/pull/463)
* Rename `align_timestamps` and `align_segmentt_timestamps` into `set_aligned_timestamps` and `set_aligned_segment_timestamps` to more clearly indicate their usage and behavior. [PR #470](https://github.com/catalystneuro/neuroconv/pull/470)


### Testing
* The tests for `automatic_dandi_upload` now follow up-to-date DANDI validation rules for file name conventions. [PR #310](https://github.com/catalystneuro/neuroconv/pull/310)
* Deactivate `MaxOneRecordingInterface` metadata tests [PR #371]((https://github.com/catalystneuro/neuroconv/pull/371)
* Integrated the DataInterface testing mixin to the SLEAP Interface. [PR #401](https://github.com/catalystneuro/neuroconv/pull/401)
* Added holistic per-interface, per-method unit testing for ecephys and ophys interfaces. [PR #283](https://github.com/catalystneuro/neuroconv/pull/283)
* Live service tests now run in a separate non-required GitHub action. [PR #420]((https://github.com/catalystneuro/neuroconv/pull/420)
* Integrated the `DataInterfaceMixin` class of tests to the `VideoInterface`. [PR #403](https://github.com/catalystneuro/neuroconv/pull/403)
* Add `generate_path_expander_demo_ibl` and associated test for `LocalPathExpander` [PR #456](https://github.com/catalystneuro/neuroconv/pull/456)
* Improved testing of all interface alignment methods via the new `TemporalAlignmentMixin` class. [PR #459](https://github.com/catalystneuro/neuroconv/pull/459)

### Fixes
* `BlackrockRecordingInterface` now writes all ElectricalSeries to "acquisition" unless changed using the `write_as` flag in `run_conversion`. [PR #315](https://github.com/catalystneuro/neuroconv/pull/315)
* Excluding Python versions 3.8 and 3.9 for the `EdfRecordingInterface` on M1 macs due to installation problems. [PR #319](https://github.com/catalystneuro/neuroconv/pull/319)
* Extend type array condition in `get_schema_from_hdmf_class` for dataset types (excludes that are DataIO). [PR #418](https://github.com/catalystneuro/neuroconv/pull/418)
* The `base_directory` argument to all `PathExpander` classes can now accept string inputs as well as `Path` inputs. [PR #427](https://github.com/catalystneuro/neuroconv/pull/427)
* Fixed the temporal alignment methods for the `RecordingInterfaces` which has multiple segments. [PR #411](https://github.com/catalystneuro/neuroconv/pull/411)
* Fixes to the temporal alignment methods for the `SortingInterface`, both single and multi-segment and recordingless. [PR #413](https://github.com/catalystneuro/neuroconv/pull/413)
* Fixes to the temporal alignment methods for the certain formats of the `RecordingInterface`. [PR #459](https://github.com/catalystneuro/neuroconv/pull/459)
* Fixes the naming of LFP interfaces to be `ElectricalSeriesLFP` instead of `ElectricalSeriesLF`. [PR #467](https://github.com/catalystneuro/neuroconv/pull/467)
* Fixed an issue with incorrect modality-specific extra requirements being associated with certain behavioral formats. [PR #469](https://github.com/catalystneuro/neuroconv/pull/469)

### Documentation and tutorial enhancements
* The instructions to build the documentation were moved to ReadTheDocs. [PR #323](https://github.com/catalystneuro/neuroconv/pull/323)
* Move testing instructions to ReadTheDocs. [PR #320](https://github.com/catalystneuro/neuroconv/pull/320)
* Moved NeuroConv catalogue from ReadMe.md to ReadTheDocs.
  [PR #322](https://github.com/catalystneuro/neuroconv/pull/322)
* Moved instructions to build the documentation from README.md to ReadTheDocs. [PR #323](https://github.com/catalystneuro/neuroconv/pull/323)
* Add `Spike2RecordingInterface` to conversion gallery. [PR #338](https://github.com/catalystneuro/neuroconv/pull/338)
* Remove authors from module docstrings [PR #354](https://github.com/catalystneuro/neuroconv/pull/354)
* Add examples for `LocalPathExpander` usage [PR #456](https://github.com/catalystneuro/neuroconv/pull/456)
* Add better docstrings to the aux functions of the Neuroscope interface [PR #485](https://github.com/catalystneuro/neuroconv/pull/485)

### Pending deprecation
* Change name from `CedRecordingInterface` to `Spike2RecordingInterface`. [PR #338](https://github.com/catalystneuro/neuroconv/pull/338)

### Improvements
* Use `Literal` in typehints (incompatible with Python<=3.8). [PR #340](https://github.com/catalystneuro/neuroconv/pull/340)
* `BaseDataInterface.get_source_schema` modified so it works for `.__init__` and `.__new__`. [PR #374](https://github.com/catalystneuro/neuroconv/pull/374)



# v0.2.4 (February 7, 2023)

### Deprecation
* All usages of `use_times` have been removed from spikeinterface tools and interfaces. The function `add_electrical_series` now determines whether the timestamps of the spikeinterface recording extractor are uniform or not and automatically stores the data according to best practices [PR #40](https://github.com/catalystneuro/neuroconv/pull/40)
* Dropped Python 3.7 support. [PR #237](https://github.com/catalystneuro/neuroconv/pull/237)

### Features
* Added a tool for determining rising and falling frames from TTL signals (`parse_rising_frames_from_ttl` and `get_falling_frames_from_ttl`). [PR #244](https://github.com/catalystneuro/neuroconv/pull/244)
* Added the `SpikeGLXNIDQInterface` for reading data from `.nidq.bin` files, as well as the ability to parse event times from specific channels via the `get_event_starting_times_from_ttl` method. Also included a `neuroconv.tools.testing.MockSpikeGLXNIDQInterface` for testing purposes. [PR #247](https://github.com/catalystneuro/neuroconv/pull/247)
* Improved handling of writing multiple probes to the same `NWB` file [PR #255](https://github.com/catalystneuro/neuroconv/pull/255)

### Pending deprecation
* Added `DeprecationWarnings` to all `spikeextractors` backends. [PR #265](https://github.com/catalystneuro/neuroconv/pull/265)
* Added `DeprecationWarning`s for `spikeextractors` objects in `neuroconv.tools.spikeinterface`. [PR #266](https://github.com/catalystneuro/neuroconv/pull/266)

### Fixes
* Temporarily hotfixed the `tensorflow` dependency after the release of `deeplabcut==2.3.0`. [PR #268](https://github.com/catalystneuro/neuroconv/pull/268)
* Fixed cleanup of waveform tests in SI tools. [PR #277](https://github.com/catalystneuro/neuroconv/pull/277)
* Fixed metadata structure for the CsvTimeIntervalsInterface, which was previously not passed validation in NWBConverters. [PR #237](https://github.com/catalystneuro/neuroconv/pull/237)
* Added propagation of the `load_sync_channel` argument for the `SpikeGLXNIDQInterface`. [PR #282](https://github.com/catalystneuro/neuroconv/pull/282)
* Fixed the default `es_key` used by stand-alone write using any `RecordingExtractorInterface` or `LFPExtractorInterface`. [PR #288](https://github.com/catalystneuro/neuroconv/pull/288)
* Fixed the default `ExtractorName` used to load the spikeinterface extractor of the `SpikeGLXLFPInterface`. [PR #288](https://github.com/catalystneuro/neuroconv/pull/288)

### Testing
* Re-organized the `test_gin_ecephys` file by splitting into each sub-modality. [PR #282](https://github.com/catalystneuro/neuroconv/pull/282)
* Add testing support for Python 3.11. [PR #234](https://github.com/catalystneuro/neuroconv/pull/234)




# v0.2.3

### Documentation and tutorial enhancements
* Remove `Path(path_to_save_nwbfile).is_file()` from each of the gallery pages. [PR #177](https://github.com/catalystneuro/neuroconv/pull/177)
* Improve docstring for `SpikeGLXRecordingInterface`. [PR #226](https://github.com/catalystneuro/neuroconv/pull/226)
* Correct typing of SpikeGLX in conversion gallery. [PR #223](https://github.com/catalystneuro/neuroconv/pull/223)
* Added tutorial for utilizing YAML metadata in a conversion pipeline. [PR #240](https://github.com/catalystneuro/neuroconv/pull/240)
* Added page in User Guide for how to use CSVs to specify metadata. [PR #241](https://github.com/catalystneuro/neuroconv/pull/177)
* Added the `BaseDataInterface` in the API docs. [PR #242](https://github.com/catalystneuro/neuroconv/pull/242)
* Fixed typo in styling section. [PR #253](https://github.com/catalystneuro/neuroconv/pull/253)
* Updated docs on JSON schema. [PR #256](https://github.com/catalystneuro/neuroconv/pull/256)
* Improved compliance with numpy-style docstring [PR #260](https://github.com/catalystneuro/neuroconv/pull/260)

### Features
* Added `AudioInterface` for files in `WAV` format using the `add_acoustic_waveform_series` utility function
  from `tools/audio` to write audio data to NWB. [PR #196](https://github.com/catalystneuro/neuroconv/pull/196)
* Added the `MaxOneRecordingInterface` for writing data stored in MaxOne (.raw.h5) format. [PR #222](https://github.com/catalystneuro/neuroconv/pull/222)
* Added the `MCSRawRecordingInterface` for writing data stored in MCSRaw (.raw) format. [PR #220](https://github.com/catalystneuro/neuroconv/pull/220)
* Added the `MEArecRecordingInterface` for writing data stored in MEArec (structured .h5) format. [PR #218](https://github.com/catalystneuro/neuroconv/pull/218)
* Added the `AlphaOmegaRecordingInterface` for writing data stored in AlphaOmega (folder of .mrx) format. [PR #212](https://github.com/catalystneuro/neuroconv/pull/212)
* Added the `PlexonRecordingInterface` for writing data stored in Plexon (.plx) format. [PR #206](https://github.com/catalystneuro/neuroconv/pull/206)
* Added the `BiocamRecordingInterface` for writing data stored in Biocam (.bwr) format. [PR #210](https://github.com/catalystneuro/neuroconv/pull/210)
* Added function to add acoustic series as `AcousticWaveformSeries` object as __acquisition__ or __stimulus__ to NWB. [PR #201](https://github.com/catalystneuro/neuroconv/pull/201)
* Added new form to the GitHub repo for requesting support for new formats. [PR #207](https://github.com/catalystneuro/neuroconv/pull/207)
* Simplified the writing of `channel_conversion` during `add_electrical_series` if the vector of gains is uniform; in this case, they are now combined into the scalar `conversion` value. [PR #218](https://github.com/catalystneuro/neuroconv/pull/218)
* Implement timestamp extraction from videos for the SLEAPInterface [PR #238](https://github.com/catalystneuro/neuroconv/pull/238)
* Prevented writing of default values for optional columns on the `ElectrodeTable`. [PR #219](https://github.com/catalystneuro/neuroconv/pull/219)
* Add interfaces for Excel and Csv time intervals tables. [PR #252](https://github.com/catalystneuro/neuroconv/pull/252)

### Testing
* Added a `session_id` to the test file for the `automatic_dandi_upload` helper function. [PR #199](https://github.com/catalystneuro/neuroconv/pull/199)
* `pre-commit` version bump. [PR #235](https://github.com/catalystneuro/neuroconv/pull/235)
* Added a `testing` sub-module to `src` and added a method (`generate_mock_ttl_signal`) for generating synthetic TTL pulses. [PR #245](https://github.com/catalystneuro/neuroconv/pull/245)

### Fixes
* `VideoInterface`. Only raise a warning if the difference between the rate estimated from timestamps and the fps (frames per seconds) is larger than two decimals. [PR #200](https://github.com/catalystneuro/neuroconv/pull/200)
* Fixed the bug in a `VideoInterface` where it would use `DataChunkIterator` even if the conversion options indicated that it should not. [PR #200](https://github.com/catalystneuro/neuroconv/pull/200)
* Update usage requirements for HDMF to prevent a buffer overflow issue fixed in hdmf-dev/hdmf#780. [PR #195](https://github.com/catalystneuro/neuroconv/pull/195)
* Remove the deprecated `distutils.version` in favor of `packaging.version` [PR #233](https://github.com/catalystneuro/neuroconv/pull/233)



# v0.2.2

### Testing

* Added a set of dev branch gallery tests for PyNWB, HDMF, SI, and NEO. [PR #113](https://github.com/catalystneuro/neuroconv/pull/113)
* Added tests for the `TypeError` and `ValueError` raising for the new `starting_frames` argument of `MovieDataInterface.run_conversion()`. [PR #113](https://github.com/catalystneuro/neuroconv/pull/113)
* Added workflow for automatic detection of CHANGELOG.md updates for PRs. [PR #187](https://github.com/catalystneuro/neuroconv/pull/187)
* Added support for python 3.10 [PR #229](https://github.com/catalystneuro/neuroconv/pull/229)

### Fixes

* Fixed a new docval typing error that arose in `hdmf>3.4.6` versions. [PR #113](https://github.com/catalystneuro/neuroconv/pull/113)
* Fixed a new input argument issue for `starting_frames` when using `external_file` for an `ImageSeries` in `pynwb>2.1.0` versions. [PR #113](https://github.com/catalystneuro/neuroconv/pull/113)
* Fixed issues regarding interaction between metadata rate values and extractor rate values in `tools.roiextractors`. [PR #159](https://github.com/catalystneuro/neuroconv/pull/159)
* Fixed sampling frequency resolution issue when detecting this from timestamps in `roiextractors.write_imaging` and `roiextractors.write_segmentation`. [PR #159](https://github.com/catalystneuro/neuroconv/pull/159)

### Documentation and tutorial enhancements
* Added a note in User Guide/DataInterfaces to help installing custom dependencies for users who use Z-shell (`zsh`). [PR #180](https://github.com/catalystneuro/neuroconv/pull/180)
* Added `MovieInterface` example in the conversion gallery. [PR #183](https://github.com/catalystneuro/neuroconv/pull/183)

### Features
* Added `ConverterPipe`, a class that allows chaining previously initialized interfaces for batch conversion and corresponding tests [PR #169](https://github.com/catalystneuro/neuroconv/pull/169)
* Added automatic extraction of metadata for `NeuralynxRecordingInterface` including filtering information for channels, device and recording time information [PR #170](https://github.com/catalystneuro/neuroconv/pull/170)
* Added stubbing capabilities to timestamp extraction in the `MovieInterface` avoiding scanning through the whole file when `stub_test=True` [PR #181](https://github.com/catalystneuro/neuroconv/pull/181)
* Added a flag `include_roi_acceptance` to `tools.roiextractors.write_segmentation` and corresponding interfaces to allow disabling the addition of boolean columns indicating ROI acceptance. [PR #193](https://github.com/catalystneuro/neuroconv/pull/193)
* Added `write_waveforms()` function in `tools.spikeinterface` to write `WaveformExtractor` objects
[PR #217](https://github.com/catalystneuro/neuroconv/pull/217)

### Pending deprecation
* Replaced the `MovieInterface` with `VideoInterface` and introduced deprecation warnings for the former. [PR #74](https://github.com/catalystneuro/neuroconv/pull/74)



# v0.2.1

### Fixes

* Updated `BlackrockRecordingInterface` to support multi stream file and added gin corresponding gin tests [PR #176](https://github.com/catalystneuro/neuroconv/pull/176)



# v0.2.0

### Back-compatability break
* All built-in DataInterfaces are now nested under the `neuroconv.datainterfaces` import structure - they are no longer available from the outer level. To import a data interface, use the syntax `from neuroconv.datainterfaces import <name of interface>`. [PR #74](https://github.com/catalystneuro/neuroconv/pull/74)
* The `AxonaRecordingExtractorInterface` has been renamed to `AxonaRecordingInterface`. [PR #74](https://github.com/catalystneuro/neuroconv/pull/74)
* The `AxonaUnitRecordingExtractorInterface` has been renamed to `AxonaUnitRecordingInterface`. [PR #74](https://github.com/catalystneuro/neuroconv/pull/74)
* The `BlackrockRecordingExtractorInterface` has been renamed to `BlackrockRecordingInterface`. [PR #74](https://github.com/catalystneuro/neuroconv/pull/74)
* The `BlackrockSortingExtractorInterface` has been renamed to `BlackrockSortingInterface`. [PR #74](https://github.com/catalystneuro/neuroconv/pull/74)
* The `OpenEphysRecordingExtractorInterface` has been renamed to `OpenEphysRecordingInterface`. [PR #74](https://github.com/catalystneuro/neuroconv/pull/74)
* The `OpenEphysSortingExtractorInterface` has been renamed to `OpenEphysSortingInterface`. [PR #74](https://github.com/catalystneuro/neuroconv/pull/74)
* The `KilosortSortingInterface` has been renamed to `KiloSortSortingInterface` to be more consistent with SpikeInterface. [PR #107](https://github.com/catalystneuro/neuroconv/pull/107)
* The `Neuroscope` interfaces have been renamed to `NeuroScope` to be more consistent with SpikeInterface. [PR #107](https://github.com/catalystneuro/neuroconv/pull/107)
* The `tools.roiextractors.add_epoch` functionality has been retired in the newest versions of ROIExtractors. [PR #112](https://github.com/catalystneuro/neuroconv/pull/112)
* Removed deprecation warnings for `save_path` argument (which is now `nwbfile_path` everywhere in the package). [PR #124](https://github.com/catalystneuro/neuroconv/pull/124)
* Changed default device name for the ecephys pipeline. Device_ecephys -> DeviceEcephys [PR #154](https://github.com/catalystneuro/neuroconv/pull/154)
* Change names of written electrical series on the ecephys pipeline. ElectricalSeries_raw -> ElectricalSeriesRaw, ElectricalSeries_processed -> ElectricalSeriesProcessed, ElectricalSeries_lfp -> ElectricalSeriesLFP  [PR #153](https://github.com/catalystneuro/neuroconv/pull/153)
* Drop spikeextractor backend support for NeuralynxRecordingInterface [PR #174](https://github.com/catalystneuro/neuroconv/pull/174)

### Fixes
* Prevented the CEDRecordingInterface from writing non-ecephys channel data. [PR #37](https://github.com/catalystneuro/neuroconv/pull/37)
* Fixed description in `write_sorting` and in `add_units_table` to have "neuroconv" in the description. [PR #104](https://github.com/catalystneuro/neuroconv/pull/104)
* Updated `spikeinterface` version number to 0.95.1 to fix issue with `SpikeGLXInterface` probe annotations.
  The issue is described [here](https://github.com/SpikeInterface/spikeinterface/issues/923). [PR #132](https://github.com/catalystneuro/neuroconv/pull/132)

### Improvements
* Unified the `run_conversion` method of `BaseSegmentationExtractorInterface` with that of all the other base interfaces. The method `write_segmentation` now uses the common `make_or_load_nwbfile` context manager [PR #29](https://github.com/catalystneuro/neuroconv/pull/29)
* Coerced the recording extractors with `spikeextractors_backend=True` to BaseRecording objects for Axona, Blackrock, Openephys, and SpikeGadgets. [PR #38](https://github.com/catalystneuro/neuroconv/pull/38)
* Added function to add PlaneSegmentation objects to an nwbfile in `roiextractors` and corresponding unit tests. [PR #23](https://github.com/catalystneuro/neuroconv/pull/23)
* `use_times` argument to be deprecated on the ecephys pipeline. The function `add_electrical_series` now determines whether the timestamps of the spikeinterface recording extractor are uniform or not and automatically stores the data according to best practices [PR #40](https://github.com/catalystneuro/neuroconv/pull/40)
* Add `NWBFile` metadata key at the level of the base data interface so it can always be inherited to be available. [PR #51](https://github.com/catalystneuro/neuroconv/pull/51).
* Added spikeinterface support to Axona LFP and coerece gin tests for LFP to be spikeinterface objects [PR #85](https://github.com/catalystneuro/neuroconv/pull/85)
* Added function to add fluorescence traces to an nwbfile in `roiextractors` and corresponding unit tests.
  The df over f traces are now added to a `DfOverF` container instead of the `Fluorescence` container.
  The metadata schema has been changed for the `BaseSegmentationExtractorInterface` to allow metadata for `DfOverF`,
  and `Flurorescence` is now not required in the metadata schema. [PR #41](https://github.com/catalystneuro/neuroconv/pull/41)
* Improved default values of OpticalChannel object names and other descriptions for Imaging data. [PR #88](https://github.com/catalystneuro/neuroconv/pull/88)
* Extended the `ImagingDataChunkIterator` to be  compatible with volumetric data. [PR #90](https://github.com/catalystneuro/neuroconv/pull/90)
* Integrated the `ImagingDataChunkIterator` with the `write_imaging` methods. [PR #90](https://github.com/catalystneuro/neuroconv/pull/90)
* Began work towards making SpikeInterface, SpikeExtractors, and ROIExtractors all non-minimal dependencies. [PR #74](https://github.com/catalystneuro/neuroconv/pull/74)
* Implemented format-wise and modality-wise extra installation requirements. If there are any requirements to use a module or data interface, these are defined in individual requirements files at the corresponding level of the package. These are in turn easily accessible from the commands `pip install neuroconv[format_name]`. `pip install neuroconv[modality_name]` will also install all dependencies necessary to make full use of any interfaces from that modality. [PR #100](https://github.com/catalystneuro/neuroconv/pull/100)
* Added frame stubbing to the `BaseSegmentationExtractorInterface`. [PR #116](https://github.com/catalystneuro/neuroconv/pull/116)
* Added `mask_type: str` and `include_roi_centroids: bool` to the `add_plane_segmentation` helper and `write_segmentation` functions for the `tools.roiextractors` submodule. [PR #117](https://github.com/catalystneuro/neuroconv/pull/117)
* Propagate `output_struct_name` argument to `ExtractSegmentationInterface` to match its extractor arguments. [PR #128](https://github.com/catalystneuro/neuroconv/pull/128)
* Added compression and iteration (with options control) to all Fluorescence traces in `write_segmentation`. [PR #120](https://github.com/catalystneuro/neuroconv/pull/120)
* For irregular recordings, timestamps can now be saved along with all traces in `write_segmentation`. [PR #130](https://github.com/catalystneuro/neuroconv/pull/130)
* Added `mask_type` argument to `tools.roiextractors.add_plane_segmentation` function and all upstream calls. This allows users to request writing not just the image_masks (still the default) but also pixels, voxels or `None` of the above. [PR #119](https://github.com/catalystneuro/neuroconv/pull/119)
* `utils.json_schema.get_schema_from_method_signature` now allows `Optional[...]` annotation typing and subsequent `None` values during validation as long as it is still only applied to a simple non-conflicting type (no `Optional[Union[..., ...]]`). [PR #119](https://github.com/catalystneuro/neuroconv/pull/119)


### Documentation and tutorial enhancements:
* Unified the documentation of NeuroConv structure in the User Guide readthedocs. [PR #39](https://github.com/catalystneuro/neuroconv/pull/39)
* Added package for viewing source code in the neuroconv documentation [PR #62](https://github.com/catalystneuro/neuroconv/pull/62)
* Added Contributing guide for the Developer section of readthedocs. [PR #73](https://github.com/catalystneuro/neuroconv/pull/73)
* Added style guide to the readthedocs [PR #28](https://github.com/catalystneuro/neuroconv/pull/28)
* Added ABF data conversion tutorial @luiztauffer [PR #89](https://github.com/catalystneuro/neuroconv/pull/89)
* Added Icephys API documentation @luiztauffer [PR #103](https://github.com/catalystneuro/neuroconv/pull/103)
* Added Blackrock sorting conversion gallery example [PR #134](https://github.com/catalystneuro/neuroconv/pull/134)
* Extended the User Guide Get metadata section in DataInterfaces with a demonstration for loading metadata from YAML. [PR #144](https://github.com/catalystneuro/neuroconv/pull/144)
* Fixed a redundancy in [PR #144](https://github.com/catalystneuro/neuroconv/pull/144) and API links. [PR #154](https://github.com/catalystneuro/neuroconv/pull/154)
* Added SLEAP conversion gallery example [PR #161](https://github.com/catalystneuro/neuroconv/pull/161)



### Features
* Added conversion interface for Neuralynx sorting data together with gin data test and a conversion example in the gallery. [PR #58](https://github.com/catalystneuro/neuroconv/pull/58)
* Added conversion interface for DeepLabCut data together with gin data test and a conversion example in the gallery. [PR #24](https://github.com/catalystneuro/neuroconv/pull/24)
* Allow writing of offsets to ElectricalSeries objects from SpikeInterface (requires PyNWB>=2.1.0). [PR #37](https://github.com/catalystneuro/neuroconv/pull/37)
* Added conversion interface for EDF (European Data Format) data together with corresponding unit tests and a conversion example in the gallery. [PR #45](https://github.com/catalystneuro/neuroconv/pull/45)
* Created ImagingExtractorDataChunkIterator, a data chunk iterator for `ImagingExtractor` objects. [PR #54](https://github.com/catalystneuro/neuroconv/pull/54)
* Added support for writing spikeinterface recording extractor with multiple segments and corresponding unit test [PR #67](https://github.com/catalystneuro/neuroconv/pull/67)
* Added spikeinterface support to the Axona data interface [PR #61](https://github.com/catalystneuro/neuroconv/pull/61)
* Added new util function `get_package` for safely attempting to attempt a package import and informatively notifying the user of how to perform the installation otherwise. [PR #74](https://github.com/catalystneuro/neuroconv/pull/74)
* All built-in DataInterfaces now load their external dependencies on-demand at time of object initialization instead of on package or interface import. [PR #74](https://github.com/catalystneuro/neuroconv/pull/74)
* Adde spikeinterface support for Blackrock sorting interface[PR #134](https://github.com/catalystneuro/neuroconv/pull/134)
* Added conversion interface for TDT recording data together with gin data test. [PR #135](https://github.com/catalystneuro/neuroconv/pull/135)
* Added conversion interface for SLEAP pose estimation data together with gin test for data. [PR #160](https://github.com/catalystneuro/neuroconv/pull/160)


### Testing
* Added unittests for correctly writing the scaling factors to the nwbfile in the `add_electrical_series` function of the spikeinterface module. [PR #37](https://github.com/catalystneuro/neuroconv/pull/37)
* Added unittest for compression options in the `add_electrical_series` function of the spikeinterface module. [PR #64](https://github.com/catalystneuro/neuroconv/pull/37)
* Added unittests for chunking in the `add_electrical_series` function of the spikeinterface module. [PR #84](https://github.com/catalystneuro/neuroconv/pull/84)
* Tests are now organized according to modality-wise lazy installations. [PR #100](https://github.com/catalystneuro/neuroconv/pull/100)

# v0.1.1
### Fixes
* Fixed the behavior of the `file_paths` usage in the MovieInterface when run via the YAML conversion specification. [PR #33](https://github.com/catalystneuro/neuroconv/pull/33)

### Improvements
* Added function to add ImagingPlane objects to an nwbfile in `roiextractors` and corresponding unit tests. [PR #19](https://github.com/catalystneuro/neuroconv/pull/19)
* Added function to add summary images from a `SegmentationExtractor` object to an nwbfile in the roiextractors module and corresponding unit tests [PR #22](https://github.com/catalystneuro/neuroconv/pull/22)
* Small improvements on ABFInterface @luiztauffer [PR #89](https://github.com/catalystneuro/neuroconv/pull/89)

### Features
* Add non-iterative writing capabilities to `add_electrical_series`. [PR #32](https://github.com/catalystneuro/neuroconv/pull/32)

### Testing
* Added unittests for the `write_as` functionality in the `add_electrical_series` of the spikeinterface module. [PR #32](https://github.com/catalystneuro/neuroconv/pull/32)


# v0.1.0

* The first release of NeuroConv.
