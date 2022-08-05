import shutil
import unittest
from hdmf.testing import TestCase
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.datainterfaces.behavior.movie import MovieInterface


try:
    import cv2

    skip_test = False
except ImportError:
    skip_test = True


@unittest.skipIf(skip_test, "cv2 not installed")
class TestMovieInterface(TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.movie_files = self.create_movies()
        self.nwb_converter = self.create_movie_converter()
        self.metadata = self.nwb_converter.get_metadata()
        self.metadata["NWBFile"].update(session_start_time=datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S"))
        self.nwbfile_path = self.test_dir / "movie_test.nwb"
        self.starting_times = [0.0, 50.0]

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir)
        del self.nwb_converter

    def create_movies(self):
        movie_file1 = str(self.test_dir / "test1.avi")
        movie_file2 = str(self.test_dir / "test2.avi")
        number_of_frames = 30
        number_of_rows = 640
        number_of_columns = 480
        frameSize = (number_of_columns, number_of_rows)  # This is give in x,y images coordinates (x is columns)
        fps = 25
        # Standard code for specifying image formats
        fourcc_specification = ("M", "J", "P", "G")
        # Utility to transform the four code specification to OpenCV specification
        fourcc = cv2.VideoWriter_fourcc(*fourcc_specification)

        writer1 = cv2.VideoWriter(
            filename=movie_file1,
            fourcc=fourcc,
            fps=fps,
            frameSize=frameSize,
        )
        writer2 = cv2.VideoWriter(
            filename=movie_file2,
            fourcc=fourcc,
            fps=fps,
            frameSize=frameSize,
        )

        for frame in range(number_of_frames):
            writer1.write(np.random.randint(0, 255, (number_of_rows, number_of_columns, 3)).astype("uint8"))
            writer2.write(np.random.randint(0, 255, (number_of_rows, number_of_columns, 3)).astype("uint8"))

        writer1.release()
        writer2.release()

        return [movie_file1, movie_file2]

    def create_movie_converter(self):
        class MovieTestNWBConverter(NWBConverter):
            data_interface_classes = dict(Movie=MovieInterface)

        source_data = dict(Movie=dict(file_paths=self.movie_files))
        return MovieTestNWBConverter(source_data)

    def test_movie_starting_times(self):
        conversion_opts = dict(Movie=dict(starting_times=self.starting_times, external_mode=False))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for no in range(len(metadata["Behavior"]["Movies"])):
                movie_interface_name = metadata["Behavior"]["Movies"][no]["name"]
                assert movie_interface_name in mod
                assert self.starting_times[no] == mod[movie_interface_name].starting_time

    def test_movie_no_starting_times(self):
        conversion_opts = dict(Movie=dict(external_mode=False))
        with self.assertRaises(ValueError):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                overwrite=True,
                conversion_options=conversion_opts,
                metadata=self.metadata,
            )

    def test_movie_no_starting_times_with_exernal_model(self):
        conversion_opts = dict(Movie=dict(external_mode=True))
        metadata = self.metadata
        movie_interface_name = metadata["Behavior"]["Movies"][0]["name"]
        metadata["Behavior"]["Movies"][1]["name"] = movie_interface_name
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            assert movie_interface_name in mod
            assert mod[movie_interface_name].starting_time == 0.0

    def test_save_movie_to_custom_module(self):
        module_name = "TestModule"
        module_description = "This is a test module."
        conversion_opts = dict(
            Movie=dict(
                starting_times=self.starting_times,
                external_mode=False,
                module_name=module_name,
                module_description=module_description,
            )
        )
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert module_name in nwbfile.processing
            assert module_description == nwbfile.processing[module_name].description

    def test_movie_chunking(self):
        conv_ops = dict(
            Movie=dict(external_mode=False, stub_test=True, starting_times=self.starting_times, chunk_data=False)
        )
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path, overwrite=True, conversion_options=conv_ops, metadata=self.metadata
        )

        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for movie_metadata in metadata["Behavior"]["Movies"]:
                movie_interface_name = movie_metadata["name"]
                assert mod[movie_interface_name].data.chunks is not None  # TODO retrive storage_layout of hdf5 dataset

    def test_movie_external_mode(self):
        conversion_opts = dict(Movie=dict(starting_times=self.starting_times, external_mode=True))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for index, movie_metadata in enumerate(metadata["Behavior"]["Movies"]):
                movie_interface_name = movie_metadata["name"]
                assert mod[movie_interface_name].external_file[0] == str(self.movie_files[index])

    def test_movie_duplicate_names_with_external_mode(self):
        conversion_opts = dict(Movie=dict(external_mode=True))
        metadata = self.metadata
        movie_interface_name = metadata["Behavior"]["Movies"][0]["name"]
        metadata["Behavior"]["Movies"][1]["name"] = movie_interface_name
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
            assert len(mod[movie_interface_name].external_file) == 2

    def test_external_mode_assertion_with_movie_name_duplication(self):
        conversion_opts = dict(Movie=dict(external_mode=False))
        metadata = self.metadata
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
        conversion_opts = dict(Movie=dict(starting_times=self.starting_times, external_mode=False, stub_test=True))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for no in range(len(metadata["Behavior"]["Movies"])):
                movie_interface_name = metadata["Behavior"]["Movies"][no]["name"]
                assert mod[movie_interface_name].data.shape[0] == 10

    def test_movie_irregular_timestamps(self):
        timestamps = [1, 2, 4]
        conversion_opts = dict(
            Movie=dict(starting_times=self.starting_times, timestamps=timestamps, external_mode=True)
        )

        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=self.metadata,
        )

        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            acquisition_module = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for movie_metadata in metadata["Behavior"]["Movies"]:
                movie_interface_name = movie_metadata["name"]
                np.testing.assert_array_equal(timestamps, acquisition_module[movie_interface_name].timestamps[:])

    def test_movie_regular_timestamps(self):
        timestamps = [2.2, 2.4, 2.6]
        conversion_opts = dict(
            Movie=dict(starting_times=self.starting_times, timestamps=timestamps, external_mode=True)
        )

        rate = 1.0 / np.round(timestamps[1] - timestamps[0], 9)
        fps = 25.0
        expected_warn_msg = (
            f"The fps={fps} from movie data is unequal to the difference in "
            f"regular timestamps. Using fps={rate} from timestamps instead."
        )

        with self.assertWarnsWith(warn_type=UserWarning, exc_msg=expected_warn_msg):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                overwrite=True,
                conversion_options=conversion_opts,
                metadata=self.metadata,
            )

        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            acquisition_module = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for movie_metadata in metadata["Behavior"]["Movies"]:
                movie_interface_name = movie_metadata["name"]
                assert acquisition_module[movie_interface_name].rate == rate
                assert acquisition_module[movie_interface_name].timestamps is None
