import os
from pathlib import Path
from tempfile import mkdtemp
from shutil import rmtree
from jsonschema import validate, RefResolver
from datetime import datetime

from hdmf.testing import TestCase
import pytest
from pynwb import NWBHDF5IO

from nwb_conversion_tools.utils.json_schema import load_dict_from_file
from nwb_conversion_tools.utils.conversion_tools import run_conversion_from_yaml

# Load data test configuration
test_config_dict = load_dict_from_file("./tests/test_on_data/gin_test_config.json")

# GIN dataset: https://gin.g-node.org/NeuralEnsemble/ephy_testing_data
if os.getenv("CI"):
    LOCAL_PATH = Path(".")  # Must be set to "." for CI
    print("Running GIN tests on Github CI!")
else:
    # Override the LOCAL_PATH to a point on your local system that contains the dataset folder
    # Use DANDIHub at hub.dandiarchive.org for open, free use of data found in the /shared/catalystneuro/ directory
    LOCAL_PATH = Path(test_config_dict["LOCAL_PATH"])
    print("Running GIN tests locally!")

DATA_PATH = LOCAL_PATH / "ephy_testing_data"
HAVE_DATA = DATA_PATH.exists()

if test_config_dic["SAVE_OUTPUTS"]:
    OUTPUT_PATH = LOCAL_PATH / "example_yaml_output"
    OUTPUT_PATH.mkdir(exist_ok=True)
else:
    OUTPUT_PATH = Path(mkdtemp())

DATA_PATH = LOCAL_PATH / "ephy_testing_data"
HAVE_DATA = DATA_PATH.exists()

if not HAVE_DATA:
    pytest.fail(f"No ephy_testing_data folder found in location: {DATA_PATH}!")


class TestYAMLConversionSpecification(TestCase):
    test_folder = OUTPUT_PATH

    def test_validate_example_specification(self):
        path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification.yml"
        schema_folder = path_to_test_yml_files.parent.parent.parent / "nwb_conversion_tools" / "schemas"
        specification_schema = load_dict_from_file(
            file_path=schema_folder / "yaml_conversion_specification_schema.json"
        )
        validate(
            instance=load_dict_from_file(file_path=yaml_file_path),
            schema=load_dict_from_file(file_path=schema_folder / "yaml_conversion_specification_schema.json"),
            resolver=RefResolver(base_uri="file://" + str(schema_folder) + "/", referrer=specification_schema),
        )

    def test_run_conversion_from_yaml(self):
        path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification.yml"
        run_conversion_from_yaml(
            specification_file_path=yaml_file_path,
            data_folder=DATA_PATH,
            output_folder=self.test_folder,
            overwrite=True,
        )

        with NWBHDF5IO(path=self.test_folder / "example_converter_spec_1.nwb", mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-09T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "1"
            assert "ElectricalSeries_raw" in nwbfile.acquisition
        with NWBHDF5IO(path=self.test_folder / "example_converter_spec_2.nwb", mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-10T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "002"
        with NWBHDF5IO(path=self.test_folder / "example_converter_spec_3.nwb", mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "no description"
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-11T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "Subject Name"
            assert "spike_times" in nwbfile.units

    def test_run_conversion_from_yaml_default_nwbfile_name(self):
        self.test_folder = self.test_folder / "test_organize"
        self.test_folder.mkdir(exist_ok=True)
        path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification_missing_nwbfile_names.yml"
        run_conversion_from_yaml(
            specification_file_path=yaml_file_path,
            data_folder=DATA_PATH,
            output_folder=self.test_folder,
            overwrite=True,
        )

        with NWBHDF5IO(path=self.test_folder / "sub-Mouse_1_ses-20201009T211909.nwb", mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-09T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "Mouse 1"
            assert "ElectricalSeries_raw" in nwbfile.acquisition

        with NWBHDF5IO(path=self.test_folder / "example_defined_name.nwb", mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-10T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "MyMouse002"

        with NWBHDF5IO(path=self.test_folder / "sub-Subject_Name_ses-20201011T211909.nwb", mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "no description"
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-11T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "Subject Name"
            assert "spike_times" in nwbfile.units

    def test_run_conversion_from_yaml_no_nwbfile_name_or_other_metadata_assertion(self):
        self.test_folder = self.test_folder / "test_organize_no_nwbfile_name_or_other_metadata"
        self.test_folder.mkdir(exist_ok=True)
        path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification_no_nwbfile_name_or_other_metadata.yml"

        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                f"Not enough metadata available to assign name to {str(self.test_folder / 'temp_nwbfile_name_1.nwb')}!"
            ),
        ):
            run_conversion_from_yaml(
                specification_file_path=yaml_file_path,
                data_folder=DATA_PATH,
                output_folder=self.test_folder,
                overwrite=True,
            )
