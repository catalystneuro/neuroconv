import unittest
from datetime import datetime
from pathlib import Path

from hdmf.testing import TestCase
from pynwb import NWBHDF5IO

from neuroconv.tools import deploy_process

from ..setup_paths import ECEPHY_DATA_PATH as DATA_PATH
from ..setup_paths import OUTPUT_PATH


class TestYAMLConversionSpecification(TestCase):
    test_folder = OUTPUT_PATH

    def test_run_conversion_from_yaml_cli(self):
        path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification.yml"
        deploy_process(
            command=(
                f"neuroconv {yaml_file_path} "
                f"--data-folder-path {DATA_PATH} --output-folder-path {self.test_folder} --overwrite"
            )
        )

        nwbfile_path = self.test_folder / "example_converter_spec_1.nwb"
        assert nwbfile_path.exists(), f"`run_conversion_from_yaml` failed to create the file at '{nwbfile_path}'! "
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert nwbfile.session_description == "Subject navigating a Y-shaped maze."
            assert "Created using NeuroConv" in nwbfile.source_script
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
            assert "Created using NeuroConv" in nwbfile.source_script
            assert nwbfile.lab == "My Lab"
            assert nwbfile.institution == "My Institution"
            assert nwbfile.session_start_time == datetime.fromisoformat("2020-10-10T21:19:09+00:00")
            assert nwbfile.subject.subject_id == "002"

        nwbfile_path = self.test_folder / "example_converter_spec_3.nwb"
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

    def test_run_conversion_from_yaml_default_nwbfile_name(self):
        self.test_folder = self.test_folder / "test_organize"
        self.test_folder.mkdir(exist_ok=True)
        path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification_missing_nwbfile_names.yml"
        deploy_process(
            command=(
                f"neuroconv {yaml_file_path} "
                f"--data-folder-path {DATA_PATH} --output-folder-path {self.test_folder} --overwrite"
            )
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


if __name__ == "__main__":
    unittest.main()
