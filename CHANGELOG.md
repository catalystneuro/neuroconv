# Upcoming

### Fixes

### Improvements
* Unified the `run_conversion` method of `BaseSegmentationExtractorInterface` with that of all the other base interfaces. The method `write_segmentation` now uses the common `make_or_load_nwbfile` context manager [PR #29](https://github.com/catalystneuro/neuroconv/pull/29)

### Features

### Testing

# v0.1.1
### Fixes
* Fixed the behavior of the `file_paths` usage in the MovieInterface when run via the YAML conversion specification. [PR #33](https://github.com/catalystneuro/neuroconv/pull/33)

### Improvements
* Added function to add ImagingPlane objects to an nwbfile in `roiextractors` and corresponding unit tests. [PR #19](https://github.com/catalystneuro/neuroconv/pull/19)

### Features
* Add non-iterative writing capabilities to `add_electrical_series`. [PR #32](https://github.com/catalystneuro/neuroconv/pull/32)
* Added conversion interface for DeepLabCut data together with unit tests and a conversion example in the gallery [PR #24](https://github.com/catalystneuro/neuroconv/pull/24)
### Testing
* Added unittests for the `write_as` functionality in the `add_electrical_series` of the spikeinterface module. [PR #32](https://github.com/catalystneuro/neuroconv/pull/32)


# v0.1.0

* The first release of NeuroConv.
