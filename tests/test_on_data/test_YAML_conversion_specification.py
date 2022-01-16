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

# Path to dataset downloaded from https://gin.g-node.org/NeuralEnsemble/ephy_testing_data
#   ophys: TODO
#   icephys: TODO
if os.getenv("CI"):
    LOCAL_PATH = Path(".")  # Must be set to "." for CI
    print("Running GIN tests on Github CI!")
else:
    LOCAL_PATH = Path("/home/jovyan/")  # Override this on personal device for local testing
    print("Running GIN tests locally!")

DATA_PATH = LOCAL_PATH / "ephy_testing_data"
HAVE_DATA = DATA_PATH.exists()

if not HAVE_DATA:
    pytest.fail(f"No ephy_testing_data folder found in location: {DATA_PATH}!")


class TestYAMLConversionSpecification(TestCase):
    def setUp(self):
        self.test_folder = Path(mkdtemp())

    def tearDown(self):
        rmtree(path=self.test_folder)

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
        path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification_no_nwbfile_name.yml"
        run_conversion_from_yaml(
            specification_file_path=yaml_file_path,
            data_folder=DATA_PATH,
            output_folder=self.test_folder,
            overwrite=True,
        )

        subject_id = "Mouse 1"
        subject_id_file_name = subject_id.replace(" ", "_")
        session_start_time = "2020-10-09T21:19:09+00:00"
        with NWBHDF5IO(path=self.test_folder / f"{subject_id_file_name}_{session_start_time}.nwb", mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat(session_start_time)
            assert nwbfile.subject.subject_id == subject_id
            assert "ElectricalSeries_raw" in nwbfile.acquisition

        subject_id = "MyMouse002"
        session_start_time = "2020-10-10T21:19:09+00:00"
        with NWBHDF5IO(path=self.test_folder / f"{subject_id}_{session_start_time}.nwb", mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat(session_start_time)
            assert nwbfile.subject.subject_id == subject_id

        subject_id = "Subject Name"
        subject_id_file_name = subject_id.replace(" ", "_")
        session_start_time = "2020-10-11T21:19:09+00:00"
        with NWBHDF5IO(path=self.test_folder / f"{subject_id_file_name}_{session_start_time}.nwb", mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "no description"
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat(session_start_time)
            assert nwbfile.subject.subject_id == subject_id
            assert "spike_times" in nwbfile.units

    def test_run_conversion_from_yaml_default_nwbfile_name_assertion(self):
        path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / f"GIN_conversion_specification_no_nwbfile_name_or_other_metadata.yml"
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "If not specifying an explicit name for the NWBFile ('nwbfile_name'), then both "
                "metadata['Subject']['subject_id'] and metadata['NWBFile']['session_start_time'] are required!"
            ),
        ):
            run_conversion_from_yaml(
                specification_file_path=yaml_file_path,
                data_folder=DATA_PATH,
                output_folder=self.test_folder,
                overwrite=True,
            )
