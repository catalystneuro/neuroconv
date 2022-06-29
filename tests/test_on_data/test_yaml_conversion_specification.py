import sys
import unittest
from pathlib import Path
from jsonschema import validate, RefResolver
from datetime import datetime

from hdmf.testing import TestCase
from pynwb import NWBHDF5IO

from nwb_conversion_tools import run_conversion_from_yaml
from nwb_conversion_tools.utils import load_dict_from_file

from .setup_paths import ECEPHY_DATA_PATH as DATA_PATH
from .setup_paths import OUTPUT_PATH


class TestYAMLConversionSpecification(TestCase):
    test_folder = OUTPUT_PATH

    def test_validate_example_specification(self):
        path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification.yml"
        schema_folder = path_to_test_yml_files.parent.parent.parent / "src" / "nwb_conversion_tools" / "schemas"
        specification_schema = load_dict_from_file(
            file_path=schema_folder / "yaml_conversion_specification_schema.json"
        )
        sys_uri_base = "file://"
        if sys.platform.startswith("win32"):
            sys_uri_base = "file:/"
        validate(
            instance=load_dict_from_file(file_path=yaml_file_path),
            schema=load_dict_from_file(file_path=schema_folder / "yaml_conversion_specification_schema.json"),
            resolver=RefResolver(base_uri=sys_uri_base + str(schema_folder) + "/", referrer=specification_schema),
        )

    def test_run_conversion_from_yaml(self):
        path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification.yml"
        run_conversion_from_yaml(
            specification_file_path=yaml_file_path,
            data_folder_path=DATA_PATH,
            output_folder_path=self.test_folder,
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
            data_folder_path=DATA_PATH,
            output_folder_path=self.test_folder,
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
                data_folder_path=DATA_PATH,
                output_folder_path=self.test_folder,
                overwrite=True,
            )


if __name__ == "__main__":
    unittest.main()
