# Upcoming

### Improvements

* Upgraded Pydantic support to `>v2.0.0`. [PR #767](https://github.com/catalystneuro/neuroconv/pull/767)
* Absorbed the `DatasetInfo` model into the `DatasetIOConfiguration` model. [PR #767](https://github.com/catalystneuro/neuroconv/pull/767)
* Keyword argument `field_name` of the `DatasetIOConfiguration.from_neurodata_object` method has been renamed to `dataset_name` to be more consistent with its usage. This only affects direct initialization of the model; usage via the `BackendConfiguration` constructor and its associated helper functions in `neuroconv.tools.nwb_helpers` is unaffected. [PR #767](https://github.com/catalystneuro/neuroconv/pull/767)
* Manual construction of a `DatasetIOConfiguration` now requires the field `dataset_name`, and will be validated to match the final path of `location_in_file`. Usage via the automated constructors is unchanged. [PR #767](https://github.com/catalystneuro/neuroconv/pull/767)



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
