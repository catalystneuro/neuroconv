import unittest
from datetime import datetime
from pathlib import Path

import numpy as np
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import DeepLabCutInterface, SLEAPInterface, VideoInterface
from neuroconv.tools.testing.data_interface_mixins import (
    DataInterfaceTestMixin,
    TemporalAlignmentMixin,
)

try:
    from .setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH


class TestDeepLabCutInterface(DataInterfaceTestMixin, TemporalAlignmentMixin, unittest.TestCase):
    data_interface_cls = DeepLabCutInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"),
        config_file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "config.yaml"),
        subject_name="ind1",
    )
    save_directory = OUTPUT_PATH

    def run_conversion(self, nwbfile_path: str):
        metadata = self.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        self.interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

    def check_interface_get_original_timestamps(self):
        pass  # TODO in separate PR

    def check_interface_get_timestamps(self):
        pass  # TODO in separate PR

    def check_interface_align_timestamps(self):
        pass  # TODO in separate PR

    def check_shift_timestamps_by_start_time(self):
        pass  # TODO in separate PR

    def check_interface_original_timestamps_inmutability(self):
        pass  # TODO in separate PR

    def check_nwbfile_temporal_alignment(self):
        pass  # TODO in separate PR

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "behavior" in nwbfile.processing
            processing_module_interfaces = nwbfile.processing["behavior"].data_interfaces
            assert "PoseEstimation" in processing_module_interfaces

            pose_estimation_series_in_nwb = processing_module_interfaces["PoseEstimation"].pose_estimation_series
            expected_pose_estimation_series = ["ind1_leftear", "ind1_rightear", "ind1_snout", "ind1_tailbase"]

            expected_pose_estimation_series_are_in_nwb_file = [
                pose_estimation in pose_estimation_series_in_nwb for pose_estimation in expected_pose_estimation_series
            ]

            assert all(expected_pose_estimation_series_are_in_nwb_file)


class TestVideoInterface(DataInterfaceTestMixin, TemporalAlignmentMixin, unittest.TestCase):
    data_interface_cls = VideoInterface
    interface_kwargs = [
        dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_avi.avi")]),
        dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_flv.flv")]),
        dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_mov.mov")]),
        dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_mp4.mp4")]),
        dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_wmv.wmv")]),
    ]
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            video_type = Path(self.test_kwargs["file_paths"][0]).suffix[1:]
            assert f"Video: video_{video_type}" in nwbfile.acquisition

    def check_interface_align_timestamps(self):
        all_unaligned_timestamps = self.interface.get_original_timestamps()

        random_number_generator = np.random.default_rng(seed=0)
        aligned_timestamps = [
            unaligned_timestamps + 1.23 + random_number_generator.random(size=unaligned_timestamps.shape)
            for unaligned_timestamps in all_unaligned_timestamps
        ]
        self.interface.align_timestamps(aligned_timestamps=aligned_timestamps)

        retrieved_aligned_timestamps = self.interface.get_timestamps()
        assert_array_equal(x=retrieved_aligned_timestamps, y=aligned_timestamps)

    def check_shift_timestamps_by_start_time(self):
        self.setUpFreshInterface()

        starting_time = 1.23
        self.interface.align_timestamps(aligned_timestamps=self.interface.get_original_timestamps())
        self.interface.align_starting_time(starting_time=starting_time)
        all_aligned_timestamps = self.interface.get_timestamps()

        unaligned_timestamps = self.interface.get_original_timestamps()
        all_expected_timestamps = [timestamps + starting_time for timestamps in unaligned_timestamps]
        [
            assert_array_equal(x=aligned_timestamps, y=expected_timestamps)
            for aligned_timestamps, expected_timestamps in zip(all_aligned_timestamps, all_expected_timestamps)
        ]

    def check_align_segment_starting_times(self):
        self.setUpFreshInterface()

        segment_starting_times = [1.23 * file_path_index for file_path_index in range(len(self.test_kwargs))]
        self.interface.align_segment_starting_times(segment_starting_times=segment_starting_times)
        all_aligned_timestamps = self.interface.get_timestamps()

        unaligned_timestamps = self.interface.get_original_timestamps()
        all_expected_timestamps = [
            timestamps + segment_starting_time
            for timestamps, segment_starting_time in zip(unaligned_timestamps, segment_starting_times)
        ]
        for aligned_timestamps, expected_timestamps in zip(all_aligned_timestamps, all_expected_timestamps):
            assert_array_equal(x=aligned_timestamps, y=expected_timestamps)

    def check_interface_original_timestamps_inmutability(self):
        self.setUpFreshInterface()

        all_pre_alignment_original_timestamps = self.interface.get_original_timestamps()

        all_aligned_timestamps = [
            pre_alignment_original_timestamps + 1.23
            for pre_alignment_original_timestamps in all_pre_alignment_original_timestamps
        ]
        self.interface.align_timestamps(aligned_timestamps=all_aligned_timestamps)

        all_post_alignment_original_timestamps = self.interface.get_original_timestamps()
        for post_alignment_original_timestamps, pre_alignment_original_timestamps in zip(
            all_post_alignment_original_timestamps, all_pre_alignment_original_timestamps
        ):
            assert_array_equal(x=post_alignment_original_timestamps, y=pre_alignment_original_timestamps)

    def check_nwbfile_temporal_alignment(self):
        pass  # TODO in separate PR

    def test_interface_alignment(self):
        interface_kwargs = self.interface_kwargs
        if isinstance(interface_kwargs, dict):
            interface_kwargs = [interface_kwargs]
        for num, kwargs in enumerate(interface_kwargs):
            with self.subTest(str(num)):
                self.case = num
                self.test_kwargs = kwargs

                self.check_interface_get_original_timestamps()
                self.check_interface_get_timestamps()
                self.check_interface_align_timestamps()
                self.check_shift_timestamps_by_start_time()
                self.check_interface_original_timestamps_inmutability()
                self.check_align_segment_starting_times()

                self.check_nwbfile_temporal_alignment()


class TestSLEAPInterface(DataInterfaceTestMixin, TemporalAlignmentMixin, unittest.TestCase):
    data_interface_cls = SLEAPInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "predictions_1.2.7_provenance_and_tracking.slp"),
        video_file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "melanogaster_courtship.mp4"),
    )
    save_directory = OUTPUT_PATH

    def run_conversion(self, nwbfile_path: str):
        metadata = self.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        self.interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "SLEAP_VIDEO_000_20190128_113421" in nwbfile.processing
            processing_module_interfaces = nwbfile.processing["SLEAP_VIDEO_000_20190128_113421"].data_interfaces
            assert "track=track_0" in processing_module_interfaces

            pose_estimation_series_in_nwb = processing_module_interfaces["track=track_0"].pose_estimation_series
            expected_pose_estimation_series = [
                "abdomen",
                "eyeL",
                "eyeR",
                "forelegL4",
                "forelegR4",
                "head",
                "hindlegL4",
                "hindlegR4",
                "midlegL4",
                "midlegR4",
                "thorax",
                "wingL",
                "wingR",
            ]
            self.assertCountEqual(first=pose_estimation_series_in_nwb, second=expected_pose_estimation_series)
