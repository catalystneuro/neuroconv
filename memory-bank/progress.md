# Progress

## What Works
- Memory bank initialized with project context
- Clear understanding of task requirements:
  - Add Returns sections to getter function docstrings
  - Use NumPy style
  - Only modify existing docstrings
  - Preserve other content

## Current Status
Starting implementation phase:
- Have list of all getter functions in codebase
- Have example format for Returns section
- Ready to begin modifying docstrings

## Known Issues
None identified yet

## What's Left to Build
1. Examine each getter function's current docstring
2. Add Returns sections where missing
3. Ensure consistent NumPy style
4. Verify changes maintain existing content

## Next Actions
1. Start with first getter function
2. Read current docstring
3. Add Returns section if missing
4. Move to next function
5. Track progress through the list

## Progress Tracking
- Total getter functions identified: 253 (from search_files)
- Functions processed: 0
- Functions updated: 0
- Functions remaining: 253

### Checked Functions

### Remaining Functions to Check
1.  ./tests/test_ophys/test_tools_roiextractors.py: def get_roi_pixel_masks(self, roi_ids: Optional[ArrayLike] = None) -> List[np.ndarray]:

2.  ./tests/test_ophys/test_tools_roiextractors.py: def get_roi_pixel_masks(self, roi_ids: Optional[ArrayLike] = None) -> List[np.ndarray]:

3.  ./tests/test_ophys/test_tools_roiextractors.py: def get_roi_pixel_masks(self, roi_ids: Optional[ArrayLike] = None) -> List[np.ndarray]:

4.  ./tests/test_ophys/test_tools_roiextractors.py: def get_roi_pixel_masks(self, roi_ids: Optional[ArrayLike] = None) -> List[np.ndarray]:

5.  ./tests/test_minimal/test_tools/test_backend_and_dataset_configuration/test_models/test_dataset_io_configuration_model.py: def get_data_io_kwargs(self):

6.  ./tests/test_minimal/test_tools/test_backend_and_dataset_configuration/test_models/test_dataset_io_configuration_model.py:# def get_data_io_kwargs(self):

7.  ./tests/test_minimal/test_tools/test_backend_and_dataset_configuration/test_models/test_dataset_io_configuration_model.py: def get_data_io_kwargs(self):

8.  ./tests/test_minimal/test_converter.py: def get_original_timestamps(self) -> np.ndarray:

9.  ./tests/test_minimal/test_converter.py: def get_timestamps(self) -> np.ndarray:

10.  ./tests/test_minimal/test_converter.py: def get_original_timestamps(self):

11.  ./tests/test_minimal/test_converter.py: def get_timestamps(self):

12.  ./src/neuroconv/tools/roiextractors/roiextractors.py:def get_nwb_imaging_metadata(

13.  ./src/neuroconv/tools/roiextractors/roiextractors.py:def get_nwb_segmentation_metadata(sgmextractor: SegmentationExtractor) -> dict:

14.  ./src/neuroconv/tools/neo/neo.py:def get_electrodes_metadata(neo_reader, electrodes_ids: list, block: int = 0) -> list:

15.  ./src/neuroconv/tools/neo/neo.py:def get_number_of_electrodes(neo_reader) -> int:

16.  ./src/neuroconv/tools/neo/neo.py:def get_number_of_segments(neo_reader, block: int = 0) -> int:

17.  ./src/neuroconv/tools/neo/neo.py:def get_command_traces(neo_reader, segment: int = 0, cmd_channel: int = 0) -> tuple[list, str, str]:

18.  ./src/neuroconv/tools/neo/neo.py:def get_conversion_from_unit(unit: str) -> float:

19.  ./src/neuroconv/tools/neo/neo.py:def get_nwb_metadata(neo_reader, metadata: dict = None) -> dict:

20.  ./src/neuroconv/tools/importing.py:def get_package_version(name: str) -> version.Version:

21.  ./src/neuroconv/tools/importing.py:def get_package(

22.  ./src/neuroconv/tools/importing.py:def get_format_summaries() -> dict[str, dict[str, Union[str, tuple[str, ...], None]]]:

23.  ./src/neuroconv/tools/data_transfers/_globus.py:def get_globus_dataset_content_sizes(

24.  ./src/neuroconv/tools/testing/mock_interfaces.py: def get_metadata(self) -> dict:

25.  ./src/neuroconv/tools/testing/mock_interfaces.py: def get_source_schema(cls) -> dict:

26.  ./src/neuroconv/tools/testing/mock_interfaces.py: def get_original_timestamps(self) -> np.ndarray:

27.  ./src/neuroconv/tools/testing/mock_interfaces.py: def get_timestamps(self) -> np.ndarray:

28.  ./src/neuroconv/tools/testing/mock_interfaces.py: def get_source_schema(cls) -> dict:

29.  ./src/neuroconv/tools/testing/mock_interfaces.py: def get_metadata(self) -> dict:

30.  ./src/neuroconv/tools/testing/mock_interfaces.py: def get_metadata(self) -> dict:

31.  ./src/neuroconv/tools/testing/mock_interfaces.py: def get_metadata(self) -> dict:

32.  ./src/neuroconv/tools/testing/mock_interfaces.py: def get_metadata(self) -> dict:

33.  ./src/neuroconv/tools/nwb_helpers/_backend_configuration.py:def get_default_backend_configuration(

34.  ./src/neuroconv/tools/nwb_helpers/_configuration_models/_zarr_dataset_io.py: def get_data_io_kwargs(self) -> dict[str, Any]:

35.  ./src/neuroconv/tools/nwb_helpers/_configuration_models/_base_dataset_io.py: def get_data_io_kwargs(self) -> dict[str, Any]:

36.  ./src/neuroconv/tools/nwb_helpers/_configuration_models/_hdf5_dataset_io.py: def get_data_io_kwargs(self) -> dict[str, Any]:

37.  ./src/neuroconv/tools/nwb_helpers/_dataset_configuration.py:def get_default_dataset_io_configurations(

38.  ./src/neuroconv/tools/nwb_helpers/_metadata_and_file_helpers.py:def get_module(nwbfile: NWBFile, name: str, description: str = None):

39.  ./src/neuroconv/tools/nwb_helpers/_metadata_and_file_helpers.py:def get_default_nwbfile_metadata() -> DeepDict:

40.  ./src/neuroconv/tools/signal_processing.py:def get_rising_frames_from_ttl(trace: np.ndarray, threshold: Optional[float] = None) -> np.ndarray:

41.  ./src/neuroconv/tools/signal_processing.py:def get_falling_frames_from_ttl(trace: np.ndarray, threshold: Optional[float] = None) -> np.ndarray:

42.  ./src/neuroconv/basetemporalalignmentinterface.py: def get_original_timestamps(self) -> np.ndarray:

43.  ./src/neuroconv/basetemporalalignmentinterface.py: def get_timestamps(self) -> np.ndarray:

44.  ./src/neuroconv/baseextractorinterface.py: def get_extractor(cls):

45.  ./src/neuroconv/utils/json_schema.py:def get_base_schema(

46.  ./src/neuroconv/utils/json_schema.py:def get_schema_from_method_signature(method: Callable, exclude: Optional[list[str]] = None) -> dict:

47.  ./src/neuroconv/utils/json_schema.py:def get_json_schema_from_method_signature(method: Callable, exclude: Optional[list[str]] = None) -> dict:

48.  ./src/neuroconv/utils/json_schema.py:def get_schema_from_hdmf_class(hdmf_class):

49.  ./src/neuroconv/utils/json_schema.py:def get_metadata_schema_for_icephys() -> dict:

50.  ./src/neuroconv/basedatainterface.py: def get_source_schema(cls) -> dict:

51.  ./src/neuroconv/basedatainterface.py: def get_metadata_schema(self) -> dict:

52.  ./src/neuroconv/basedatainterface.py: def get_metadata(self) -> DeepDict:

53.  ./src/neuroconv/basedatainterface.py: def get_conversion_options_schema(self) -> dict:

54.  ./src/neuroconv/basedatainterface.py: def get_default_backend_configuration(

55.  ./src/neuroconv/datainterfaces/behavior/video/videodatainterface.py: def get_metadata_schema(self):

56.  ./src/neuroconv/datainterfaces/behavior/video/videodatainterface.py: def get_metadata(self):

57.  ./src/neuroconv/datainterfaces/behavior/video/videodatainterface.py: def get_original_timestamps(self, stub_test: bool = False) -> list[np.ndarray]:

58.  ./src/neuroconv/datainterfaces/behavior/video/videodatainterface.py: def get_timing_type(self) -> Literal["starting_time and rate", "timestamps"]:

59.  ./src/neuroconv/datainterfaces/behavior/video/videodatainterface.py: def get_timestamps(self, stub_test: bool = False) -> list[np.ndarray]:

60.  ./src/neuroconv/datainterfaces/behavior/video/video_utils.py:def get_video_timestamps(file_path: FilePath, max_frames: Optional[int] = None, display_progress: bool = True) -> list:

61.  ./src/neuroconv/datainterfaces/behavior/video/video_utils.py: def get_video_timestamps(self, max_frames: Optional[int] = None, display_progress: bool = True):

62.  ./src/neuroconv/datainterfaces/behavior/video/video_utils.py: def get_video_fps(self):

63.  ./src/neuroconv/datainterfaces/behavior/video/video_utils.py: def get_frame_shape(self) -> Tuple:

64.  ./src/neuroconv/datainterfaces/behavior/video/video_utils.py: def get_video_frame_count(self):

65.  ./src/neuroconv/datainterfaces/behavior/video/video_utils.py: def get_cv_attribute(attribute_name: str):

66.  ./src/neuroconv/datainterfaces/behavior/video/video_utils.py: def get_video_frame(self, frame_number: int):

67.  ./src/neuroconv/datainterfaces/behavior/video/video_utils.py: def get_video_frame_dtype(self):

68.  ./src/neuroconv/datainterfaces/behavior/sleap/sleapdatainterface.py: def get_source_schema(cls) -> dict:

69.  ./src/neuroconv/datainterfaces/behavior/sleap/sleapdatainterface.py: def get_original_timestamps(self) -> np.ndarray:

70.  ./src/neuroconv/datainterfaces/behavior/sleap/sleapdatainterface.py: def get_timestamps(self) -> np.ndarray:

71.  ./src/neuroconv/datainterfaces/behavior/fictrac/fictracdatainterface.py: def get_source_schema(cls) -> dict:

72.  ./src/neuroconv/datainterfaces/behavior/fictrac/fictracdatainterface.py: def get_metadata(self):

73.  ./src/neuroconv/datainterfaces/behavior/fictrac/fictracdatainterface.py: def get_original_timestamps(self):

74.  ./src/neuroconv/datainterfaces/behavior/fictrac/fictracdatainterface.py: def get_timestamps(self):

75.  ./src/neuroconv/datainterfaces/behavior/deeplabcut/deeplabcutdatainterface.py: def get_source_schema(cls) -> dict:

76.  ./src/neuroconv/datainterfaces/behavior/deeplabcut/deeplabcutdatainterface.py: def get_metadata(self):

77.  ./src/neuroconv/datainterfaces/behavior/deeplabcut/deeplabcutdatainterface.py: def get_original_timestamps(self) -> np.ndarray:

78.  ./src/neuroconv/datainterfaces/behavior/deeplabcut/deeplabcutdatainterface.py: def get_timestamps(self) -> np.ndarray:

79.  ./src/neuroconv/datainterfaces/behavior/lightningpose/lightningposeconverter.py: def get_source_schema(cls):

80.  ./src/neuroconv/datainterfaces/behavior/lightningpose/lightningposeconverter.py: def get_conversion_options_schema(self) -> dict:

81.  ./src/neuroconv/datainterfaces/behavior/lightningpose/lightningposeconverter.py: def get_metadata(self) -> DeepDict:

82.  ./src/neuroconv/datainterfaces/behavior/lightningpose/lightningposedatainterface.py: def get_metadata_schema(self) -> dict:

83.  ./src/neuroconv/datainterfaces/behavior/lightningpose/lightningposedatainterface.py: def get_original_timestamps(self, stub_test: bool = False) -> np.ndarray:

84.  ./src/neuroconv/datainterfaces/behavior/lightningpose/lightningposedatainterface.py: def get_timestamps(self, stub_test: bool = False) -> np.ndarray:

85.  ./src/neuroconv/datainterfaces/behavior/lightningpose/lightningposedatainterface.py: def get_metadata(self) -> DeepDict:

86.  ./src/neuroconv/datainterfaces/behavior/audio/audiointerface.py: def get_metadata_schema(self) -> dict:

87.  ./src/neuroconv/datainterfaces/behavior/audio/audiointerface.py: def get_metadata(self) -> dict:

88.  ./src/neuroconv/datainterfaces/behavior/audio/audiointerface.py: def get_original_timestamps(self) -> np.ndarray:

89.  ./src/neuroconv/datainterfaces/behavior/audio/audiointerface.py: def get_timestamps(self) -> Optional[np.ndarray]:

90.  ./src/neuroconv/datainterfaces/behavior/miniscope/miniscopedatainterface.py: def get_source_schema(cls) -> dict:

91.  ./src/neuroconv/datainterfaces/behavior/miniscope/miniscopedatainterface.py: def get_metadata(self) -> DeepDict:

92.  ./src/neuroconv/datainterfaces/behavior/medpc/medpc_helpers.py:def get_medpc_variables(file_path: FilePath, variable_names: list) -> dict:

93.  ./src/neuroconv/datainterfaces/behavior/medpc/medpcdatainterface.py: def get_metadata(self) -> DeepDict:

94.  ./src/neuroconv/datainterfaces/behavior/medpc/medpcdatainterface.py: def get_metadata_schema(self) -> dict:

95.  ./src/neuroconv/datainterfaces/behavior/medpc/medpcdatainterface.py: def get_original_timestamps(self, medpc_name_to_info_dict: dict) -> dict[str, np.ndarray]:

96.  ./src/neuroconv/datainterfaces/behavior/medpc/medpcdatainterface.py: def get_timestamps(self) -> dict[str, np.ndarray]:

97.  ./src/neuroconv/datainterfaces/behavior/neuralynx/neuralynx_nvt_interface.py: def get_original_timestamps(self) -> np.ndarray:

98.  ./src/neuroconv/datainterfaces/behavior/neuralynx/neuralynx_nvt_interface.py: def get_timestamps(self) -> np.ndarray:

99.  ./src/neuroconv/datainterfaces/behavior/neuralynx/neuralynx_nvt_interface.py: def get_metadata(self) -> DeepDict:

100.  ./src/neuroconv/datainterfaces/behavior/neuralynx/neuralynx_nvt_interface.py: def get_metadata_schema(self) -> dict:

101.  ./src/neuroconv/datainterfaces/ophys/caiman/caimandatainterface.py: def get_source_schema(cls) -> dict:

102.  ./src/neuroconv/datainterfaces/ophys/micromanagertiff/micromanagertiffdatainterface.py: def get_source_schema(cls) -> dict:

103.  ./src/neuroconv/datainterfaces/ophys/micromanagertiff/micromanagertiffdatainterface.py: def get_metadata(self) -> dict:

104.  ./src/neuroconv/datainterfaces/ophys/baseimagingextractorinterface.py: def get_metadata_schema(

105.  ./src/neuroconv/datainterfaces/ophys/baseimagingextractorinterface.py: def get_metadata(

106.  ./src/neuroconv/datainterfaces/ophys/baseimagingextractorinterface.py: def get_original_timestamps(self) -> np.ndarray:

107.  ./src/neuroconv/datainterfaces/ophys/baseimagingextractorinterface.py: def get_timestamps(self) -> np.ndarray:

108.  ./src/neuroconv/datainterfaces/ophys/sbx/sbxdatainterface.py: def get_metadata(self) -> dict:

109.  ./src/neuroconv/datainterfaces/ophys/tdt_fp/tdtfiberphotometrydatainterface.py: def get_metadata(self) -> DeepDict:

110.  ./src/neuroconv/datainterfaces/ophys/tdt_fp/tdtfiberphotometrydatainterface.py: def get_metadata_schema(self) -> dict:

111.  ./src/neuroconv/datainterfaces/ophys/tdt_fp/tdtfiberphotometrydatainterface.py: def get_original_timestamps(self, t1: float = 0.0, t2: float = 0.0) -> dict[str, np.ndarray]:

112.  ./src/neuroconv/datainterfaces/ophys/tdt_fp/tdtfiberphotometrydatainterface.py: def get_timestamps(self, t1: float = 0.0, t2: float = 0.0) -> dict[str, np.ndarray]:

113.  ./src/neuroconv/datainterfaces/ophys/tdt_fp/tdtfiberphotometrydatainterface.py: def get_original_starting_time_and_rate(self, t1: float = 0.0, t2: float = 0.0) -> dict[str, tuple[float, float]]:

114.  ./src/neuroconv/datainterfaces/ophys/tdt_fp/tdtfiberphotometrydatainterface.py: def get_starting_time_and_rate(self, t1: float = 0.0, t2: float = 0.0) -> tuple[float, float]:

115.  ./src/neuroconv/datainterfaces/ophys/tdt_fp/tdtfiberphotometrydatainterface.py: def get_events(self) -> dict[str, dict[str, np.ndarray]]:

116.  ./src/neuroconv/datainterfaces/ophys/scanimage/scanimageimaginginterfaces.py: def get_source_schema(cls) -> dict:

117.  ./src/neuroconv/datainterfaces/ophys/scanimage/scanimageimaginginterfaces.py: def get_source_schema(cls) -> dict:

118.  ./src/neuroconv/datainterfaces/ophys/scanimage/scanimageimaginginterfaces.py: def get_metadata(self) -> dict:

119.  ./src/neuroconv/datainterfaces/ophys/scanimage/scanimageimaginginterfaces.py: def get_source_schema(cls) -> dict:

120.  ./src/neuroconv/datainterfaces/ophys/scanimage/scanimageimaginginterfaces.py: def get_metadata(self) -> dict:

121.  ./src/neuroconv/datainterfaces/ophys/scanimage/scanimageimaginginterfaces.py: def get_metadata(self) -> dict:

122.  ./src/neuroconv/datainterfaces/ophys/scanimage/scanimageimaginginterfaces.py: def get_metadata(self) -> dict:

123.  ./src/neuroconv/datainterfaces/ophys/scanimage/scanimageimaginginterfaces.py: def get_metadata(self) -> dict:

124.  ./src/neuroconv/datainterfaces/ophys/scanimage/scanimageimaginginterfaces.py:def get_scanimage_major_version(scanimage_metadata: dict) -> str:

125.  ./src/neuroconv/datainterfaces/ophys/basesegmentationextractorinterface.py: def get_metadata_schema(self) -> dict:

126.  ./src/neuroconv/datainterfaces/ophys/basesegmentationextractorinterface.py: def get_metadata(self) -> dict:

127.  ./src/neuroconv/datainterfaces/ophys/basesegmentationextractorinterface.py: def get_original_timestamps(self) -> np.ndarray:

128.  ./src/neuroconv/datainterfaces/ophys/basesegmentationextractorinterface.py: def get_timestamps(self) -> np.ndarray:

129.  ./src/neuroconv/datainterfaces/ophys/miniscope/miniscopeconverter.py: def get_source_schema(cls):

130.  ./src/neuroconv/datainterfaces/ophys/miniscope/miniscopeconverter.py: def get_conversion_options_schema(self) -> dict:

131.  ./src/neuroconv/datainterfaces/ophys/miniscope/miniscopeimagingdatainterface.py: def get_source_schema(cls) -> dict:

132.  ./src/neuroconv/datainterfaces/ophys/miniscope/miniscopeimagingdatainterface.py: def get_metadata(self) -> DeepDict:

133.  ./src/neuroconv/datainterfaces/ophys/miniscope/miniscopeimagingdatainterface.py: def get_metadata_schema(self) -> dict:

134.  ./src/neuroconv/datainterfaces/ophys/miniscope/miniscopeimagingdatainterface.py: def get_original_timestamps(self) -> np.ndarray:

135.  ./src/neuroconv/datainterfaces/ophys/suite2p/suite2pdatainterface.py: def get_source_schema(cls) -> dict:

136.  ./src/neuroconv/datainterfaces/ophys/suite2p/suite2pdatainterface.py: def get_available_planes(cls, folder_path: DirectoryPath) -> dict:

137.  ./src/neuroconv/datainterfaces/ophys/suite2p/suite2pdatainterface.py: def get_available_channels(cls, folder_path: DirectoryPath) -> dict:

138.  ./src/neuroconv/datainterfaces/ophys/suite2p/suite2pdatainterface.py: def get_metadata(self) -> DeepDict:

139.  ./src/neuroconv/datainterfaces/ophys/tiff/tiffdatainterface.py: def get_source_schema(cls) -> dict:

140.  ./src/neuroconv/datainterfaces/ophys/brukertiff/brukertiffconverter.py: def get_source_schema(cls):

141.  ./src/neuroconv/datainterfaces/ophys/brukertiff/brukertiffconverter.py: def get_conversion_options_schema(self):

142.  ./src/neuroconv/datainterfaces/ophys/brukertiff/brukertiffconverter.py: def get_source_schema(cls):

143.  ./src/neuroconv/datainterfaces/ophys/brukertiff/brukertiffconverter.py: def get_conversion_options_schema(self):

144.  ./src/neuroconv/datainterfaces/ophys/brukertiff/brukertiffdatainterface.py: def get_source_schema(cls) -> dict:

145.  ./src/neuroconv/datainterfaces/ophys/brukertiff/brukertiffdatainterface.py: def get_streams(

146.  ./src/neuroconv/datainterfaces/ophys/brukertiff/brukertiffdatainterface.py: def get_metadata(self) -> DeepDict:

147.  ./src/neuroconv/datainterfaces/ophys/brukertiff/brukertiffdatainterface.py: def get_source_schema(cls) -> dict:

148.  ./src/neuroconv/datainterfaces/ophys/brukertiff/brukertiffdatainterface.py: def get_streams(cls, folder_path: DirectoryPath) -> dict:

149.  ./src/neuroconv/datainterfaces/ophys/brukertiff/brukertiffdatainterface.py: def get_metadata(self) -> DeepDict:

150.  ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglx_utils.py:def get_session_start_time(recording_metadata: dict) -> datetime:

151.  ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglx_utils.py:def get_device_metadata(meta) -> dict:

152.  ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxconverter.py: def get_source_schema(cls):

153.  ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxconverter.py: def get_streams(cls, folder_path: DirectoryPath) -> list[str]:

154.  ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxconverter.py: def get_conversion_options_schema(self) -> dict:

155.  ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxdatainterface.py: def get_source_schema(cls) -> dict:

156.  ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxdatainterface.py: def get_metadata(self) -> dict:

157.  ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxdatainterface.py: def get_original_timestamps(self) -> np.ndarray:

158.  ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxnidqinterface.py: def get_source_schema(cls) -> dict:

159.  ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxnidqinterface.py: def get_metadata(self) -> dict:

160.  ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxnidqinterface.py: def get_channel_names(self) -> list[str]:

161.  ./src/neuroconv/datainterfaces/ecephys/spikeglx/spikeglxnidqinterface.py: def get_event_times_from_ttl(self, channel_name: str) -> np.ndarray:

162.  ./src/neuroconv/datainterfaces/ecephys/baserecordingextractorinterface.py: def get_metadata_schema(self) -> dict:

163.  ./src/neuroconv/datainterfaces/ecephys/baserecordingextractorinterface.py: def get_metadata(self) -> DeepDict:

164.  ./src/neuroconv/datainterfaces/ecephys/baserecordingextractorinterface.py: def get_original_timestamps(self) -> Union[np.ndarray, list[np.ndarray]]:

165.  ./src/neuroconv/datainterfaces/ecephys/baserecordingextractorinterface.py: def get_timestamps(self) -> Union[np.ndarray, list[np.ndarray]]:

166.  ./src/neuroconv/datainterfaces/ecephys/openephys/openephysdatainterface.py: def get_source_schema(cls) -> dict:

167.  ./src/neuroconv/datainterfaces/ecephys/openephys/openephysdatainterface.py: def get_stream_names(cls, folder_path: DirectoryPath) -> list[str]:

168.  ./src/neuroconv/datainterfaces/ecephys/openephys/openephyssortingdatainterface.py: def get_source_schema(cls) -> dict:

169.  ./src/neuroconv/datainterfaces/ecephys/openephys/openephysbinarydatainterface.py: def get_stream_names(cls, folder_path: DirectoryPath) -> list[str]:

170.  ./src/neuroconv/datainterfaces/ecephys/openephys/openephysbinarydatainterface.py: def get_source_schema(cls) -> dict:

171.  ./src/neuroconv/datainterfaces/ecephys/openephys/openephysbinarydatainterface.py: def get_metadata(self) -> dict:

172.  ./src/neuroconv/datainterfaces/ecephys/openephys/openephyslegacydatainterface.py: def get_stream_names(cls, folder_path: DirectoryPath) -> list[str]:

173.  ./src/neuroconv/datainterfaces/ecephys/openephys/openephyslegacydatainterface.py: def get_source_schema(cls):

174.  ./src/neuroconv/datainterfaces/ecephys/openephys/openephyslegacydatainterface.py: def get_metadata(self):

175.  ./src/neuroconv/datainterfaces/ecephys/edf/edfdatainterface.py: def get_source_schema(cls) -> dict:

176.  ./src/neuroconv/datainterfaces/ecephys/edf/edfdatainterface.py: def get_metadata(self) -> dict:

177.  ./src/neuroconv/datainterfaces/ecephys/plexon/plexondatainterface.py: def get_source_schema(cls) -> dict:

178.  ./src/neuroconv/datainterfaces/ecephys/plexon/plexondatainterface.py: def get_metadata(self) -> DeepDict:

179.  ./src/neuroconv/datainterfaces/ecephys/plexon/plexondatainterface.py: def get_source_schema(cls) -> dict:

180.  ./src/neuroconv/datainterfaces/ecephys/plexon/plexondatainterface.py: def get_metadata(self) -> DeepDict:

181.  ./src/neuroconv/datainterfaces/ecephys/plexon/plexondatainterface.py: def get_source_schema(cls) -> dict:

182.  ./src/neuroconv/datainterfaces/ecephys/plexon/plexondatainterface.py: def get_metadata(self) -> dict:

183.  ./src/neuroconv/datainterfaces/ecephys/spikegadgets/spikegadgetsdatainterface.py: def get_source_schema(cls) -> dict:

184.  ./src/neuroconv/datainterfaces/ecephys/basesortingextractorinterface.py: def get_metadata_schema(self) -> dict:

185.  ./src/neuroconv/datainterfaces/ecephys/basesortingextractorinterface.py: def get_original_timestamps(self) -> np.ndarray:

186.  ./src/neuroconv/datainterfaces/ecephys/basesortingextractorinterface.py: def get_timestamps(self) -> Union[np.ndarray, list[np.ndarray]]:

187.  ./src/neuroconv/datainterfaces/ecephys/kilosort/kilosortdatainterface.py: def get_source_schema(cls) -> dict:

188.  ./src/neuroconv/datainterfaces/ecephys/kilosort/kilosortdatainterface.py: def get_metadata(self):

189.  ./src/neuroconv/datainterfaces/ecephys/phy/phydatainterface.py: def get_source_schema(cls) -> dict:

190.  ./src/neuroconv/datainterfaces/ecephys/phy/phydatainterface.py: def get_metadata(self):

191.  ./src/neuroconv/datainterfaces/ecephys/axona/axona_utils.py:def get_eeg_sampling_frequency(file_path: FilePath) -> float:

192.  ./src/neuroconv/datainterfaces/ecephys/axona/axona_utils.py:def get_all_file_paths(file_path: FilePath) -> list:

193.  ./src/neuroconv/datainterfaces/ecephys/axona/axona_utils.py:def get_header_bstring(file: FilePath) -> bytes:

194.  ./src/neuroconv/datainterfaces/ecephys/axona/axona_utils.py:def get_position_object(file_path: FilePath) -> Position:

195.  ./src/neuroconv/datainterfaces/ecephys/axona/axonadatainterface.py: def get_source_schema(cls) -> dict:

196.  ./src/neuroconv/datainterfaces/ecephys/axona/axonadatainterface.py: def get_metadata(self):

197.  ./src/neuroconv/datainterfaces/ecephys/axona/axonadatainterface.py: def get_source_schema(cls) -> dict:

198.  ./src/neuroconv/datainterfaces/ecephys/axona/axonadatainterface.py: def get_source_schema(cls) -> dict:

199.  ./src/neuroconv/datainterfaces/ecephys/axona/axonadatainterface.py: def get_source_schema(cls) -> dict:

200.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscopedatainterface.py: def get_source_schema(self) -> dict:

201.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscopedatainterface.py: def get_ecephys_metadata(xml_file_path: str) -> dict:

202.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscopedatainterface.py: def get_metadata(self) -> dict:

203.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscopedatainterface.py: def get_original_timestamps(self) -> np.ndarray:

204.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscopedatainterface.py: def get_source_schema(self) -> dict:

205.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscopedatainterface.py: def get_metadata(self) -> dict:

206.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscopedatainterface.py: def get_source_schema(self) -> dict:

207.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscopedatainterface.py: def get_metadata(self) -> dict:

208.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscope_utils.py:def get_xml_file_path(data_file_path: str) -> str:

209.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscope_utils.py:def get_xml(xml_file_path: str):

210.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscope_utils.py:def get_neural_channels(xml_file_path: str) -> list:

211.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscope_utils.py:def get_channel_groups(xml_file_path: str) -> list:

212.  ./src/neuroconv/datainterfaces/ecephys/neuroscope/neuroscope_utils.py:def get_session_start_time(xml_file_path: str) -> datetime:

213.  ./src/neuroconv/datainterfaces/ecephys/alphaomega/alphaomegadatainterface.py: def get_source_schema(cls) -> dict:

214.  ./src/neuroconv/datainterfaces/ecephys/alphaomega/alphaomegadatainterface.py: def get_metadata(self) -> dict:

215.  ./src/neuroconv/datainterfaces/ecephys/blackrock/blackrockdatainterface.py: def get_source_schema(cls):

216.  ./src/neuroconv/datainterfaces/ecephys/blackrock/blackrockdatainterface.py: def get_metadata(self) -> dict:

217.  ./src/neuroconv/datainterfaces/ecephys/blackrock/blackrockdatainterface.py: def get_source_schema(cls) -> dict:

218.  ./src/neuroconv/datainterfaces/ecephys/blackrock/blackrockdatainterface.py: def get_metadata(self) -> dict:

219.  ./src/neuroconv/datainterfaces/ecephys/biocam/biocamdatainterface.py: def get_source_schema(cls) -> dict:

220.  ./src/neuroconv/datainterfaces/ecephys/cellexplorer/cellexplorerdatainterface.py: def get_source_schema(cls) -> dict:

221.  ./src/neuroconv/datainterfaces/ecephys/cellexplorer/cellexplorerdatainterface.py: def get_original_timestamps(self):

222.  ./src/neuroconv/datainterfaces/ecephys/cellexplorer/cellexplorerdatainterface.py: def get_metadata(self) -> dict:

223.  ./src/neuroconv/datainterfaces/ecephys/maxwell/maxonedatainterface.py: def get_metadata(self) -> dict:

224.  ./src/neuroconv/datainterfaces/ecephys/intan/intandatainterface.py: def get_source_schema(cls) -> dict:

225.  ./src/neuroconv/datainterfaces/ecephys/intan/intandatainterface.py: def get_metadata_schema(self) -> dict:

226.  ./src/neuroconv/datainterfaces/ecephys/intan/intandatainterface.py: def get_metadata(self) -> dict:

227.  ./src/neuroconv/datainterfaces/ecephys/spike2/spike2datainterface.py: def get_source_schema(cls) -> dict:

228.  ./src/neuroconv/datainterfaces/ecephys/spike2/spike2datainterface.py: def get_all_channels_info(cls, file_path: FilePath):

229.  ./src/neuroconv/datainterfaces/ecephys/neuralynx/neuralynxdatainterface.py: def get_stream_names(cls, folder_path: DirectoryPath) -> list[str]:

230.  ./src/neuroconv/datainterfaces/ecephys/neuralynx/neuralynxdatainterface.py: def get_source_schema(cls) -> dict:

231.  ./src/neuroconv/datainterfaces/ecephys/neuralynx/neuralynxdatainterface.py: def get_metadata(self) -> dict:

232.  ./src/neuroconv/datainterfaces/ecephys/mcsraw/mcsrawdatainterface.py: def get_source_schema(cls) -> dict:

233.  ./src/neuroconv/datainterfaces/ecephys/mearec/mearecdatainterface.py: def get_source_schema(cls) -> dict:

234.  ./src/neuroconv/datainterfaces/ecephys/mearec/mearecdatainterface.py: def get_metadata(self) -> dict:

235.  ./src/neuroconv/datainterfaces/icephys/baseicephysinterface.py: def get_source_schema(cls) -> dict:

236.  ./src/neuroconv/datainterfaces/icephys/baseicephysinterface.py: def get_metadata_schema(self) -> dict:

237.  ./src/neuroconv/datainterfaces/icephys/baseicephysinterface.py: def get_metadata(self) -> dict:

238.  ./src/neuroconv/datainterfaces/icephys/baseicephysinterface.py: def get_original_timestamps(self) -> np.ndarray:

239.  ./src/neuroconv/datainterfaces/icephys/baseicephysinterface.py: def get_timestamps(self) -> np.ndarray:

240.  ./src/neuroconv/datainterfaces/icephys/abf/abfdatainterface.py:def get_start_datetime(neo_reader):

241.  ./src/neuroconv/datainterfaces/icephys/abf/abfdatainterface.py: def get_source_schema(cls) -> dict:

242.  ./src/neuroconv/datainterfaces/icephys/abf/abfdatainterface.py: def get_metadata(self) -> dict:

243.  ./src/neuroconv/datainterfaces/text/timeintervalsinterface.py: def get_metadata(self) -> dict:

244.  ./src/neuroconv/datainterfaces/text/timeintervalsinterface.py: def get_metadata_schema(self) -> dict:

245.  ./src/neuroconv/datainterfaces/text/timeintervalsinterface.py: def get_original_timestamps(self, column: str) -> np.ndarray:

246.  ./src/neuroconv/datainterfaces/text/timeintervalsinterface.py: def get_timestamps(self, column: str) -> np.ndarray:

247.  ./src/neuroconv/nwbconverter.py: def get_source_schema(cls) -> dict:

248.  ./src/neuroconv/nwbconverter.py: def get_metadata_schema(self) -> dict:

249.  ./src/neuroconv/nwbconverter.py: def get_metadata(self) -> DeepDict:

250.  ./src/neuroconv/nwbconverter.py: def get_conversion_options_schema(self) -> dict:

251.  ./src/neuroconv/nwbconverter.py: def get_default_backend_configuration(

252.  ./src/neuroconv/nwbconverter.py: def get_source_schema(cls) -> dict:

253.  ./src/neuroconv/nwbconverter.py: def get_conversion_options_schema(self) -> dict:
