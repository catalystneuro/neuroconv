"""
This file is hidden from normal pytest globbing by not including 'test' in the filename.

Instead, the tests must be invoked directly from the file. This is designed mostly for use in the GitHub Actions.
"""

import os
import unittest
from datetime import datetime
from pathlib import Path

from hdmf.testing import TestCase
from pynwb import NWBHDF5IO

from neuroconv.tools import deploy_process

from .test_on_data.setup_paths import ECEPHY_DATA_PATH as DATA_PATH
from .test_on_data.setup_paths import OUTPUT_PATH


class TestLatestDockerYAMLConversionSpecification(TestCase):
    test_folder = OUTPUT_PATH
    tag = os.getenv("NEUROCONV_DOCKER_TESTS_TAG", "latest")
    source_volume = os.getenv("NEUROCONV_DOCKER_TESTS_SOURCE_VOLUME", "/home/runner/work/neuroconv")

    def test_run_conversion_from_yaml_cli(self):
        path_to_test_yml_files = Path(__file__).parent / "test_on_data" / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification.yml"

        output = deploy_process(
            command=(
                "docker run "
                f"--volume {self.source_volume}:{self.source_volume} "
                f"--volume {self.test_folder}:{self.test_folder} "
                "ghcr.io/catalystneuro/neuroconv:{self.tag} "
                f"-t neuroconv {yaml_file_path} "
                f"--data-folder-path {self.source_volume}/{DATA_PATH} --output-folder-path {self.test_folder} --overwrite"
            ),
            catch_output=True,
        )
        print(output)

        nwbfile_path = self.test_folder / "example_converter_spec_1.nwb"
        assert nwbfile_path.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path}'! "
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-09T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "1"
            assert "ElectricalSeriesAP" in nwbfile.acquisition

        nwbfile_path = self.test_folder / "example_converter_spec_2.nwb"
        assert nwbfile_path.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path}'! "
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-10T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "002"

        nwbfile_path = self.test_folder / "example_converter_spec_3.nwb"
        assert nwbfile_path.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path}'! "
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Auto-generated by neuroconv"
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-11T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "Subject Name"
            assert "spike_times" in nwbfile.units

    def test_run_conversion_from_yaml_variable(self):
        path_to_test_yml_files = Path(__file__).parent / "test_on_data" / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification.yml"

        with open(file=yaml_file_path, mode="r") as io:
            yaml_lines = io.readlines()

        yaml_string = "".join(yaml_lines)
        os.environ["NEUROCONV_YAML"] = yaml_string
        os.environ["NEUROCONV_DATA_PATH"] = self.source_volume + str(DATA_PATH)
        os.environ["NEUROCONV_OUTPUT_PATH"] = str(self.test_folder)

        output = deploy_process(
            command=(
                "docker run -t "
                f"--volume {self.source_volume}:{self.source_volume} "
                f"--volume {self.test_folder}:{self.test_folder} "
                '-e NEUROCONV_YAML="$NEUROCONV_YAML" '
                '-e NEUROCONV_DATA_PATH="$NEUROCONV_DATA_PATH" '
                '-e NEUROCONV_OUTPUT_PATH="$NEUROCONV_OUTPUT_PATH" '
                "ghcr.io/catalystneuro/neuroconv:yaml_variable"
            ),
            catch_output=True,
        )
        print(output)

        nwbfile_path = self.test_folder / "example_converter_spec_1.nwb"
        assert nwbfile_path.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path}'! "
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-09T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "1"
            assert "ElectricalSeriesAP" in nwbfile.acquisition

        nwbfile_path = self.test_folder / "example_converter_spec_2.nwb"
        assert nwbfile_path.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path}'! "
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-10T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "002"

        nwbfile_path = self.test_folder / "example_converter_spec_3.nwb"
        assert nwbfile_path.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path}'! "
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Auto-generated by neuroconv"
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-11T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "Subject Name"
            assert "spike_times" in nwbfile.units
