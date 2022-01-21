import shutil

import numpy as np
import pytest
from pynwb import NWBHDF5IO

from nwb_conversion_tools import NWBConverter, MovieInterface

try:
    import cv2
except ImportError:
    pytestmark = pytest.mark.skip(f"cv2 not installed, skipping test module {__name__} ")


@pytest.fixture(scope="module")
def base_path(tmp_path_factory):
    test_folder = tmp_path_factory.mktemp("movie_tests")
    yield test_folder
    print(f"removing {test_folder}")
    shutil.rmtree(test_folder)


@pytest.fixture
def create_movies(base_path):
    movie_file1 = base_path / "test1.avi"
    movie_file2 = base_path / "test2.avi"
    movie_file1.unlink(missing_ok=True)
    movie_file2.unlink(missing_ok=True)
    (nf, nx, ny) = (50, 640, 480)
    writer1 = cv2.VideoWriter(
        filename=str(movie_file1),
        apiPreference=None,
        fourcc=cv2.VideoWriter_fourcc("M", "J", "P", "G"),
        fps=25,
        frameSize=(ny, nx),
        params=None,
    )
    writer2 = cv2.VideoWriter(
        filename=str(movie_file2),
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
    return [str(movie_file1), str(movie_file2)]


@pytest.fixture
def movie_converter(create_movies):
    class MovieTestNWBConverter(NWBConverter):
        data_interface_classes = dict(Movie=MovieInterface)

    source_data = dict(Movie=dict(file_paths=create_movies))
    converter = MovieTestNWBConverter(source_data)
    yield converter
    del converter


@pytest.fixture(scope="module")
def nwbfile_path(base_path):
    return str(base_path / "test.nwb")


def test_movie_starting_times(movie_converter, nwbfile_path, create_movies):
    starting_times = [np.float(np.random.randint(200)) for i in range(len(create_movies))]
    conversion_opts = dict(Movie=dict(starting_times=starting_times, external_mode=False))
    movie_converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, conversion_options=conversion_opts)
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        mod = nwbfile.acquisition
        metadata = movie_converter.get_metadata()
        for no in range(len(metadata["Behavior"]["Movies"])):
            movie_interface_name = metadata["Behavior"]["Movies"][no]["name"]
            assert movie_interface_name in mod
            assert starting_times[no] == mod[movie_interface_name].starting_time


def test_movie_custom_module(movie_converter, nwbfile_path, create_movies):
    starting_times = [np.float(np.random.randint(200)) for i in range(len(create_movies))]
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
    movie_converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, conversion_options=conversion_opts)
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        assert module_name in nwbfile.processing
        assert module_description == nwbfile.processing[module_name].description


@pytest.mark.parametrize("chunk_data", [True, False])
def test_movie_chunking(chunk_data, movie_converter, nwbfile_path, create_movies):
    starting_times = [np.float(np.random.randint(200)) for i in range(len(create_movies))]
    conv_ops = dict(
        Movie=dict(external_mode=False, stub_test=True, starting_times=starting_times, chunk_data=chunk_data)
    )
    movie_converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, conversion_options=conv_ops)
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        mod = nwbfile.acquisition
        metadata = movie_converter.get_metadata()
        for no in range(len(metadata["Behavior"]["Movies"])):
            movie_interface_name = metadata["Behavior"]["Movies"][no]["name"]
            if chunk_data:
                assert mod[movie_interface_name].data.chunks is not None  # TODO retrive storage_layout of hdf5 dataset
            else:
                assert mod[movie_interface_name].data.chunks is not None


def test_movie_external_mode(movie_converter, nwbfile_path, create_movies):
    starting_times = [np.float(np.random.randint(200)) for i in range(len(create_movies))]
    conversion_opts = dict(Movie=dict(starting_times=starting_times, external_mode=True))
    movie_converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, conversion_options=conversion_opts)
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        mod = nwbfile.acquisition
        metadata = movie_converter.get_metadata()
        for no in range(len(metadata["Behavior"]["Movies"])):
            movie_interface_name = metadata["Behavior"]["Movies"][no]["name"]
            assert mod[movie_interface_name].external_file[0] == create_movies[no]
