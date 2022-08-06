import unittest
from datetime import datetime
from parameterized import parameterized, param

from pynwb import NWBHDF5IO
from neuroconv import NWBConverter
from neuroconv.datainterfaces.behavior.movie import MovieInterface

# from neuroconv.datainterfaces.behavior.deeplabcut import DeepLabCutInterface

from .setup_paths import OUTPUT_PATH, BEHAVIOR_DATA_PATH


class TestDeepLabCutInterface(unittest.TestCase):
    savedir = OUTPUT_PATH

    @parameterized.expand(
        [
            # param(
            #     data_interface=DeepLabCutInterface,
            #     interface_kwargs=dict(
            #         file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"),
            #         config_file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "config.yaml"),
            #         subject_name="ind1",
            #     ),
            # )
        ],
        skip_on_empty=True,
    )
    def test_convert_behaviordata_to_nwb(self, data_interface, interface_kwargs):
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
        conversion_opts = dict(Movie=dict(external_mode=True))

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
        conversion_opts = dict(Movie=dict(external_mode=True))

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
