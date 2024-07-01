"""
This file is hidden from normal pytest globbing by not including 'test' in the filename.

Instead, the tests must be invoked directly from the file. This is designed mostly for use in the GitHub Actions.

To allow this test to work, the developer must create a folder on the outer level of their personal Google Drive
called 'testing_rclone_with_config' which contains a single subfolder 'ci_tests'
with example text file 'test_text_file.txt' containing the content
"This is a test file for the Rclone (with config) docker image hosted on NeuroConv!".

Then the developer must install Rclone and call `rclone config` to generate tokens in their own `rclone.conf` file.
The developer can easily find the location of the config file on their system using `rclone config file`.
"""

import os
import unittest
from datetime import datetime
from pathlib import Path

import pytest
from hdmf.testing import TestCase

from neuroconv.tools import deploy_process

from .test_on_data.setup_paths import OUTPUT_PATH

RCLONE_DRIVE_ACCESS_TOKEN = os.getenv("RCLONE_DRIVE_ACCESS_TOKEN")
RCLONE_DRIVE_REFRESH_TOKEN = os.getenv("RCLONE_DRIVE_REFRESH_TOKEN")
RCLONE_EXPIRY_TOKEN = os.getenv("RCLONE_EXPIRY_TOKEN")


@pytest.mark.skipIf(RCLONE_DRIVE_ACCESS_TOKEN is None, reason="The Rclone Google Drive token has not been specified.")
class TestRcloneWithConfig(TestCase):
    test_folder = OUTPUT_PATH / "rclone_tests"
    test_config_file = test_folder / "rclone.conf"

    def setUp(self):
        self.test_folder.mkdir(exist_ok=True)

        # Pretend as if .conf file already exists on the system (created via interactive `rclone config` command)
        token_dictionary = dict(
            access_token=RCLONE_DRIVE_ACCESS_TOKEN,
            token_type="Bearer",
            refresh_token=RCLONE_DRIVE_REFRESH_TOKEN,
            expiry=RCLONE_EXPIRY_TOKEN,
        )
        token_string = str(token_dictionary).replace("'", '"').replace(" ", "")
        rclone_config_contents = [
            "[test_google_drive_remote]\n",
            "type = drive\n",
            "scope = drive\n",
            f"token = {token_string}\n",
            "team_drive = \n",
            "\n",
        ]
        with open(path=test_config_file, mode="w") as io:
            io.writelines(rclone_config_contents)

    def test_rclone_with_config(self):
        path_to_test_yml_files = Path(__file__).parent / "test_on_data" / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification.yml"

        with open(path=test_config_file, mode="r") as io:
            rclone_config_file_stream = io.read()

        os.environ["RCLONE_CONFIG"] = rclone_config_file_stream
        os.environ["RCLONE_COMMAND"] = (
            f"rclone copy test_google_drive_remote:testing_rclone_with_config {self.test_folder}"
        )

        output = deploy_process(
            command=(
                "docker run -t "
                f"--volume {self.test_folder}:{self.test_folder} "
                '-e RCLONE_CONFIG="$RCLONE_CONFIG" '
                '-e RCLONE_COMMAND="$RCLONE_COMMAND" '
                "ghcr.io/catalystneuro/neuroconv:rclone_with_config"
            ),
            catch_output=True,
        )
        print(output)

        testing_file_path = self.test_folder / "testing_rclone_with_config" / "ci_tests" / "test_text_file.txt"
        assert testing_file_path.is_file()

        with open(path=testing_file_path, mode="r") as io:
            file_content = io.read()
            assert file_content == "This is a test file for the Rclone (with config) docker image hosted on NeuroConv!"
