import unittest
from datetime import datetime
from pathlib import Path

import pytest
from hdmf.testing import TestCase
from jsonschema import validate
from pynwb import NWBHDF5IO
from referencing import Registry, Resource

from neuroconv import run_conversion_from_yaml
from neuroconv.utils import load_dict_from_file

from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
from ..setup_paths import ECEPHY_DATA_PATH as DATA_PATH


@pytest.mark.parametrize(
    "fname",
    [
        "GIN_conversion_specification.yml",
        "GIN_conversion_specification_dandi_upload.yml",
        "GIN_conversion_specification_missing_nwbfile_names.yml",
        "GIN_conversion_specification_no_nwbfile_name_or_other_metadata.yml",
        "GIN_conversion_specification_videos.yml",
    ],
)
def test_validate_example_specifications(fname):
    path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
    schema_folder = path_to_test_yml_files.parent.parent.parent.parent / "src" / "neuroconv" / "schemas"

    # Load schemas
    specification_schema = load_dict_from_file(file_path=schema_folder / "yaml_conversion_specification_schema.json")
    metadata_schema = load_dict_from_file(file_path=schema_folder / "metadata_schema.json")

    # The yaml specification references the metadata schema, so we need to load it into the registry
    registry = Registry().with_resource("metadata_schema.json", Resource.from_contents(metadata_schema))

    yaml_file_path = path_to_test_yml_files / fname
    validate(
        instance=load_dict_from_file(file_path=yaml_file_path),
        schema=specification_schema,
        registry=registry,
    )


def test_run_conversion_from_yaml():
    path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
    yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification.yml"
    run_conversion_from_yaml(
        specification_file_path=yaml_file_path,
        data_folder_path=DATA_PATH,
        output_folder_path=OUTPUT_PATH,
        overwrite=True,
    )

    nwbfile_path_1 = OUTPUT_PATH / "example_converter_spec_1.nwb"
    assert nwbfile_path_1.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path_1}'!"
    with NWBHDF5IO(path=nwbfile_path_1, mode="r") as io:
        nwbfile = io.read()
        assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
        assert "Created using NeuroConv" in nwbfile.source_script
        assert nwbfile.lab == "My Lab"
        assert nwbfile.institution == "My Institution"
        assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-09T21:19:09+00:00")
        assert nwbfile.subject.subject_id == "1"
        assert "ElectricalSeriesAP" in nwbfile.acquisition

    nwbfile_path_2 = OUTPUT_PATH / "example_converter_spec_2.nwb"
    assert nwbfile_path_2.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path_2}'!"
    with NWBHDF5IO(path=nwbfile_path_2, mode="r") as io:
        nwbfile = io.read()
        assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
        assert "Created using NeuroConv" in nwbfile.source_script
        assert nwbfile.lab == "My Lab"
        assert nwbfile.institution == "My Institution"
        assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-10T21:19:09+00:00")
        assert nwbfile.subject.subject_id == "002"

    nwbfile_path_3 = OUTPUT_PATH / "example_converter_spec_3.nwb"
    assert nwbfile_path_3.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path_3}'!"
    with NWBHDF5IO(path=nwbfile_path_3, mode="r") as io:
        nwbfile = io.read()
        assert nwbfile.session_description == ""
        assert "Created using NeuroConv" in nwbfile.source_script
        assert nwbfile.lab == "My Lab"
        assert nwbfile.institution == "My Institution"
        assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-11T21:19:09+00:00")
        assert nwbfile.subject.subject_id == "Subject Name"
        assert "spike_times" in nwbfile.units


class TestYAMLConversionSpecification(TestCase):
    test_folder = OUTPUT_PATH

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

        nwbfile_path = self.test_folder / "sub-Mouse-1_ses-20201009T211909.nwb"
        assert nwbfile_path.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path}'! "
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert "Created using NeuroConv" in nwbfile.source_script
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-09T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "Mouse 1"
            assert "ElectricalSeriesAP" in nwbfile.acquisition

        nwbfile_path = self.test_folder / "sub-Mouse-1_ses-20201109T211909.nwb"
        assert nwbfile_path.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path}'! "
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert "Created using NeuroConv" in nwbfile.source_script
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-11-09T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "Mouse 1"
            assert "ElectricalSeriesAP" in nwbfile.acquisition

        nwbfile_path = self.test_folder / "example_defined_name.nwb"
        assert nwbfile_path.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path}'! "
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert "Created using NeuroConv" in nwbfile.source_script
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-10T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "MyMouse002"

        nwbfile_path = self.test_folder / "sub-Subject-Name_ses-20201011T211909.nwb"
        assert nwbfile_path.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path}'! "
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == ""
            assert "Created using NeuroConv" in nwbfile.source_script
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

    def test_run_conversion_from_yaml_on_behavior(self):
        path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification_videos.yml"
        run_conversion_from_yaml(
            specification_file_path=yaml_file_path,
            data_folder_path=BEHAVIOR_DATA_PATH,
            output_folder_path=self.test_folder,
            overwrite=True,
        )


if __name__ == "__main__":
    unittest.main()
