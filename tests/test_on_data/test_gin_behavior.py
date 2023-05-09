import unittest
from datetime import datetime
from pathlib import Path

import pytest
import sleap_io
from hdmf.testing import TestCase
from parameterized import param, parameterized
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.datainterfaces import DeepLabCutInterface, SLEAPInterface, VideoInterface

# enable to run locally in interactive mode
try:
    from .setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH

if not BEHAVIOR_DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {BEHAVIOR_DATA_PATH}!")


class TestSLEAPInterface(TestCase):
    savedir = OUTPUT_PATH

    @parameterized.expand(
        [
            param(
                data_interface=SLEAPInterface,
                interface_kwargs=dict(
                    file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "predictions_1.2.7_provenance_and_tracking.slp"),
                ),
            )
        ]
    )
    def test_sleap_to_nwb_interface(self, data_interface, interface_kwargs):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}.nwb")

        interface = SLEAPInterface(**interface_kwargs)
        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        slp_predictions_path = interface_kwargs["file_path"]
        labels = sleap_io.load_slp(slp_predictions_path)

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            # Test matching number of processing modules
            number_of_videos = len(labels.videos)
            assert len(nwbfile.processing) == number_of_videos

            # Test processing module naming as video
            processing_module_name = "SLEAP_VIDEO_000_20190128_113421"
            assert processing_module_name in nwbfile.processing

            # For this case we have as many containers as tracks
            # Each track usually represents a subject
            processing_module = nwbfile.processing[processing_module_name]
            processing_module_interfaces = processing_module.data_interfaces
            assert len(processing_module_interfaces) == len(labels.tracks)

            # Test name of PoseEstimation containers
            extracted_container_names = processing_module_interfaces.keys()
            for track in labels.tracks:
                expected_track_name = f"track={track.name}"
                assert expected_track_name in extracted_container_names

            # Test one PoseEstimation container
            container_name = f"track={track.name}"
            pose_estimation_container = processing_module_interfaces[container_name]
            # Test that the skeleton nodes are store as nodes in containers
            expected_node_names = [node.name for node in labels.skeletons[0]]
            assert expected_node_names == list(pose_estimation_container.nodes[:])

            # Test that each PoseEstimationSeries is named as a node
            for node_name in pose_estimation_container.nodes[:]:
                assert node_name in pose_estimation_container.pose_estimation_series

    @parameterized.expand(
        [
            param(
                data_interface=SLEAPInterface,
                interface_kwargs=dict(
                    file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "melanogaster_courtship.slp"),
                    video_file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "melanogaster_courtship.mp4"),
                ),
            )
        ]
    )
    def test_sleap_interface_timestamps_propagation(self, data_interface, interface_kwargs):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}.nwb")

        interface = SLEAPInterface(**interface_kwargs)
        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        slp_predictions_path = interface_kwargs["file_path"]
        labels = sleap_io.load_slp(slp_predictions_path)

        from neuroconv.datainterfaces.behavior.sleap.sleap_utils import (
            extract_timestamps,
        )

        expected_timestamps = set(extract_timestamps(interface_kwargs["video_file_path"]))

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            # Test matching number of processing modules
            number_of_videos = len(labels.videos)
            assert len(nwbfile.processing) == number_of_videos

            # Test processing module naming as video
            video_name = Path(labels.videos[0].filename).stem
            processing_module_name = f"SLEAP_VIDEO_000_{video_name}"

            # For this case we have as many containers as tracks
            processing_module_interfaces = nwbfile.processing[processing_module_name].data_interfaces

            extracted_container_names = processing_module_interfaces.keys()
            for track in labels.tracks:
                expected_track_name = f"track={track.name}"
                assert expected_track_name in extracted_container_names

                container_name = f"track={track.name}"
                pose_estimation_container = processing_module_interfaces[container_name]

                # Test that each PoseEstimationSeries is named as a node
                for node_name in pose_estimation_container.nodes[:]:
                    pose_estimation_series = pose_estimation_container.pose_estimation_series[node_name]
                    extracted_timestamps = pose_estimation_series.timestamps[:]

                    # Some frames do not have predictions associated with them, so we test for sub-set
                    assert set(extracted_timestamps).issubset(expected_timestamps)


class TestVideoConversions(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video_files = list((BEHAVIOR_DATA_PATH / "videos" / "CFR").iterdir())
        cls.video_files.sort()
        cls.number_of_video_files = len(cls.video_files)
        cls.segment_starting_times = [0.0, 50.0, 100.0, 150.0, 175.0]

    def _get_metadata(self):
        """TODO: temporary helper function to fetch new metadata each time; need to debug in follow-up."""
        self.metadata = self.converter.get_metadata()
        self.metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        self.image_series_name = self.metadata["Behavior"]["Videos"][0]["name"]

    def test_real_videos(self):
        # TODO - merge this with the data mixin in follow-up
        for file_index, (file_path, segment_starting_time) in enumerate(
            zip(self.video_files, self.segment_starting_times)
        ):
            self.file_index = file_index

            class VideoTestNWBConverter(NWBConverter):
                data_interface_classes = dict(Video=VideoInterface)

            source_data = dict(Video=dict(file_paths=[file_path]))
            self.converter = VideoTestNWBConverter(source_data)
            self.interface = self.converter.data_interface_objects["Video"]
            self.interface.align_segment_starting_times(
                segment_starting_times=[self.segment_starting_times[self.file_index]]
            )

            self.check_video_starting_times()
            self.check_video_custom_module()
            self.check_video_chunking()

    def check_video_starting_times(self):
        self._get_metadata()
        conversion_options = dict(Video=dict(external_mode=False))
        nwbfile_path = OUTPUT_PATH / "check_video_starting_times.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert self.image_series_name in nwbfile.acquisition
            self.image_series = nwbfile.acquisition[self.image_series_name]

            if self.image_series.starting_time is not None:
                assert self.segment_starting_times[self.file_index] == self.image_series.starting_time
            else:
                assert self.segment_starting_times[self.file_index] == self.image_series.timestamps[0]

    def check_video_custom_module(self):
        self._get_metadata()
        module_name = "TestModule"
        module_description = "This is a test module."
        conversion_options = dict(
            Video=dict(
                external_mode=False,
                module_name=module_name,
                module_description=module_description,
            )
        )
        nwbfile_path = OUTPUT_PATH / "test_video_custom_module.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert module_name in nwbfile.processing
            assert module_description == nwbfile.processing[module_name].description
            assert self.image_series_name in nwbfile.processing[module_name].data_interfaces

    def check_video_chunking(self):
        self._get_metadata()
        conversion_options = dict(Video=dict(external_mode=False, stub_test=True, chunk_data=False))
        nwbfile_path = OUTPUT_PATH / "check_video_chunking.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert self.image_series_name in nwbfile.acquisition
            assert nwbfile.acquisition[self.image_series_name].data.chunks is not None

    def check_external_mode(self):
        self._get_metadata()
        conversion_options = dict(Video=dict(external_mode=True))
        nwbfile_path = OUTPUT_PATH / "check_external_mode.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert self.image_series_name in nwbfile.acquisition
            assert nwbfile.acquisition[self.image_series_name].external_file[0] == str(
                self.video_files[self.file_index]
            )

    def check_video_stub(self):
        self._get_metadata()
        conversion_options = dict(Video=dict(external_mode=False, stub_test=True))
        nwbfile_path = OUTPUT_PATH / "check_video_stub.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert self.image_series_name in nwbfile.acquisition
            assert nwbfile.acquisition[self.image_series_name].data.shape[0] == 10


if __name__ == "__main__":
    unittest.main()
