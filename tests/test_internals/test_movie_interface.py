import numpy as np
from tempfile import mkdtemp
from shutil import rmtree
from pathlib import Path
from itertools import product

from pynwb import NWBHDF5IO
from hdmf.testing import TestCase

from nwb_conversion_tools import (
    NWBConverter,
    MovieInterface,
)

try:
    import cv2

    HAVE_OPENCV = True
except ImportError:
    HAVE_OPENCV = False


class TestMovieInterface(TestCase):
    def setUp(self):
        self.test_dir = Path(mkdtemp())

    def tearDown(self):
        rmtree(self.test_dir)

    def test_movie_interface(self):
        if HAVE_OPENCV:
            movie_file = self.test_dir / "test1.avi"
            nwbfile_path = str(self.test_dir / "test1.nwb")
            (nf, nx, ny) = (50, 640, 480)
            writer = cv2.VideoWriter(
                filename=str(movie_file),
                apiPreference=None,
                fourcc=cv2.VideoWriter_fourcc("M", "J", "P", "G"),
                fps=25,
                frameSize=(ny, nx),
                params=None,
            )
            for k in range(nf):
                writer.write(np.random.randint(0, 255, (nx, ny, 3)).astype("uint8"))
            writer.release()

            class MovieTestNWBConverter(NWBConverter):
                data_interface_classes = dict(Movie=MovieInterface)

            source_data = dict(Movie=dict(file_paths=[movie_file]))
            converter = MovieTestNWBConverter(source_data)
            metadata = converter.get_metadata()

            # Default usage
            converter.run_conversion(metadata=metadata, nwbfile_path=nwbfile_path, overwrite=True)

            # This conversion option operates independently of all others
            converter.run_conversion(
                metadata=metadata,
                nwbfile_path=nwbfile_path,
                overwrite=True,
                conversion_options=dict(Movie=dict(starting_times=[123.0])),
            )

            # These conversion options do not operate independently, so test them jointly
            conversion_options_testing_matrix = [
                dict(Movie=dict(external_mode=False, stub_test=x, chunk_data=y))
                for x, y in product([True, False], repeat=2)
            ]
            for conversion_options in conversion_options_testing_matrix:
                converter.run_conversion(
                    metadata=metadata, nwbfile_path=nwbfile_path, overwrite=True, conversion_options=conversion_options
                )

            module_name = "TestModule"
            module_description = "This is a test module."
            nwbfile = converter.run_conversion(metadata=metadata, save_to_file=False)

            # TODO: each of the asserts below here should be broken off into a separate test call
            # Much of the detail above can be included into either setUp or setUpClass
            assert f"Video: {Path(movie_file).stem}" in nwbfile.acquisition
            nwbfile = converter.run_conversion(
                metadata=metadata,
                save_to_file=False,
                nwbfile=nwbfile,
                conversion_options=dict(Movie=dict(module_name=module_name)),
            )
            assert module_name in nwbfile.modules
            nwbfile = converter.run_conversion(
                metadata=metadata,
                save_to_file=False,
                conversion_options=dict(Movie=dict(module_name=module_name, module_description=module_description)),
            )
            assert module_name in nwbfile.modules and nwbfile.modules[module_name].description == module_description

            metadata.update(
                Behavior=dict(
                    Movies=[
                        dict(
                            name="CustomName",
                            description="CustomDescription",
                            unit="CustomUnit",
                            resolution=12.3,
                            comments="CustomComments",
                        )
                    ]
                )
            )
            converter.run_conversion(metadata=metadata, nwbfile_path=nwbfile_path, overwrite=True)
            with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
                nwbfile = io.read()
                custom_name = metadata["Behavior"]["Movies"][0]["name"]
                assert custom_name in nwbfile.acquisition
                assert metadata["Behavior"]["Movies"][0]["description"] == nwbfile.acquisition[custom_name].description
                assert metadata["Behavior"]["Movies"][0]["comments"] == nwbfile.acquisition[custom_name].comments

            converter.run_conversion(
                metadata=metadata,
                nwbfile_path=nwbfile_path,
                overwrite=True,
                conversion_options=dict(Movie=dict(external_mode=False, stub_test=True)),
            )
            with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
                nwbfile = io.read()
                custom_name = metadata["Behavior"]["Movies"][0]["name"]
                assert custom_name in nwbfile.acquisition
                assert metadata["Behavior"]["Movies"][0]["description"] == nwbfile.acquisition[custom_name].description
                assert metadata["Behavior"]["Movies"][0]["unit"] == nwbfile.acquisition[custom_name].unit
                assert metadata["Behavior"]["Movies"][0]["resolution"] == nwbfile.acquisition[custom_name].resolution
                assert metadata["Behavior"]["Movies"][0]["comments"] == nwbfile.acquisition[custom_name].comments
