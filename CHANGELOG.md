# Upcoming

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


### Documentation and tutorial enhancements:
* Unified the documentation of NeuroConv structure in the User Guide readthedocs. [PR #39](https://github.com/catalystneuro/neuroconv/pull/39)
* Added package for viewing source code in the neuroconv documentation [PR #62](https://github.com/catalystneuro/neuroconv/pull/62)
* Added Contributing guide for the Developer section of readthedocs. [PR #73](https://github.com/catalystneuro/neuroconv/pull/73)
* Added style guide to the readthedocs [PR #28](https://github.com/catalystneuro/neuroconv/pull/28)
* Added ABF data conversion tutorial @luiztauffer [PR #89](https://github.com/catalystneuro/neuroconv/pull/89)
* Added Icephys API documentation @luiztauffer [PR #103](https://github.com/catalystneuro/neuroconv/pull/103)
* Added Blackrock sorting conversion gallery example [PR #134](https://github.com/catalystneuro/neuroconv/pull/134)
* Extended the User Guide Get metadata section in DataInterfaces with a demonstration for loading metadata from YAML. [PR #144](https://github.com/catalystneuro/neuroconv/pull/144)

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


### Testing
* Added unittests for correctly writing the scaling factors to the nwbfile in the `add_electrical_series` function of the spikeinterface module. [PR #37](https://github.com/catalystneuro/neuroconv/pull/37)
* Added unittest for compresion options in the `add_electrical_series` function of the spikeinterface module. [PR #64](https://github.com/catalystneuro/neuroconv/pull/37)
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
