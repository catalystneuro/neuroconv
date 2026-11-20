from datetime import datetime

from numpy.testing import assert_allclose, assert_array_equal
from pynwb import read_nwb

from neuroconv import ConverterPipe
from neuroconv.datainterfaces import ExternalVideoInterface, FacemapInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH

FACEMAP_DATA_PATH = BEHAVIOR_DATA_PATH / "facemap" / "motion_svd" / "matlab_gui"
FIRST_N_COMPONENTS = 3


class TestFacemapInterfaceHDF5Container(DataInterfaceTestMixin):
    """The container `saveROI.m` writes: `save(savepath, '-v7.3', 'proc')`."""

    folder_path = FACEMAP_DATA_PATH / "whole_frame_and_one_roi" / "single_video_hdf5"
    interface_kwargs = dict(
        file_path=str(folder_path / "11222019_grabAM05_spont_proc.mat"),
        video_file_path=str(folder_path / "11222019_grabAM05_spont.avi"),
    )
    data_interface_cls = FacemapInterface
    conversion_options = dict(first_n_components=FIRST_N_COMPONENTS)
    expected_temporal_alignment_keys = ("facemap",)
    save_directory = OUTPUT_PATH

    expected_spatial_series_keys = {"facemap_eye_center_of_mass"}
    expected_time_series_keys = {"facemap_pupil_area", "facemap_pupil_area_raw"}
    expected_motion_svd_metadata_keys = {"facemap_multivideo", "facemap_roi1"}
    expected_container_names = {
        "EyeTracking",
        "PupilTracking",
        "MotionSVDMasksMultivideo",
        "MotionSVDSeriesMultivideo",
        "MotionSVDMasksROI1",
        "MotionSVDSeriesROI1",
    }
    expected_number_of_frames = 100
    expected_first_pupil_area = 5197.043
    expected_first_pupil_area_raw = 5197.043
    expected_first_eye_center_of_mass = [43.43814, 44.745445]
    expected_mask_coordinates = {"Multivideo": [49, 0, 294, 287], "ROI1": [147, 112, 279, 240]}
    expected_first_motion_svd = {
        "Multivideo": [1976.3438, -75.97976, -263.36057],
        "ROI1": [-46.846825, -949.67224, -117.67231],
    }
    expected_processed_frame_dimension = [295, 288]
    expected_average_motion_at_row_0_column_1 = {"Multivideo": 0.3526673, "ROI1": 2.7717488}
    expected_downsampling_factor = 4.0

    def check_extracted_metadata(self, metadata: dict):
        assert set(metadata["SpatialSeries"]) == self.expected_spatial_series_keys
        assert set(metadata["TimeSeries"]) == self.expected_time_series_keys
        facemap_metadata = metadata["Behavior"]["Facemap"]
        assert set(facemap_metadata["MotionSVDMasks"]) == self.expected_motion_svd_metadata_keys
        assert set(facemap_metadata["MotionSVDSeries"]) == self.expected_motion_svd_metadata_keys

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        containers = nwbfile.processing["behavior"].data_interfaces
        assert set(containers) == self.expected_container_names

        eye_center_of_mass = containers["EyeTracking"].spatial_series["eye_center_of_mass"]
        assert eye_center_of_mass.data.shape == (self.expected_number_of_frames, 2)
        assert_allclose(eye_center_of_mass.data[0], self.expected_first_eye_center_of_mass, rtol=1e-6)
        pupil_tracking = containers["PupilTracking"]
        assert_allclose(pupil_tracking.time_series["pupil_area"].data[0], self.expected_first_pupil_area, rtol=1e-6)
        assert_allclose(
            pupil_tracking.time_series["pupil_area_raw"].data[0], self.expected_first_pupil_area_raw, rtol=1e-6
        )

        for region_name, expected_mask_coordinates in self.expected_mask_coordinates.items():
            masks = containers[f"MotionSVDMasks{region_name}"]
            assert_array_equal(masks.mask_coordinates[:], expected_mask_coordinates)
            assert_array_equal(masks.processed_frame_dimension[:], self.expected_processed_frame_dimension)
            assert masks.downsampling_factor == self.expected_downsampling_factor
            assert len(masks) == FIRST_N_COMPONENTS
            row_start, column_start, row_end, column_end = expected_mask_coordinates
            assert masks.average_motion.shape == (row_end - row_start, column_end - column_start)
            assert_allclose(
                masks.average_motion[0, 1], self.expected_average_motion_at_row_0_column_1[region_name], rtol=1e-6
            )

            series = containers[f"MotionSVDSeries{region_name}"]
            assert series.data.shape == (self.expected_number_of_frames, FIRST_N_COMPONENTS)
            assert_allclose(series.data[0], self.expected_first_motion_svd[region_name], rtol=1e-6)


class TestFacemapInterfaceMatlab5Container(DataInterfaceTestMixin):
    """The same session as the HDF5 class resaved as plain MATLAB 5.0, which h5py cannot open."""

    folder_path = FACEMAP_DATA_PATH / "whole_frame_and_one_roi" / "single_video_matlab5"
    interface_kwargs = dict(
        file_path=str(folder_path / "11222019_grabAM05_spont_proc.mat"),
        video_file_path=str(folder_path / "11222019_grabAM05_spont.avi"),
    )
    data_interface_cls = FacemapInterface
    conversion_options = dict(first_n_components=FIRST_N_COMPONENTS)
    expected_temporal_alignment_keys = ("facemap",)
    save_directory = OUTPUT_PATH

    expected_spatial_series_keys = {"facemap_eye_center_of_mass"}
    expected_time_series_keys = {"facemap_pupil_area", "facemap_pupil_area_raw"}
    expected_motion_svd_metadata_keys = {"facemap_multivideo", "facemap_roi1"}
    expected_container_names = {
        "EyeTracking",
        "PupilTracking",
        "MotionSVDMasksMultivideo",
        "MotionSVDSeriesMultivideo",
        "MotionSVDMasksROI1",
        "MotionSVDSeriesROI1",
    }
    expected_number_of_frames = 100
    expected_first_pupil_area = 5197.043
    expected_first_pupil_area_raw = 5197.043
    expected_first_eye_center_of_mass = [43.43814, 44.745445]
    expected_mask_coordinates = {"Multivideo": [49, 0, 294, 287], "ROI1": [147, 112, 279, 240]}
    expected_first_motion_svd = {
        "Multivideo": [1976.3438, -75.97976, -263.36057],
        "ROI1": [-46.846825, -949.67224, -117.67231],
    }
    expected_processed_frame_dimension = [295, 288]
    expected_average_motion_at_row_0_column_1 = {"Multivideo": 0.3526673, "ROI1": 2.7717488}
    expected_downsampling_factor = 4.0

    def check_extracted_metadata(self, metadata: dict):
        assert set(metadata["SpatialSeries"]) == self.expected_spatial_series_keys
        assert set(metadata["TimeSeries"]) == self.expected_time_series_keys
        facemap_metadata = metadata["Behavior"]["Facemap"]
        assert set(facemap_metadata["MotionSVDMasks"]) == self.expected_motion_svd_metadata_keys
        assert set(facemap_metadata["MotionSVDSeries"]) == self.expected_motion_svd_metadata_keys

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        containers = nwbfile.processing["behavior"].data_interfaces
        assert set(containers) == self.expected_container_names

        eye_center_of_mass = containers["EyeTracking"].spatial_series["eye_center_of_mass"]
        assert eye_center_of_mass.data.shape == (self.expected_number_of_frames, 2)
        assert_allclose(eye_center_of_mass.data[0], self.expected_first_eye_center_of_mass, rtol=1e-6)
        pupil_tracking = containers["PupilTracking"]
        assert_allclose(pupil_tracking.time_series["pupil_area"].data[0], self.expected_first_pupil_area, rtol=1e-6)
        assert_allclose(
            pupil_tracking.time_series["pupil_area_raw"].data[0], self.expected_first_pupil_area_raw, rtol=1e-6
        )

        for region_name, expected_mask_coordinates in self.expected_mask_coordinates.items():
            masks = containers[f"MotionSVDMasks{region_name}"]
            assert_array_equal(masks.mask_coordinates[:], expected_mask_coordinates)
            assert_array_equal(masks.processed_frame_dimension[:], self.expected_processed_frame_dimension)
            assert masks.downsampling_factor == self.expected_downsampling_factor
            assert len(masks) == FIRST_N_COMPONENTS
            row_start, column_start, row_end, column_end = expected_mask_coordinates
            assert masks.average_motion.shape == (row_end - row_start, column_end - column_start)
            assert_allclose(
                masks.average_motion[0, 1], self.expected_average_motion_at_row_0_column_1[region_name], rtol=1e-6
            )

            series = containers[f"MotionSVDSeries{region_name}"]
            assert series.data.shape == (self.expected_number_of_frames, FIRST_N_COMPONENTS)
            assert_allclose(series.data[0], self.expected_first_motion_svd[region_name], rtol=1e-6)


class TestFacemapInterfaceWholeFrameOnly(DataInterfaceTestMixin):
    """A pupil ROI and the whole-frame motion SVD, with no small ROI drawn, so only cell 0 of `motSVD` holds data."""

    folder_path = FACEMAP_DATA_PATH / "whole_frame_only" / "single_video_matlab5"
    interface_kwargs = dict(
        file_path=str(folder_path / "face_video_proc.mat"),
        video_file_path=str(folder_path / "face_video.avi"),
    )
    data_interface_cls = FacemapInterface
    conversion_options = dict(first_n_components=FIRST_N_COMPONENTS)
    expected_temporal_alignment_keys = ("facemap",)
    save_directory = OUTPUT_PATH

    expected_spatial_series_keys = {"facemap_eye_center_of_mass"}
    expected_time_series_keys = {"facemap_pupil_area", "facemap_pupil_area_raw"}
    expected_motion_svd_metadata_keys = {"facemap_multivideo"}
    expected_container_names = {"EyeTracking", "PupilTracking", "MotionSVDMasksMultivideo", "MotionSVDSeriesMultivideo"}
    expected_number_of_frames = 100
    expected_first_pupil_area = 1515.5901
    expected_first_pupil_area_raw = 1485.8027
    expected_first_eye_center_of_mass = [41.205887, 45.540756]
    expected_mask_coordinates = {"Multivideo": [58, 0, 242, 311]}
    expected_first_motion_svd = {"Multivideo": [-117.641846, 147.4447, -31.44171]}
    expected_processed_frame_dimension = [298, 358]
    expected_average_motion_at_row_0_column_1 = {"Multivideo": 0.38216954}
    expected_downsampling_factor = 4.0

    def check_extracted_metadata(self, metadata: dict):
        assert set(metadata["SpatialSeries"]) == self.expected_spatial_series_keys
        assert set(metadata["TimeSeries"]) == self.expected_time_series_keys
        facemap_metadata = metadata["Behavior"]["Facemap"]
        assert set(facemap_metadata["MotionSVDMasks"]) == self.expected_motion_svd_metadata_keys
        assert set(facemap_metadata["MotionSVDSeries"]) == self.expected_motion_svd_metadata_keys

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        containers = nwbfile.processing["behavior"].data_interfaces
        assert set(containers) == self.expected_container_names

        eye_center_of_mass = containers["EyeTracking"].spatial_series["eye_center_of_mass"]
        assert eye_center_of_mass.data.shape == (self.expected_number_of_frames, 2)
        assert_allclose(eye_center_of_mass.data[0], self.expected_first_eye_center_of_mass, rtol=1e-6)
        pupil_tracking = containers["PupilTracking"]
        assert_allclose(pupil_tracking.time_series["pupil_area"].data[0], self.expected_first_pupil_area, rtol=1e-6)
        assert_allclose(
            pupil_tracking.time_series["pupil_area_raw"].data[0], self.expected_first_pupil_area_raw, rtol=1e-6
        )

        for region_name, expected_mask_coordinates in self.expected_mask_coordinates.items():
            masks = containers[f"MotionSVDMasks{region_name}"]
            assert_array_equal(masks.mask_coordinates[:], expected_mask_coordinates)
            assert_array_equal(masks.processed_frame_dimension[:], self.expected_processed_frame_dimension)
            assert masks.downsampling_factor == self.expected_downsampling_factor
            assert len(masks) == FIRST_N_COMPONENTS
            row_start, column_start, row_end, column_end = expected_mask_coordinates
            assert masks.average_motion.shape == (row_end - row_start, column_end - column_start)
            assert_allclose(
                masks.average_motion[0, 1], self.expected_average_motion_at_row_0_column_1[region_name], rtol=1e-6
            )

            series = containers[f"MotionSVDSeries{region_name}"]
            assert series.data.shape == (self.expected_number_of_frames, FIRST_N_COMPONENTS)
            assert_allclose(series.data[0], self.expected_first_motion_svd[region_name], rtol=1e-6)


class TestFacemapInterfacePupilOnly(DataInterfaceTestMixin):
    """A run with a pupil ROI and no motion SVD.

    Facemap writes `motSVD`, `uMotMask`, `avgmot`, `avgframe` and `avgmotion`
    whether or not an SVD was computed, leaving them empty when it was not, so the
    presence of those keys says nothing about whether they hold data.

    This fixture ships without its video, which is not public. It is paired with the
    100-frame video of the public session, which gives its 100 frames their times.
    """

    interface_kwargs = dict(
        file_path=str(FACEMAP_DATA_PATH / "pupil_only" / "single_video_hdf5" / "face_video_proc.mat"),
        video_file_path=str(
            FACEMAP_DATA_PATH / "whole_frame_and_one_roi" / "single_video_hdf5" / "11222019_grabAM05_spont.avi"
        ),
    )
    data_interface_cls = FacemapInterface
    expected_temporal_alignment_keys = ("facemap",)
    save_directory = OUTPUT_PATH

    expected_spatial_series_keys = {"facemap_eye_center_of_mass"}
    expected_time_series_keys = {"facemap_pupil_area", "facemap_pupil_area_raw"}
    expected_container_names = {"EyeTracking", "PupilTracking"}
    expected_number_of_frames = 100
    expected_first_pupil_area = 1530.868
    expected_first_pupil_area_raw = 1552.7341
    expected_first_eye_center_of_mass = [39.992153, 48.079636]

    def check_extracted_metadata(self, metadata: dict):
        assert set(metadata["SpatialSeries"]) == self.expected_spatial_series_keys
        assert set(metadata["TimeSeries"]) == self.expected_time_series_keys
        assert "Facemap" not in metadata.get("Behavior", {})

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        containers = nwbfile.processing["behavior"].data_interfaces
        assert set(containers) == self.expected_container_names

        eye_center_of_mass = containers["EyeTracking"].spatial_series["eye_center_of_mass"]
        assert eye_center_of_mass.data.shape == (self.expected_number_of_frames, 2)
        assert_allclose(eye_center_of_mass.data[0], self.expected_first_eye_center_of_mass, rtol=1e-6)
        pupil_tracking = containers["PupilTracking"]
        assert_allclose(pupil_tracking.time_series["pupil_area"].data[0], self.expected_first_pupil_area, rtol=1e-6)
        assert_allclose(
            pupil_tracking.time_series["pupil_area_raw"].data[0], self.expected_first_pupil_area_raw, rtol=1e-6
        )


class TestFacemapSourceVideoLink:
    """A masks entry's `source_video_metadata_key` links the masks to the video another interface wrote."""

    def test_masks_link_the_named_video(self):
        folder_path = FACEMAP_DATA_PATH / "whole_frame_and_one_roi" / "single_video_hdf5"
        video_file_path = folder_path / "11222019_grabAM05_spont.avi"
        video_metadata_key = "face_camera"
        linked_masks_metadata_key = "facemap_roi1"

        video_interface = ExternalVideoInterface(file_paths=[video_file_path], metadata_key=video_metadata_key)
        facemap_interface = FacemapInterface(
            file_path=folder_path / "11222019_grabAM05_spont_proc.mat", video_file_path=video_file_path, verbose=False
        )
        converter = ConverterPipe(data_interfaces=dict(video=video_interface, facemap=facemap_interface))
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        masks_metadata = metadata["Behavior"]["Facemap"]["MotionSVDMasks"]
        masks_metadata[linked_masks_metadata_key]["source_video_metadata_key"] = video_metadata_key

        nwbfile = converter.create_nwbfile(
            metadata=metadata, conversion_options=dict(facemap=dict(first_n_components=FIRST_N_COMPONENTS))
        )

        expected_video_name = metadata["Behavior"]["ExternalVideos"][video_metadata_key]["name"]
        behavior_module = nwbfile.processing["behavior"]
        assert behavior_module[masks_metadata[linked_masks_metadata_key]["name"]].source_video.name == (
            expected_video_name
        )
        assert behavior_module[masks_metadata["facemap_multivideo"]["name"]].source_video is None
