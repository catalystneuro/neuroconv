import unittest
from pathlib import Path
from datetime import datetime

from parameterized import parameterized, param
from pynwb import NWBHDF5IO
from neuroconv import NWBConverter
from neuroconv.datainterfaces import MovieInterface, DeepLabCutInterface, SLEAPInterface

from .setup_paths import OUTPUT_PATH, BEHAVIOR_DATA_PATH
import sleap_io


class TestSLEAPInterface(unittest.TestCase):

    savedir = OUTPUT_PATH

    @parameterized.expand(
        [
            param(
                data_interface=SLEAPInterface,
                interface_kwargs=dict(
                    file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "predictions_1.2.7_provenance_and_tracking.slp")
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
                    file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "predictions_1.2.7_provenance_and_tracking.slp")
                ),
            )
        ]
    )
    def test_sleap_to_nwb_converter(self, data_interface, interface_kwargs):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}converter.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestBehavior=data_interface)

        converter = TestConverter(source_data=dict(TestBehavior=dict(interface_kwargs)))
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

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


class TestDeepLabCutInterface(unittest.TestCase):
    savedir = OUTPUT_PATH

    @parameterized.expand(
        [
            param(
                data_interface=DeepLabCutInterface,
                interface_kwargs=dict(
                    file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"),
                    config_file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "config.yaml"),
                    subject_name="ind1",
                ),
            )
        ]
    )
    def test_deeplabcut_to_nwb(self, data_interface, interface_kwargs):
        nwbfile_path = self.savedir / f"{data_interface.__name__}.nwb"

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestBehavior=data_interface)

        converter = TestConverter(source_data=dict(TestBehavior=dict(interface_kwargs)))
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

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


class TestMovieDataNwbConversions(unittest.TestCase):
    def setUp(self):
        self.movie_files = list((BEHAVIOR_DATA_PATH / "videos" / "CFR").iterdir())
        self.movie_files.sort()
        self.number_of_movie_files = len(self.movie_files)
        self.nwb_converter = self.create_movie_converter()
        self.nwbfile_path = OUTPUT_PATH / "movie_test.nwb"
        self.starting_times = [0.0, 50.0, 100.0, 150.0, 175.0]

    def create_movie_converter(self):
        class MovieTestNWBConverter(NWBConverter):
            data_interface_classes = dict(Movie=MovieInterface)

        source_data = dict(Movie=dict(file_paths=self.movie_files))
        return MovieTestNWBConverter(source_data)

    def get_metadata(self):
        metadata = self.nwb_converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        return metadata

    def test_movie_starting_times(self):
        starting_times = self.starting_times
        conversion_opts = dict(Movie=dict(starting_times=starting_times, external_mode=False))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=self.get_metadata(),
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for no in range(len(metadata["Behavior"]["Movies"])):
                movie_interface_name = metadata["Behavior"]["Movies"][no]["name"]
                assert movie_interface_name in mod
                if mod[movie_interface_name].starting_time is not None:
                    assert starting_times[no] == mod[movie_interface_name].starting_time
                else:
                    assert starting_times[no] == mod[movie_interface_name].timestamps[0]

    def test_movie_starting_times_none(self):
        """For multiple ImageSeries containers, starting times must be provided with len(movie_files)"""
        conversion_opts = dict(Movie=dict(external_mode=False))
        with self.assertRaises(ValueError):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                overwrite=True,
                conversion_options=conversion_opts,
                metadata=self.get_metadata(),
            )

    def test_movie_starting_times_with_duplicate_names(self):
        """When all movies go in one ImageSeries container, starting times should be assumed 0.0"""
        self.nwbfile_path = self.nwbfile_path.parent / "movie_duplicated_names.nwb"
        conversion_opts = dict(Movie=dict(external_mode=True, starting_frames=[[0] * 5]))

        metadata = self.get_metadata()
        movies_metadata = metadata["Behavior"]["Movies"]
        first_movie_name = movies_metadata[0]["name"]
        for movie in movies_metadata:
            movie["name"] = first_movie_name

        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert first_movie_name in nwbfile.acquisition
            image_series = nwbfile.acquisition[first_movie_name]
            assert image_series is not None
            starting_time = image_series.starting_time
            if starting_time is None:
                starting_time = image_series.timestamps[0]
            assert starting_time == 0.0, f"image series {image_series} starting time not equal to 0"

    def test_movie_custom_module(self):
        starting_times = self.starting_times
        module_name = "TestModule"
        module_description = "This is a test module."
        conversion_opts = dict(
            Movie=dict(
                starting_times=starting_times,
                external_mode=False,
                module_name=module_name,
                module_description=module_description,
            )
        )
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=self.get_metadata(),
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert module_name in nwbfile.processing
            assert module_description == nwbfile.processing[module_name].description

    def test_movie_chunking(self):
        starting_times = self.starting_times
        conv_ops = dict(
            Movie=dict(external_mode=False, stub_test=True, starting_times=starting_times, chunk_data=False)
        )
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path, overwrite=True, conversion_options=conv_ops, metadata=self.get_metadata()
        )

        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for no in range(len(metadata["Behavior"]["Movies"])):
                movie_interface_name = metadata["Behavior"]["Movies"][no]["name"]
                assert mod[movie_interface_name].data.chunks is not None  # TODO retrive storage_layout of hdf5 dataset

    def test_external_mode(self):
        starting_times = self.starting_times
        conversion_opts = dict(Movie=dict(starting_times=starting_times, external_mode=True))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=self.get_metadata(),
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for no in range(len(metadata["Behavior"]["Movies"])):
                movie_interface_name = metadata["Behavior"]["Movies"][no]["name"]
                assert mod[movie_interface_name].external_file[0] == str(self.movie_files[no])

    def test_external_model_with_duplicate_movies(self):
        conversion_opts = dict(Movie=dict(external_mode=True, starting_frames=[[0] * 5]))

        metadata = self.get_metadata()
        movie_interface_name = metadata["Behavior"]["Movies"][0]["name"]
        for no in range(1, len(self.movie_files)):
            metadata["Behavior"]["Movies"][no]["name"] = movie_interface_name

        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            assert len(mod) == 1
            assert movie_interface_name in mod
            assert len(mod[movie_interface_name].external_file) == len(self.movie_files)

    def test_movie_duplicate_kwargs(self):
        conversion_opts = dict(Movie=dict(external_mode=False))
        metadata = self.get_metadata()
        movie_interface_name = metadata["Behavior"]["Movies"][0]["name"]
        metadata["Behavior"]["Movies"][1]["name"] = movie_interface_name
        with self.assertRaises(AssertionError):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                overwrite=True,
                conversion_options=conversion_opts,
                metadata=metadata,
            )

    def test_movie_stub(self):
        starting_times = self.starting_times
        conversion_opts = dict(Movie=dict(starting_times=starting_times, external_mode=False, stub_test=True))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=self.get_metadata(),
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for no in range(len(metadata["Behavior"]["Movies"])):
                movie_interface_name = metadata["Behavior"]["Movies"][no]["name"]
                assert mod[movie_interface_name].data.shape[0] == 10


if __name__ == "__main__":
    unittest.main()
