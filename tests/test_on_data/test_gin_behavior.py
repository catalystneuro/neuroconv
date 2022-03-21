import tempfile
import unittest
import os
from pathlib import Path
from datetime import datetime

import pytest
import numpy as np
from pynwb import NWBHDF5IO
from nwb_conversion_tools import NWBConverter, MovieInterface
from nwb_conversion_tools.utils import load_dict_from_file


# Load the configuration for the data tests
test_config_dict = load_dict_from_file(Path(__file__).parent / "gin_test_config.json")

#  GIN dataset: https://gin.g-node.org/CatalystNeuro/behavior_testing_data
if os.getenv("CI"):
    LOCAL_PATH = Path(".")  # Must be set to "." for CI
    print("Running GIN tests on Github CI!")
else:
    # Override LOCAL_PATH in the `gin_test_config.json` file to a point on your system that contains the dataset folder
    # Use DANDIHub at hub.dandiarchive.org for open, free use of data found in the /shared/catalystneuro/ directory
    LOCAL_PATH = Path(test_config_dict["LOCAL_PATH"])
    print("Running GIN tests locally!")
BEHAVIOR_DATA_PATH = LOCAL_PATH / "behavior_testing_data"
HAVE_BEHAVIOR_DATA = BEHAVIOR_DATA_PATH.exists()

if test_config_dict["SAVE_OUTPUTS"]:
    OUTPUT_PATH = LOCAL_PATH / "example_nwb_output"
    OUTPUT_PATH.mkdir(exist_ok=True)
else:
    OUTPUT_PATH = Path(tempfile.mkdtemp())

if not HAVE_BEHAVIOR_DATA:
    pytest.fail(f"No oephys_testing_data folder found in location: {BEHAVIOR_DATA_PATH}!")


class TestMovieDataNwbConversions(unittest.TestCase):
    savedir = OUTPUT_PATH

    def setUp(self) -> None:
        self.movie_files = list((BEHAVIOR_DATA_PATH / "videos" / "CFR").iterdir())
        self.nwb_converter = self.create_movie_converter()
        self.nwbfile_path = os.path.join(self.savedir, "movie_test.nwb")

    def create_movie_converter(self):
        class MovieTestNWBConverter(NWBConverter):
            data_interface_classes = dict(Movie=MovieInterface)

        source_data = dict(Movie=dict(file_paths=self.movie_files))
        return MovieTestNWBConverter(source_data)

    def get_metadata(self):
        metadata = self.nwb_converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S"))
        return metadata

    def test_movie_starting_times(self):
        starting_times = [np.float(np.random.randint(200)) for i in range(len(self.movie_files))]
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

    def test_movie_starting_times_none_duplicate(self):
        """When all movies go in one ImageSeries container, starting times should be assumed 0.0"""
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
            assert movie_interface_name in mod
            assert mod[movie_interface_name].starting_time == 0.0

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
        starting_times = [np.float(np.random.randint(200)) for i in range(len(self.movie_files))]
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

    def test_movie_external_mode(self):
        starting_times = [np.float(np.random.randint(200)) for i in range(len(self.movie_files))]
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

    def test_movie_duplicate_kwargs_external(self):
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
        starting_times = [np.float(np.random.randint(200)) for i in range(len(self.movie_files))]
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
