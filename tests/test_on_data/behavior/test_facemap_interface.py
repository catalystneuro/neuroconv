import unittest

import h5py
from ndx_facemap_motionsvd import MotionSVDMasks, MotionSVDSeries
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO
from pynwb.behavior import EyeTracking, PupilTracking

from neuroconv.datainterfaces import FacemapInterface
from neuroconv.tools.testing.data_interface_mixins import (
    DataInterfaceTestMixin,
    TemporalAlignmentMixin,
)

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH


class TestFacemapInterface(DataInterfaceTestMixin, TemporalAlignmentMixin, unittest.TestCase):

    data_interface_cls = FacemapInterface
    interface_kwargs = dict(
        mat_file_path=str(BEHAVIOR_DATA_PATH / "Facemap" / "facemap_output_test.mat"),
        video_file_path=str(BEHAVIOR_DATA_PATH / "Facemap" / "raw_behavioral_video.avi"),
        first_n_components=3,
    )
    conversion_options = dict()
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls):

        cls.eye_tracking_module = "EyeTracking"
        cls.eye_com_expected_metadata = dict(
            name="eye_center_of_mass",
            description="The position of the eye measured in degrees.",
            reference_frame="unknown",
            unit="degrees",
        )

        cls.pupil_tracking_module = "PupilTracking"
        cls.pupil_area_expected_metadata = dict(
            name="pupil_area",
            description="Area of pupil.",
            unit="unknown",
        )
        cls.pupil_area_raw_expected_metadata = dict(
            name="pupil_area_raw",
            description="Raw unprocessed area of pupil.",
            unit="unknown",
        )

        cls.motion_masks_module = "MotionSVDMasks"
        cls.motion_masks_expected_metadata = dict(
            name="MotionSVDMasks",
            description="Motion masks",
        )
        cls.motion_series_module = "MotionSVDSeries"
        cls.motion_series_expected_metadata = dict(
            name="MotionSVDSeries",
            description="Motion SVD components",
        )
        with h5py.File(cls.interface_kwargs["mat_file_path"], "r") as file:
            cls.eye_tracking_test_data = file["proc"]["pupil"]["com"][:].T
            cls.pupil_area_test_data = file["proc"]["pupil"]["area"][:].T
            cls.pupil_area_raw_test_data = file["proc"]["pupil"]["area_raw"][:].T

    def check_extracted_metadata(self, metadata: dict):

        self.assertIn(self.eye_tracking_module, metadata["Behavior"])
        self.assertEqual(self.eye_com_expected_metadata, metadata["Behavior"]["EyeTracking"])

        self.assertIn(self.pupil_tracking_module, metadata["Behavior"])
        self.assertEqual(self.pupil_area_expected_metadata, metadata["Behavior"]["PupilTracking"]["area"])
        self.assertEqual(self.pupil_area_raw_expected_metadata, metadata["Behavior"]["PupilTracking"]["area_raw"])

        self.assertIn(self.motion_masks_module, metadata["Behavior"])
        self.assertEqual(self.motion_masks_expected_metadata, metadata["Behavior"]["MotionSVDMasks"])

        self.assertIn(self.motion_series_module, metadata["Behavior"])
        self.assertEqual(self.motion_series_expected_metadata, metadata["Behavior"]["MotionSVDSeries"])

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            self.assertIn("behavior", nwbfile.processing)

            self.assertIn(self.eye_tracking_module, nwbfile.processing["behavior"].data_interfaces)
            eye_tracking_container = nwbfile.processing["behavior"].data_interfaces[self.eye_tracking_module]
            self.assertIsInstance(eye_tracking_container, EyeTracking)
            eye_tracking_spatial_series = eye_tracking_container.spatial_series["eye_center_of_mass"]
            self.assertEqual(eye_tracking_spatial_series.data.shape, self.eye_tracking_test_data.shape)
            assert_array_equal(eye_tracking_spatial_series.data[:], self.eye_tracking_test_data)

            self.assertIn(self.pupil_tracking_module, nwbfile.processing["behavior"].data_interfaces)
            pupil_tracking_container = nwbfile.processing["behavior"].data_interfaces[self.pupil_tracking_module]
            self.assertIsInstance(pupil_tracking_container, PupilTracking)
            pupil_area_time_series = pupil_tracking_container.time_series["pupil_area"]
            self.assertEqual(pupil_area_time_series.data.shape, self.pupil_area_test_data.shape)
            assert_array_equal(pupil_area_time_series.data[:], self.pupil_area_test_data)
            pupil_area_raw_time_series = pupil_tracking_container.time_series["pupil_area_raw"]
            self.assertEqual(pupil_area_raw_time_series.data.shape, self.pupil_area_raw_test_data.shape)
            assert_array_equal(pupil_area_raw_time_series.data[:], self.pupil_area_raw_test_data)

            self.assertIn("MotionSVDMasksMultivideo", nwbfile.processing["behavior"].data_interfaces)
            motion_masks_container = nwbfile.processing["behavior"].data_interfaces["MotionSVDMasksMultivideo"]
            self.assertIsInstance(motion_masks_container, MotionSVDMasks)
            assert_array_equal(motion_masks_container.processed_frame_dimension[:], [295, 288])
            assert_array_equal(motion_masks_container.mask_coordinates[:], [49, 0, 294, 287])
            self.assertEqual(motion_masks_container.downsampling_factor, 4.0)
            self.assertEqual(motion_masks_container["image_mask"].shape[0], 3)
            self.assertIn("MotionSVDSeriesMultivideo", nwbfile.processing["behavior"].data_interfaces)
            motion_seires_container = nwbfile.processing["behavior"].data_interfaces["MotionSVDSeriesMultivideo"]
            self.assertIsInstance(motion_seires_container, MotionSVDSeries)
            self.assertEqual(motion_seires_container.data.shape[0], 18078)
            self.assertIn("MotionSVDMasksROI1", nwbfile.processing["behavior"].data_interfaces)
            motion_masks_container = nwbfile.processing["behavior"].data_interfaces["MotionSVDMasksROI1"]
            self.assertIsInstance(motion_masks_container, MotionSVDMasks)
            assert_array_equal(motion_masks_container.processed_frame_dimension[:], [295, 288])
            assert_array_equal(motion_masks_container.mask_coordinates[:], [147, 112, 279, 240])
            self.assertEqual(motion_masks_container.downsampling_factor, 4.0)
            self.assertEqual(motion_masks_container["image_mask"].shape[0], 3)
            self.assertIn("MotionSVDSeriesROI1", nwbfile.processing["behavior"].data_interfaces)
            motion_seires_container = nwbfile.processing["behavior"].data_interfaces["MotionSVDSeriesROI1"]
            self.assertIsInstance(motion_seires_container, MotionSVDSeries)
            self.assertEqual(motion_seires_container.data.shape[0], 18078)
