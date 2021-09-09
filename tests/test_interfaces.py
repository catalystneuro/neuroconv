from jsonschema import Draft7Validator
import numpy as np
from tempfile import mkdtemp
from shutil import rmtree
from pathlib import Path
from itertools import product

import pytest

try:
    import cv2

    HAVE_OPENCV = True
except ImportError:
    HAVE_OPENCV = False

from nwb_conversion_tools import NWBConverter, MovieInterface, RecordingTutorialInterface, interface_list


@pytest.mark.parametrize("data_interface", interface_list)
def test_interface_source_schema(data_interface):
    schema = data_interface.get_source_schema()
    Draft7Validator.check_schema(schema)


@pytest.mark.parametrize("data_interface", interface_list)
def test_interface_conversion_options_schema(data_interface):
    schema = data_interface.get_conversion_options_schema()
    Draft7Validator.check_schema(schema)


def test_tutorial_interfaces():
    class TutorialNWBConverter(NWBConverter):
        data_interface_classes = dict(
            RecordingTutorial=RecordingTutorialInterface,
            # SortingTutorial=SortingTutorialInterface
        )
    duration = 10.  # Seconds
    num_channels = 4
    sampling_frequency = 30000.  # Hz
    stub_test = True
    test_dir = Path(mkdtemp())
    output_file = str(test_dir / "TestTutorial.nwb")
    source_data = dict(
        RecordingTutorial=dict(
            duration=duration,
            num_channels=num_channels,
            sampling_frequency=sampling_frequency
        ),
        # SortingTutorial=dict(
        #     duration=duration,
        #     num_channels=num_channels,
        #     sampling_frequency=sampling_frequency
        # )
    )
    converter = TutorialNWBConverter(source_data=source_data)
    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_description"] = "NWB Conversion Tools tutorial."
    metadata["NWBFile"]["experimenter"] = ["My name"]
    metadata["Subject"] = dict(subject_id="Name of imaginary testing subject (required for DANDI upload)")
    conversion_options = dict(
        RecordingTutorial=dict(stub_test=stub_test),
        # TutorialSorting=dict()
    )
    converter.run_conversion(
        metadata=metadata,
        nwbfile_path=output_file,
        save_to_file=True,  # If False, this instead returns the NWBFile object in memory
        overwrite=True,  # If False, this appends an existing file
        conversion_options=conversion_options
    )


def test_movie_interface():
    if HAVE_OPENCV:
        test_dir = Path(mkdtemp())
        movie_file = test_dir / "test1.avi"
        nwbfile_path = str(test_dir / "test1.nwb")
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
        rmtree(test_dir)
