import os
import warnings
from datetime import datetime
from pathlib import Path

from numpy.testing import assert_allclose
from pynwb import read_nwb
from pynwb.image import ImageSeries

from neuroconv import ConverterPipe, NWBConverter
from neuroconv.converters import LightningPoseConverter
from neuroconv.tools import get_module
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin
from neuroconv.utils import DeepDict

from ..setup_paths import BEHAVIOR_DATA_PATH

lightning_pose_folder_path = BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds"


class TestLightningPoseConverter(DataInterfaceTestMixin):
    data_interface_cls = LightningPoseConverter
    interface_kwargs = dict(
        file_path=str(lightning_pose_folder_path / "test_vid.csv"),
        original_video_file_path=str(lightning_pose_folder_path / "test_vid.mp4"),
        labeled_video_file_path=str(lightning_pose_folder_path / "labeled_videos/test_vid_labeled.mp4"),
        image_series_original_video_name="original_video_name",
        image_series_labeled_video_name="labeled_video_name",
    )
    expected_temporal_alignment_keys = ("lightning_pose", "original_video", "labeled_video")

    file_path = interface_kwargs["file_path"]
    original_video_file_path = interface_kwargs["original_video_file_path"]
    labeled_video_file_path = interface_kwargs["labeled_video_file_path"]

    pose_estimation_name = "PoseEstimation"
    original_video_name = "original_video_name"
    labeled_video_name = "labeled_video_name"

    original_video_height = 406
    original_video_width = 396

    expected_keypoint_names = [
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

    pose_estimation_metadata = DeepDict(
        name=pose_estimation_name,
        description="Contains the pose estimation series for each keypoint.",
        scorer="heatmap_tracker",
        source_software="LightningPose",
        camera_name="CameraPoseEstimation",
    )

    pose_estimation_metadata.update(
        {
            keypoint_name: dict(
                name=f"PoseEstimationSeries{keypoint_name}",
                description=f"The estimated position (x, y) of {keypoint_name} over time.",
            )
            for keypoint_name in expected_keypoint_names
        }
    )

    converter_metadata = dict(
        Behavior=dict(
            PoseEstimation=pose_estimation_metadata,
            ExternalVideos={
                "original_video": dict(
                    name="original_video_name",
                    description="The original video used for pose estimation.",
                    unit="Frames",
                    device_metadata_key="original_video_camera",
                ),
                "labeled_video": dict(
                    name="labeled_video_name",
                    description="The video recorded by camera with the pose estimation labels.",
                    unit="Frames",
                    device_metadata_key="labeled_video_camera",
                ),
            },
        )
    )

    stub_conversion_options = dict(stub_test=True)

    def check_read_nwb(self, nwbfile_path: str):
        self.assertNWBFileStructure(nwbfile_path=nwbfile_path)

    def test_expected_metadata(self, setup_interface):
        metadata = self.interface.get_metadata(use_new_metadata_format=False)
        videos_metadata = metadata["Behavior"]["ExternalVideos"]
        assert len(videos_metadata) == 2
        assert metadata["Behavior"] == self.converter_metadata["Behavior"]

    # TODO: remove when the legacy metadata["Behavior"]["PoseEstimation"] block is removed. The tests
    # above pass no metadata, which fills the dict-based format, so that is the covered path and this
    # is what holds the old one to writing the same file.
    def test_run_conversion_old_metadata_format(self, setup_interface, tmp_path):
        nwbfile_path = str(tmp_path / "test_lightningpose_converter_old_metadata_format.nwb")

        metadata = self.interface.get_metadata(use_new_metadata_format=False)
        self.interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, **self.stub_conversion_options)

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, links_video=False, **self.stub_conversion_options)

    def test_run_conversion_add_conversion_options(self, setup_interface, tmp_path):
        nwbfile_path = str(tmp_path / "test_lightningpose_converter_conversion_options.nwb")

        conversion_options = dict(
            **self.stub_conversion_options, reference_frame="(0,0) corresponds to the top left corner of the video."
        )
        self.interface.run_conversion(
            nwbfile_path=nwbfile_path,
            **conversion_options,
        )

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, **self.stub_conversion_options)

    def assertNWBFileStructure(self, nwbfile_path: str, stub_test: bool = False, links_video: bool = True):
        from ndx_pose import PoseEstimation

        nwbfile = read_nwb(nwbfile_path)
        try:

            assert nwbfile.session_start_time == datetime(2023, 11, 9, 10, 14, 37).astimezone()

            # Check original video added to acquisition
            assert self.original_video_name in nwbfile.acquisition
            image_series = nwbfile.acquisition[self.original_video_name]
            assert isinstance(image_series, ImageSeries)
            # Written relative to the NWB file, except on Windows CI where the data sits on another drive
            output_directory = Path(nwbfile_path).resolve().parent
            video_path = Path(self.original_video_file_path).resolve()
            if video_path.anchor == output_directory.anchor:
                expected_external_file = Path(os.path.relpath(video_path, start=output_directory)).as_posix()
            else:
                expected_external_file = video_path.as_posix()
            assert image_series.external_file[:] == expected_external_file
            assert image_series.description == "The original video used for pose estimation."

            # Check labeled video added to behavior processing module
            behavior = get_module(nwbfile=nwbfile, name="behavior")
            assert self.labeled_video_name in behavior.data_interfaces
            image_series_labeled_video = behavior.data_interfaces[self.labeled_video_name]
            assert isinstance(image_series_labeled_video, ImageSeries)
            labeled_video_path = Path(self.labeled_video_file_path).resolve()
            if labeled_video_path.anchor == output_directory.anchor:
                expected_labeled_file = Path(os.path.relpath(labeled_video_path, start=output_directory)).as_posix()
            else:
                expected_labeled_file = labeled_video_path.as_posix()
            assert image_series_labeled_video.external_file[:] == expected_labeled_file
            assert (
                image_series_labeled_video.description
                == "The video recorded by camera with the pose estimation labels."
            )

            # Check pose estimation added to behavior processing module
            assert self.pose_estimation_name in behavior.data_interfaces
            assert isinstance(behavior[self.pose_estimation_name], PoseEstimation)
            pose_estimation_container = nwbfile.processing["behavior"]["PoseEstimation"]

            if links_video:
                # The container links the ImageSeries objects themselves rather than naming them in the
                # ``original_videos`` / ``labeled_videos`` path fields, which are left unset.
                assert pose_estimation_container.source_video is image_series
                assert pose_estimation_container.labeled_video is image_series_labeled_video
                assert pose_estimation_container.original_videos is None
                assert pose_estimation_container.labeled_videos is None
            else:
                # The legacy shape names the ImageSeries in the path fields, which is what it always did.
                assert list(pose_estimation_container.original_videos[:]) == [image_series.name]
                assert list(pose_estimation_container.labeled_videos[:]) == [image_series_labeled_video.name]

            num_frames = 994 if not stub_test else 10
            for pose_estimation_series in pose_estimation_container.pose_estimation_series.values():
                assert pose_estimation_series.data.shape[0] == num_frames
                assert pose_estimation_series.confidence.shape[0] == num_frames
        finally:
            nwbfile.read_io.close()

    def test_converter_in_converter(self, tmp_path):
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

        conversion_options = dict(TestPoseConverter=self.stub_conversion_options)

        nwbfile_path = str(tmp_path / "test_lightningpose_converter_in_nwbconverter.nwb")
        converter.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        self.assertNWBFileStructure(nwbfile_path, **self.stub_conversion_options)

    def test_converter_in_converter_pipe(self, setup_interface, tmp_path):
        converter_pipe = ConverterPipe(data_interfaces=[self.interface])

        nwbfile_path = tmp_path / "test_lightningpose_converter_in_converter_pipe.nwb"

        conversion_options = dict(LightningPoseConverter=self.stub_conversion_options)
        converter_pipe.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, **self.stub_conversion_options)

    def test_converter_pipe_shift_times_reaches_the_converter(self, setup_interface):
        unshifted_times = {
            key: self.interface.temporal_alignment[key].get_times() for key in self.interface.temporal_alignment.keys()
        }
        converter_pipe = ConverterPipe(data_interfaces=[self.interface])

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            converter_pipe.temporal_alignment.shift_times(5.0)

        for key, times in unshifted_times.items():
            assert_allclose(self.interface.temporal_alignment[key].get_times(), times + 5.0)
