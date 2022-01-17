from itertools import product

import numpy as np
import pytest
from pynwb import NWBHDF5IO

from nwb_conversion_tools import NWBConverter, MovieInterface

try:
    import cv2

    HAVE_OPENCV = True
except ImportError:
    HAVE_OPENCV = False


@pytest.fixture(scope="module")
def create_movies(tmp_path_factory):
    if HAVE_OPENCV:
        base_path = tmp_path_factory.mktemp("movie_tests")
        movie_file1 = base_path / "test1.avi"
        movie_file2 = base_path / "test2.avi"
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


@pytest.fixture(scope="module")
def movie_converter(create_movies):
    if HAVE_OPENCV:

        class MovieTestNWBConverter(NWBConverter):
            data_interface_classes = dict(Movie=MovieInterface)

        source_data = dict(Movie=dict(file_paths=create_movies))
        converter = MovieTestNWBConverter(source_data)
        return converter


def assert_nwbfile_conversion(
    converter,
    nwbfile_path,
    starting_times: list = None,
    module_name: str = None,
    module_description: str = None,
    metadata: dict = None,
    stub_test: bool = False,
    external_mode: bool = False,
    chunk_data: bool = False,
):
    metadata = converter.get_metadata() if metadata is None else metadata
    custom_names = [metadata["Behavior"]["Movies"][i]["name"] for i in range(len(metadata["Behavior"]["Movies"]))]
    conversion_opts = dict(
        starting_times=starting_times,
        stub_test=stub_test,
        external_mode=external_mode,
        chunk_data=chunk_data,
    )
    if module_name:
        conversion_opts.update(module_name=module_name)
    if module_description:
        conversion_opts.update(module_description=module_description)
    converter.run_conversion(
        metadata=metadata, nwbfile_path=nwbfile_path, overwrite=True, conversion_options=dict(Movie=conversion_opts)
    )
    module_name = module_name if module_name is not None else "acquisition"
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        mod = nwbfile.modules[module_name]
        assert module_name in mod
        if module_description:
            assert module_description == mod.description
        for no, name in enumerate(custom_names):
            if external_mode:
                for file_name in converter.data_interfaces["Movie"].source_data["file_paths"]:
                    assert file_name in mod[name].external_file
            else:
                assert name in mod
            if starting_times:
                assert starting_times[no] == mod[name].starting_time


@pytest.fixture(scope="module")
def nwbfile_path(tmp_path_factory):
    nwbfile_path = str(tmp_path_factory.mktemp("movie_tests") / "test.nwb")
    return nwbfile_path


def test_conversion_default(movie_converter, create_movies, nwbfile_path):
    if HAVE_OPENCV:
        starting_times = [np.float(np.random.randint(200)) for i in range(len(create_movies))]
        assert_nwbfile_conversion(converter=movie_converter, nwbfile_path=nwbfile_path, starting_times=starting_times)


def test_conversion_custom(movie_converter, nwbfile_path):
    if HAVE_OPENCV:
        starting_times = [np.float(np.random.randint(200)) for i in range(len(create_movies))]
        module_name = "TestModule"
        module_description = "This is a test module."
        assert_nwbfile_conversion(
            converter=movie_converter,
            nwbfile_path=nwbfile_path,
            module_description=module_description,
            module_name=module_name,
            starting_times=starting_times,
        )


def test_conversion_options(movie_converter, nwbfile_path):
    if HAVE_OPENCV:
        starting_times = [np.float(np.random.randint(200)) for i in range(len(create_movies))]
        conversion_options_testing_matrix = [
            dict(external_mode=False, stub_test=True, chunk_data=i) for i in [True, False]
        ]
        for conv_ops in conversion_options_testing_matrix:
            assert_nwbfile_conversion(
                converter=movie_converter, nwbfile_path=nwbfile_path, starting_times=starting_times, **conv_ops
            )


def test_conversion_external_mode(movie_converter, nwbfile_path):
    if HAVE_OPENCV:
        assert_nwbfile_conversion(converter=movie_converter, nwbfile_path=nwbfile_path, external_mode=True)
