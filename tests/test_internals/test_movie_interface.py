import unittest
import tempfile
import numpy as np
from pynwb import NWBHDF5IO
import os
from nwb_conversion_tools import NWBConverter, MovieInterface

try:
    import cv2
    skip_test = False
except ImportError:
    skip_test = True


@unittest.skipIf(skip_test, "cv2 not installed")
class TestMovieInterface(unittest.TestCase):

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.movie_files = self.create_movies()
        self.nwb_converter = self.create_movie_converter()
        self.nwbfile_path = os.path.join(self.test_dir, "movie_test.nwb")

    def create_movies(self):
        movie_file1 = os.path.join(self.test_dir, "test1.avi")
        movie_file2 = os.path.join(self.test_dir, "test2.avi")
        (nf, nx, ny) = (10, 640, 480)
        writer1 = cv2.VideoWriter(
            filename=movie_file1,
            apiPreference=None,
            fourcc=cv2.VideoWriter_fourcc("M", "J", "P", "G"),
            fps=25,
            frameSize=(ny, nx),
            params=None,
        )
        writer2 = cv2.VideoWriter(
            filename=movie_file2,
            apiPreference=None,
            fourcc=cv2.VideoWriter_fourcc("M", "J", "P", "G"),
            fps=25,
            frameSize=(ny, nx),
            params=None,
        )

        for k in range(nf):
            writer1.write(np.random.randint(0, 255, (nx, ny, 3)).astype("uint8"))
            writer2.write(np.random.randint(0, 255, (nx, ny, 3)).astype("uint8"))
        writer1.release()
        writer2.release()
        return [movie_file1, movie_file2]

    def create_movie_converter(self):
        class MovieTestNWBConverter(NWBConverter):
            data_interface_classes = dict(Movie=MovieInterface)

        source_data = dict(Movie=dict(file_paths=self.movie_files))
        return MovieTestNWBConverter(source_data)

    def test_movie_starting_times(self):
        starting_times = [np.float(np.random.randint(200)) for i in range(len(self.movie_files))]
        conversion_opts = dict(Movie=dict(starting_times=starting_times, external_mode=False))
        self.nwb_converter.run_conversion(nwbfile_path=self.nwbfile_path,
                                          overwrite=True,
                                          conversion_options=conversion_opts)
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for no in range(len(metadata["Behavior"]["Movies"])):
                movie_interface_name = metadata["Behavior"]["Movies"][no]["name"]
                assert movie_interface_name in mod
                assert starting_times[no] == mod[movie_interface_name].starting_time

    def test_movie_custom_module(self):
        starting_times = [np.float(np.random.randint(200)) for i in range(len(self.movie_files))]
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
        self.nwb_converter.run_conversion(nwbfile_path=self.nwbfile_path,
                                          overwrite=True,
                                          conversion_options=conversion_opts)
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert module_name in nwbfile.processing
            assert module_description == nwbfile.processing[module_name].description

    def test_movie_chunking(self):
        starting_times = [np.float(np.random.randint(200)) for i in range(len(self.movie_files))]
        conv_ops = dict(
            Movie=dict(external_mode=False, stub_test=True, starting_times=starting_times, chunk_data=False)
        )
        self.nwb_converter.run_conversion(nwbfile_path=self.nwbfile_path,
                                          overwrite=True,
                                          conversion_options=conv_ops)

        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for no in range(len(metadata["Behavior"]["Movies"])):
                movie_interface_name = metadata["Behavior"]["Movies"][no]["name"]
                assert mod[movie_interface_name].data.chunks is not None  # TODO retrive storage_layout of hdf5 dataset

    def test_movie_external_mode(self):
        starting_times = [np.float(np.random.randint(200)) for i in range(len(self.movie_files))]
        conversion_opts = dict(Movie=dict(starting_times=starting_times, external_mode=True))
        self.nwb_converter.run_conversion(nwbfile_path=self.nwbfile_path, overwrite=True,
                                          conversion_options=conversion_opts)
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            mod = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for no in range(len(metadata["Behavior"]["Movies"])):
                movie_interface_name = metadata["Behavior"]["Movies"][no]["name"]
                assert mod[movie_interface_name].external_file[0] == self.movie_files[no]
