import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from warnings import warn

from hdmf.testing import TestCase
from pynwb import NWBHDF5IO
from pynwb.image import ImageSeries

from neuroconv import ConverterPipe, NWBConverter
from neuroconv.converters import LightningPoseConverter
from neuroconv.tools import get_module
from neuroconv.utils import DeepDict

from ..setup_paths import BEHAVIOR_DATA_PATH


class TestLightningPoseConverter(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        lightning_pose_folder_path = BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds"
        cls.file_path = str(lightning_pose_folder_path / "test_vid.csv")
        cls.original_video_file_path = str(lightning_pose_folder_path / "test_vid.mp4")
        cls.labeled_video_file_path = str(lightning_pose_folder_path / "labeled_videos/test_vid_labeled.mp4")

        cls.pose_estimation_name = "PoseEstimation"
        cls.original_video_name = "original_video_name"
        cls.labeled_video_name = "labeled_video_name"

        cls.original_video_height = 406
        cls.original_video_width = 396

        cls.converter = LightningPoseConverter(
            file_path=cls.file_path,
            original_video_file_path=cls.original_video_file_path,
            labeled_video_file_path=cls.labeled_video_file_path,
            image_series_original_video_name=cls.original_video_name,
            image_series_labeled_video_name=cls.labeled_video_name,
        )

        cls.expected_keypoint_names = [
            "paw1LH_top",
            "paw2LF_top",
            "paw3RF_top",
            "paw4RH_top",
            "tailBase_top",
            "tailMid_top",
            "nose_top",
            "obs_top",
            "paw1LH_bot",
            "paw2LF_bot",
            "paw3RF_bot",
            "paw4RH_bot",
            "tailBase_bot",
            "tailMid_bot",
            "nose_bot",
            "obsHigh_bot",
            "obsLow_bot",
        ]

        cls.pose_estimation_metadata = DeepDict(
            name=cls.pose_estimation_name,
            description="Contains the pose estimation series for each keypoint.",
            scorer="heatmap_tracker",
            source_software="LightningPose",
            camera_name="CameraPoseEstimation",
        )

        cls.pose_estimation_metadata.update(
            {
                keypoint_name: dict(
                    name=f"PoseEstimationSeries{keypoint_name}",
                    description=f"The estimated position (x, y) of {keypoint_name} over time.",
                )
                for keypoint_name in cls.expected_keypoint_names
            }
        )

        cls.converter_metadata = dict(
            Behavior=dict(
                PoseEstimation=cls.pose_estimation_metadata,
                Videos=[
                    dict(
                        description="The original video used for pose estimation.",
                        name="original_video_name",
                        unit="Frames",
                    ),
                    dict(
                        description="The video recorded by camera with the pose estimation labels.",
                        name="labeled_video_name",
                        unit="Frames",
                    ),
                ],
            )
        )

        cls.test_dir = Path(tempfile.mkdtemp())

        cls.conversion_options = dict(stub_test=True)

        cls.pose_estimation_name = "PoseEstimation"

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_expected_metadata(self):
        metadata = self.converter.get_metadata()
        videos_metadata = metadata["Behavior"]["Videos"]
        self.assertEqual(len(videos_metadata), 2)
        self.assertDictEqual(metadata["Behavior"], self.converter_metadata["Behavior"])

    def test_run_conversion(self):
        nwbfile_path = str(self.test_dir / "test_lightningpose_converter.nwb")
        self.converter.run_conversion(nwbfile_path=nwbfile_path)

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path)

    def test_run_conversion_add_conversion_options(self):
        nwbfile_path = str(self.test_dir / "test_lightningpose_converter_conversion_options.nwb")

        conversion_options = dict(
            **self.conversion_options, reference_frame="(0,0) corresponds to the top left corner of the video."
        )
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            **conversion_options,
        )

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, **self.conversion_options)

    def assertNWBFileStructure(self, nwbfile_path: str, stub_test: bool = False):
        from ndx_pose import PoseEstimation

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            self.assertEqual(nwbfile.session_start_time, datetime(2023, 11, 9, 10, 14, 37).astimezone())

            # Check original video added to acquisition
            self.assertIn(self.original_video_name, nwbfile.acquisition)
            image_series = nwbfile.acquisition[self.original_video_name]
            self.assertIsInstance(image_series, ImageSeries)
            self.assertEqual(image_series.external_file[:], self.original_video_file_path)
            self.assertEqual(image_series.description, "The original video used for pose estimation.")

            # Check labeled video added to behavior processing module
            behavior = get_module(nwbfile=nwbfile, name="behavior")
            self.assertIn(self.labeled_video_name, behavior.data_interfaces)
            image_series_labeled_video = behavior.data_interfaces[self.labeled_video_name]
            self.assertIsInstance(image_series_labeled_video, ImageSeries)
            self.assertEqual(
                image_series_labeled_video.external_file[:],
                self.labeled_video_file_path,
            )
            self.assertEqual(
                image_series_labeled_video.description,
                "The video recorded by camera with the pose estimation labels.",
            )

            # Check pose estimation added to behavior processing module
            self.assertIn(self.pose_estimation_name, behavior.data_interfaces)
            self.assertIsInstance(behavior[self.pose_estimation_name], PoseEstimation)
            pose_estimation_container = nwbfile.processing["behavior"]["PoseEstimation"]

            # The current link between the pose estimation container "original_videos" and "labeled_videos" and the
            # ImageSeries is the name of the ImageSeries. TODO: update this when ndx-pose 0.2.0 is released.
            self.assertEqual(pose_estimation_container.original_videos[:], [image_series.name])
            self.assertEqual(pose_estimation_container.labeled_videos[:], [image_series_labeled_video.name])

            num_frames = 994 if not stub_test else 10
            for pose_estimation_series in pose_estimation_container.pose_estimation_series.values():
                self.assertEqual(pose_estimation_series.data.shape[0], num_frames)
                self.assertEqual(pose_estimation_series.confidence.shape[0], num_frames)

    def test_converter_in_converter(self):
        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestPoseConverter=LightningPoseConverter)

        converter = TestConverter(
            source_data=dict(
                TestPoseConverter=dict(
                    file_path=self.file_path,
                    original_video_file_path=self.original_video_file_path,
                    labeled_video_file_path=self.labeled_video_file_path,
                    image_series_original_video_name=self.original_video_name,
                    image_series_labeled_video_name=self.labeled_video_name,
                )
            )
        )

        conversion_options = dict(TestPoseConverter=self.conversion_options)

        nwbfile_path = str(self.test_dir / "test_lightningpose_converter_in_nwbconverter.nwb")
        converter.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        self.assertNWBFileStructure(nwbfile_path, **self.conversion_options)

    def test_converter_in_converter_pipe(self):
        converter_pipe = ConverterPipe(data_interfaces=[self.converter])

        nwbfile_path = self.test_dir / "test_lightningpose_converter_in_converter_pipe.nwb"

        conversion_options = dict(LightningPoseConverter=self.conversion_options)
        converter_pipe.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, **self.conversion_options)
