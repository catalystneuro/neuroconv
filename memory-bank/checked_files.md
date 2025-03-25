### Checked Files

1. ./src/neuroconv/tools/roiextractors/roiextractors.py
   - _get_default_ophys_metadata(): Added Returns section
   - _get_default_segmentation_metadata(): Added Returns section
   - get_nwb_imaging_metadata(): Added Returns section
   - get_nwb_segmentation_metadata(): Added Returns section and improved parameter description

2. ./src/neuroconv/tools/neo/neo.py
   - get_number_of_electrodes(): Added Returns section and improved docstring with Parameters section
   - get_number_of_segments(): Added Returns section and improved docstring with Parameters section
   - get_command_traces(): Added Returns section and improved parameter descriptions
   - get_nwb_metadata(): Added Returns section and improved parameter description

3. ./src/neuroconv/tools/importing.py
   - get_format_summaries(): Added Returns section with detailed description of return value

4. ./src/neuroconv/tools/data_transfers/_globus.py
   - get_globus_dataset_content_sizes(): Added Returns section and improved docstring with Parameters section

5. ./src/neuroconv/tools/testing/mock_interfaces.py
   - MockInterface.get_metadata(): Added docstring with Returns section
   - MockRecordingInterface.get_metadata(): Improved docstring with Returns section
   - MockSortingInterface.get_metadata(): Added docstring with Returns section
   - MockImagingInterface.get_metadata(): Added docstring with Returns section
   - MockSegmentationInterface.get_metadata(): Added docstring with Returns section

6. ./src/neuroconv/tools/nwb_helpers/_backend_configuration.py
   - get_default_backend_configuration(): Added Returns section and improved docstring with Parameters section

7. ./src/neuroconv/tools/nwb_helpers/_configuration_models/_zarr_dataset_io.py
   - ZarrDatasetIOConfiguration.get_data_io_kwargs(): Added docstring with Returns section

8. ./src/neuroconv/tools/nwb_helpers/_configuration_models/_base_dataset_io.py
   - _recursively_find_location_in_memory_nwbfile(): Added Returns section and improved docstring with Parameters section
   - _find_location_in_memory_nwbfile(): Added Returns section and improved docstring with Parameters section
   - _infer_dtype_of_list(): Added Returns section and improved docstring with Parameters section
   - _infer_dtype(): Added Returns section and improved docstring with Parameters section
   - DatasetIOConfiguration.get_data_io_kwargs(): Added Returns section to abstract method docstring
   - DatasetIOConfiguration.from_neurodata_object(): Added Returns section and Raises section

9. ./src/neuroconv/tools/nwb_helpers/_configuration_models/_hdf5_dataset_io.py
   - HDF5DatasetIOConfiguration.get_data_io_kwargs(): Added docstring with Returns section

10. ./src/neuroconv/tools/nwb_helpers/_configuration_models/_hdf5_backend.py
    - No getter functions found that need Returns sections added

11. ./src/neuroconv/tools/nwb_helpers/_configuration_models/_zarr_backend.py
    - No getter functions found that need Returns sections added

12. ./src/neuroconv/tools/nwb_helpers/_configuration_models/_base_backend.py
    - BackendConfiguration.from_nwbfile(): Added docstring with Parameters and Returns sections

13. ./src/neuroconv/tools/nwb_helpers/_dataset_configuration.py
    - _get_io_mode(): Added docstring with Parameters and Returns sections
    - _is_dataset_written_to_file(): Added docstring with Parameters and Returns sections
    - get_default_dataset_io_configurations(): Already has appropriate Yields section instead of Returns section

14. ./src/neuroconv/tools/nwb_helpers/_metadata_and_file_helpers.py
    - get_module(): Added docstring with Parameters and Returns sections
    - get_default_nwbfile_metadata(): Added Returns section
    - make_nwbfile_from_metadata(): Added docstring with Parameters, Returns, and Raises sections
    - _resolve_backend(): Already has appropriate Returns section

15. ./src/neuroconv/tools/signal_processing.py
    - get_rising_frames_from_ttl(): Already has appropriate Returns section
    - get_falling_frames_from_ttl(): Already has appropriate Returns section

16. ./src/neuroconv/basetemporalalignmentinterface.py
    - get_original_timestamps(): Already has appropriate Returns section
    - get_timestamps(): Already has appropriate Returns section

17. ./src/neuroconv/baseextractorinterface.py
    - get_extractor(): Added docstring with Returns section
    - _source_data_to_extractor_kwargs(): Added docstring with Parameters and Returns sections

18. ./src/neuroconv/utils/json_schema.py
    - get_base_schema(): Added docstring with Parameters and Returns sections
    - get_schema_from_hdmf_class(): Added docstring with Parameters and Returns sections
    - get_metadata_schema_for_icephys(): Improved docstring with NumPy-style Returns section

19. ./src/neuroconv/basedatainterface.py
    - get_source_schema(): Already has appropriate Returns section
    - get_metadata_schema(): Added docstring with Returns section
    - get_metadata(): Added docstring with Returns section
    - get_conversion_options_schema(): Added docstring with Returns section
    - get_default_backend_configuration(): Already has appropriate Returns section

20. ./src/neuroconv/datainterfaces/behavior/video/videodatainterface.py
    - get_metadata_schema(): Added docstring with Returns section
    - get_metadata(): Added docstring with Returns section
    - get_original_timestamps(): Already has appropriate Returns section
    - get_timing_type(): Already has appropriate Returns section
    - get_timestamps(): Already has appropriate Returns section

21. ./src/neuroconv/datainterfaces/behavior/video/video_utils.py
    - get_video_timestamps(): Already has appropriate Returns section
    - VideoCaptureContext.get_video_timestamps(): Added docstring with Parameters and Returns sections
    - VideoCaptureContext.get_video_fps(): Added docstring with Returns section
    - VideoCaptureContext.get_frame_shape(): Added docstring with Returns section
    - VideoCaptureContext.get_video_frame_count(): Added docstring with Returns section
    - VideoCaptureContext.get_cv_attribute(): Added docstring with Parameters and Returns sections
    - VideoCaptureContext.get_video_frame(): Added docstring with Parameters and Returns sections
    - VideoCaptureContext.get_video_frame_dtype(): Added docstring with Returns section

22. ./src/neuroconv/datainterfaces/behavior/audio/audiointerface.py
    - get_metadata_schema(): Added docstring with Returns section
    - get_metadata(): Added docstring with Returns section
    - get_original_timestamps(): Added docstring with Returns and Raises sections
    - get_timestamps(): Added docstring with Returns and Raises sections
    - set_aligned_timestamps(): Added docstring with Parameters and Raises sections
    - align_by_interpolation(): Added docstring with Parameters and Raises sections

23. ./src/neuroconv/datainterfaces/behavior/sleap/sleapdatainterface.py
    - get_source_schema(): Added docstring with Returns section
    - get_original_timestamps(): Added docstring with Returns and Raises sections
    - get_timestamps(): Added docstring with Returns section
    - set_aligned_timestamps(): Added docstring with Parameters section

24. ./src/neuroconv/datainterfaces/behavior/fictrac/fictracdatainterface.py
    - get_source_schema(): Added docstring with Returns section
    - get_metadata(): Added docstring with Returns section
    - get_timestamps(): Added docstring with Returns section
    - set_aligned_timestamps(): Added docstring with Parameters section
    - set_aligned_starting_time(): Added docstring with Parameters section

25. ./src/neuroconv/datainterfaces/behavior/deeplabcut/deeplabcutdatainterface.py
    - get_source_schema(): Added docstring with Returns section
    - get_metadata(): Added docstring with Returns section
    - get_original_timestamps(): Added docstring with Returns and Raises sections
    - get_timestamps(): Added docstring with Returns and Raises sections

26. ./src/neuroconv/datainterfaces/behavior/lightningpose/lightningposeconverter.py
    - get_source_schema(): Added docstring with Returns section
    - get_conversion_options_schema(): Added docstring with Returns section
    - get_metadata(): Added docstring with Returns section

27. ./src/neuroconv/datainterfaces/behavior/lightningpose/lightningposedatainterface.py
    - get_metadata_schema(): Added docstring with Returns section
    - get_original_timestamps(): Added docstring with Parameters and Returns sections
    - get_timestamps(): Added docstring with Parameters and Returns sections
    - set_aligned_timestamps(): Added docstring with Parameters section
    - get_metadata(): Added docstring with Returns section

28. ./src/neuroconv/datainterfaces/behavior/medpc/medpcdatainterface.py
    - get_metadata(): Added docstring with Returns section
    - get_metadata_schema(): Added docstring with Returns section
    - get_original_timestamps(): Already has appropriate Returns section
    - get_timestamps(): Already has appropriate Returns section

29. ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxnidqinterface.py
    - get_source_schema(): Added docstring with Returns section
    - get_metadata(): Added docstring with Returns section
    - get_channel_names(): Improved docstring with Returns section
    - get_event_times_from_ttl(): Already has appropriate Returns section

30. ./src/neuroconv/datainterfaces/behavior/miniscope/miniscopedatainterface.py
    - get_source_schema(): Added docstring with Returns section
    - get_metadata(): Added docstring with Returns section

31. ./src/neuroconv/datainterfaces/behavior/medpc/medpc_helpers.py
    - get_medpc_variables(): Already has appropriate Returns section
    - _get_session_lines(): Already has appropriate Returns section
    - read_medpc_file(): Already has appropriate Returns section

32. ./src/neuroconv/datainterfaces/behavior/neuralynx/neuralynx_nvt_interface.py
    - get_original_timestamps(): Added docstring with Returns section
    - get_timestamps(): Added docstring with Returns section
    - set_aligned_timestamps(): Added docstring with Parameters section
    - get_metadata(): Added docstring with Returns section
    - get_metadata_schema(): Added docstring with Returns section

33. ./src/neuroconv/datainterfaces/ophys/caiman/caimandatainterface.py
    - get_source_schema(): Improved docstring with Returns section

34. ./src/neuroconv/datainterfaces/ophys/micromanagertiff/micromanagertiffdatainterface.py
    - get_source_schema(): Improved docstring with Returns section
    - get_metadata(): Improved docstring with Returns section

35. ./src/neuroconv/datainterfaces/ophys/baseimagingextractorinterface.py
    - get_metadata_schema(): Added Returns section
    - get_metadata(): Added Returns section
    - get_original_timestamps(): Added docstring with Returns section
    - get_timestamps(): Added docstring with Returns section
    - set_aligned_timestamps(): Added docstring with Parameters section

36. ./src/neuroconv/datainterfaces/ophys/sbx/sbxdatainterface.py
    - get_metadata(): Improved docstring with Returns section

37. ./src/neuroconv/datainterfaces/ophys/tdt_fp/tdtfiberphotometrydatainterface.py
    - get_metadata(): Improved docstring with Returns section
    - get_metadata_schema(): Improved docstring with Returns section
    - get_original_timestamps(): Already has appropriate Returns section
    - get_timestamps(): Already has appropriate Returns section
    - get_original_starting_time_and_rate(): Already has appropriate Returns section
    - get_starting_time_and_rate(): Already has appropriate Returns section
    - get_events(): Already has appropriate Returns section

38. ./src/neuroconv/datainterfaces/ophys/tiff/tiffdatainterface.py
    - get_source_schema(): Improved docstring with Returns section and fixed typo

39. ./src/neuroconv/datainterfaces/ophys/scanimage/scanimageimaginginterfaces.py
    - ScanImageImagingInterface.get_source_schema(): Improved docstring with Returns section
    - ScanImageLegacyImagingInterface.get_source_schema(): Improved docstring with Returns section
    - ScanImageLegacyImagingInterface.get_metadata(): Improved docstring with Returns section
    - ScanImageMultiFileImagingInterface.get_source_schema(): Improved docstring with Returns section
    - ScanImageMultiPlaneImagingInterface.get_metadata(): Improved docstring with Returns section
    - ScanImageMultiPlaneMultiFileImagingInterface.get_metadata(): Improved docstring with Returns section
    - ScanImageSinglePlaneImagingInterface.get_metadata(): Improved docstring with Returns section
    - ScanImageSinglePlaneMultiFileImagingInterface.get_metadata(): Improved docstring with Returns section
    - get_scanimage_major_version(): Already has appropriate Returns section

40. ./src/neuroconv/datainterfaces/ophys/basesegmentationextractorinterface.py
    - get_metadata_schema(): Already has appropriate Returns section
    - get_metadata(): Added docstring with Returns section
    - get_original_timestamps(): Added docstring with Returns section
    - get_timestamps(): Added docstring with Returns section
    - set_aligned_timestamps(): Added docstring with Parameters section

41. ./src/neuroconv/datainterfaces/ophys/miniscope/miniscopeconverter.py
    - get_source_schema(): Added docstring with Returns section
    - get_conversion_options_schema(): Improved docstring with Returns section

42. ./src/neuroconv/datainterfaces/ophys/miniscope/miniscopeimagingdatainterface.py
    - get_source_schema(): Improved docstring with Returns section
    - get_metadata(): Improved docstring with Returns section
    - get_metadata_schema(): Improved docstring with Returns section
    - get_original_timestamps(): Added docstring with Returns section

43. ./src/neuroconv/datainterfaces/ophys/cnmfe/cnmfedatainterface.py
    - No getter functions found that need Returns sections added

44. ./src/neuroconv/datainterfaces/ophys/suite2p/suite2pdatainterface.py
    - get_source_schema(): Improved docstring with Returns section
    - get_available_planes(): Added docstring with Parameters and Returns sections
    - get_available_channels(): Added docstring with Parameters and Returns sections
    - get_metadata(): Improved docstring with Returns section

45. ./src/neuroconv/datainterfaces/ophys/brukertiff/brukertiffconverter.py
    - BrukerTiffMultiPlaneConverter.get_source_schema(): Improved docstring with Returns section
    - BrukerTiffMultiPlaneConverter.get_conversion_options_schema(): Improved docstring with Returns section
    - BrukerTiffSinglePlaneConverter.get_source_schema(): Added docstring with Returns section
    - BrukerTiffSinglePlaneConverter.get_conversion_options_schema(): Improved docstring with Returns section

46. ./src/neuroconv/datainterfaces/ophys/brukertiff/brukertiffdatainterface.py
    - BrukerTiffMultiPlaneImagingInterface.get_source_schema(): Improved docstring with Returns section
    - BrukerTiffMultiPlaneImagingInterface._determine_position_current(): Improved docstring with Returns section
    - BrukerTiffMultiPlaneImagingInterface.get_metadata(): Improved docstring with Returns section
    - BrukerTiffSinglePlaneImagingInterface.get_source_schema(): Improved docstring with Returns section
    - BrukerTiffSinglePlaneImagingInterface._determine_position_current(): Improved docstring with Returns section
    - BrukerTiffSinglePlaneImagingInterface.get_metadata(): Improved docstring with Returns section

47. ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglx_utils.py
    - get_session_start_time(): Already has appropriate Parameters and Returns sections
    - fetch_stream_id_for_spikelgx_file(): Already has appropriate Parameters and Returns sections
    - get_device_metadata(): Improved docstring with Parameters section and enhanced Returns section

48. ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxconverter.py
    - get_source_schema(): Added docstring with Returns section
    - get_streams(): Improved docstring with Parameters and Returns sections
    - get_conversion_options_schema(): Added docstring with Returns section

49. ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxdatainterface.py
    - get_source_schema(): Added docstring with Returns section
    - _source_data_to_extractor_kwargs(): Added docstring with Parameters and Returns sections
    - get_metadata(): Added docstring with Returns section
    - get_original_timestamps(): Added docstring with Returns section

50. ./src/neuroconv/datainterfaces/ecephys/baserecordingextractorinterface.py
    - get_metadata_schema(): Improved docstring with Returns section
    - get_metadata(): Added docstring with Returns section
    - get_original_timestamps(): Already has appropriate Returns section
    - get_timestamps(): Already has appropriate Returns section
    - has_probe(): Already has appropriate Returns section

51. ./src/neuroconv/datainterfaces/ecephys/basesortingextractorinterface.py
    - get_metadata_schema(): Improved docstring with Returns section
    - get_original_timestamps(): Already has appropriate Returns section
    - get_timestamps(): Already has appropriate Returns section
    - subset_sorting(): Already has appropriate Returns section

52. ./src/neuroconv/datainterfaces/text/timeintervalsinterface.py
    - get_metadata(): Added docstring with Returns section
    - get_metadata_schema(): Already has appropriate Returns section
    - get_original_timestamps(): Already has appropriate Returns section
    - get_timestamps(): Already has appropriate Returns section

53. ./src/neuroconv/datainterfaces/ecephys/openephys/openephysbinarydatainterface.py
    - get_stream_names(): Added docstring with Parameters and Returns sections
    - get_source_schema(): Improved docstring with Returns section
    - get_metadata(): Added docstring with Returns section

54. ./src/neuroconv/datainterfaces/ecephys/openephys/openephyslegacydatainterface.py
    - get_stream_names(): Added docstring with Parameters and Returns sections
    - get_source_schema(): Improved docstring with Returns section
    - get_metadata(): Added docstring with Returns section

55. ./src/neuroconv/datainterfaces/ecephys/openephys/openephyssortingdatainterface.py
    - get_source_schema(): Improved docstring with Returns section

56. ./src/neuroconv/datainterfaces/ecephys/edf/edfdatainterface.py
    - get_source_schema(): Improved docstring with Returns section
    - _source_data_to_extractor_kwargs(): Added docstring with Parameters and Returns sections
    - extract_nwb_file_metadata(): Added docstring with Returns section
    - extract_subject_metadata(): Added docstring with Returns section
    - get_metadata(): Added docstring with Returns section

57. ./src/neuroconv/datainterfaces/ecephys/plexon/plexondatainterface.py
    - PlexonRecordingInterface.get_source_schema(): Improved docstring with Returns section
    - PlexonRecordingInterface.get_metadata(): Added docstring with Returns section
    - Plexon2RecordingInterface.get_source_schema(): Improved docstring with Returns section
    - Plexon2RecordingInterface._source_data_to_extractor_kwargs(): Added docstring with Parameters and Returns sections
    - Plexon2RecordingInterface.get_metadata(): Added docstring with Returns section
    - PlexonSortingInterface.get_source_schema(): Improved docstring with Returns section
    - PlexonSortingInterface.get_metadata(): Added docstring with Returns section

58. ./src/neuroconv/datainterfaces/ecephys/spikegadgets/spikegadgetsdatainterface.py
    - get_source_schema(): Improved docstring with Returns section

59. ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscopedatainterface.py
    - NeuroScopeRecordingInterface.get_source_schema(): Improved docstring with Returns section
    - NeuroScopeRecordingInterface.get_ecephys_metadata(): Added docstring with Parameters and Returns sections
    - NeuroScopeRecordingInterface.get_metadata(): Added docstring with Returns section
    - NeuroScopeRecordingInterface.get_original_timestamps(): Added docstring with Returns section
    - NeuroScopeLFPInterface.get_source_schema(): Improved docstring with Returns section
    - NeuroScopeLFPInterface.get_metadata(): Added docstring with Returns section
    - NeuroScopeSortingInterface.get_source_schema(): Improved docstring with Returns section
    - NeuroScopeSortingInterface.get_metadata(): Added docstring with Returns section

60. ./src/neuroconv/datainterfaces/ecephys/neuralynx/neuralynxdatainterface.py
    - NeuralynxRecordingInterface.get_stream_names(): Added docstring with Parameters and Returns sections
    - NeuralynxRecordingInterface.get_source_schema(): Improved docstring with Returns section
    - NeuralynxRecordingInterface._source_data_to_extractor_kwargs(): Added docstring with Parameters and Returns sections
    - NeuralynxRecordingInterface.get_metadata(): Added docstring with Returns section
    - extract_neo_header_metadata(): Already has appropriate Parameters and Returns sections

61. ./src/neuroconv/datainterfaces/ecephys/axona/axonadatainterface.py
    - AxonaRecordingInterface.get_source_schema(): Added docstring with Returns section
    - AxonaRecordingInterface._source_data_to_extractor_kwargs(): Added docstring with Parameters and Returns sections
    - AxonaRecordingInterface.extract_nwb_file_metadata(): Added docstring with Returns section
    - AxonaRecordingInterface.extract_ecephys_metadata(): Added docstring with Returns section
    - AxonaRecordingInterface.get_metadata(): Added docstring with Returns section
    - AxonaUnitRecordingInterface.get_source_schema(): Added docstring with Returns section
    - AxonaLFPDataInterface.get_source_schema(): Added docstring with Returns section
    - AxonaLFPDataInterface._source_data_to_extractor_kwargs(): Added docstring with Parameters and Returns sections
    - AxonaPositionDataInterface.get_source_schema(): Added docstring with Returns section

62. ./src/neuroconv/datainterfaces/ecephys/kilosort/kilosortdatainterface.py
    - KiloSortSortingInterface.get_source_schema(): Added docstring with Returns section
    - KiloSortSortingInterface.get_metadata(): Added docstring with Returns section

63. ./src/neuroconv/datainterfaces/ecephys/phy/phydatainterface.py
    - PhySortingInterface.get_source_schema(): Added docstring with Returns section
    - PhySortingInterface.get_metadata(): Added docstring with Returns section

64. ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscope_utils.py
    - get_xml_file_path(): Added docstring with Parameters and Returns sections
    - get_xml(): Added docstring with Parameters and Returns sections
    - safe_find(): Added docstring with Parameters and Returns sections
    - safe_nested_find(): Added docstring with Parameters and Returns sections
    - get_neural_channels(): Already has appropriate Parameters and Returns sections
    - get_channel_groups(): Improved docstring with Parameters and Returns sections
    - get_session_start_time(): Improved docstring with Parameters and Returns sections

65. ./src/neuroconv/datainterfaces/ecephys/alphaomega/alphaomegadatainterface.py
    - AlphaOmegaRecordingInterface.get_source_schema(): Added docstring with Returns section
    - AlphaOmegaRecordingInterface._source_data_to_extractor_kwargs(): Added docstring with Parameters and Returns sections
    - AlphaOmegaRecordingInterface.get_metadata(): Added docstring with Returns section

66. ./src/neuroconv/datainterfaces/ecephys/blackrock/blackrockdatainterface.py
    - BlackrockRecordingInterface.get_source_schema(): Added docstring with Returns section
    - BlackrockRecordingInterface._source_data_to_extractor_kwargs(): Added docstring with Parameters and Returns sections
    - BlackrockRecordingInterface.get_metadata(): Added docstring with Returns section
    - BlackrockSortingInterface.get_source_schema(): Added docstring with Returns section
    - BlackrockSortingInterface.get_metadata(): Added docstring with Returns section

67. ./src/neuroconv/datainterfaces/ecephys/blackrock/header_tools.py
    - _parse_nsx_basic_header(): Added docstring with Parameters and Returns sections
    - _parse_nev_basic_header(): Added docstring with Parameters and Returns sections

68. ./src/neuroconv/datainterfaces/ecephys/biocam/biocamdatainterface.py
    - BiocamRecordingInterface.get_source_schema(): Added docstring with Returns section

69. ./src/neuroconv/datainterfaces/ecephys/cellexplorer/cellexplorerdatainterface.py
    - CellExplorerRecordingInterface.get_source_schema(): Added docstring with Returns section
    - CellExplorerRecordingInterface.get_original_timestamps(): Added docstring with Returns section
    - CellExplorerSortingInterface._source_data_to_extractor_kwargs(): Added docstring with Parameters and Returns sections
    - CellExplorerSortingInterface.get_metadata(): Added docstring with Returns section

70. ./src/neuroconv/datainterfaces/ecephys/maxwell/maxonedatainterface.py
    - MaxOneRecordingInterface.get_metadata(): Added docstring with Returns section

71. ./src/neuroconv/datainterfaces/ecephys/intan/intandatainterface.py
    - IntanRecordingInterface.get_source_schema(): Added docstring with Returns section
    - IntanRecordingInterface._source_data_to_extractor_kwargs(): Added docstring with Parameters and Returns sections
    - IntanRecordingInterface.get_metadata_schema(): Added docstring with Returns section
    - IntanRecordingInterface.get_metadata(): Added docstring with Returns section

72. ./src/neuroconv/datainterfaces/ecephys/spike2/spike2datainterface.py
    - Spike2RecordingInterface.get_source_schema(): Added docstring with Returns section
    - Spike2RecordingInterface.get_all_channels_info(): Added docstring with Parameters and Returns sections

73. ./src/neuroconv/datainterfaces/ecephys/mcsraw/mcsrawdatainterface.py
    - MCSRawRecordingInterface.get_source_schema(): Added docstring with Returns section

74. ./src/neuroconv/datainterfaces/ecephys/mearec/mearecdatainterface.py
    - MEArecRecordingInterface.get_source_schema(): Added docstring with Returns section
    - MEArecRecordingInterface.get_metadata(): Added docstring with Returns section

75. ./src/neuroconv/datainterfaces/icephys/baseicephysinterface.py
    - BaseIcephysInterface.get_source_schema(): Added docstring with Returns section
    - BaseIcephysInterface.get_metadata_schema(): Added docstring with Returns section
    - BaseIcephysInterface.get_metadata(): Added docstring with Returns section
    - BaseIcephysInterface.get_original_timestamps(): Added docstring with Returns and Raises sections
    - BaseIcephysInterface.get_timestamps(): Added docstring with Returns and Raises sections

76. ./src/neuroconv/datainterfaces/icephys/abf/abfdatainterface.py
    - AbfInterface.get_source_schema(): Added docstring with Returns section
    - AbfInterface.get_metadata(): Added docstring with Returns section

77. ./src/neuroconv/nwbconverter.py
    - NWBConverter.get_source_schema(): Added docstring with Returns section
    - NWBConverter.get_metadata_schema(): Added docstring with Returns section
    - NWBConverter.get_metadata(): Added docstring with Returns section
    - NWBConverter.get_conversion_options_schema(): Added docstring with Returns section
    - ConverterPipe.get_conversion_options_schema(): Added docstring with Returns section
