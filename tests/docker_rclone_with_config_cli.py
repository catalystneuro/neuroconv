"""
This file is hidden from normal pytest globbing by not including 'test' in the filename.

Instead, the tests must be invoked directly from the file. This is designed mostly for use in the GitHub Actions.
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
class TestLatestDockerYAMLConversionSpecification(TestCase):
    test_folder = OUTPUT_PATH
    test_config_file = test_folder / "rclone.conf"

    def setUp(self):
        # Pretend as if .conf file already exists on the system (created via interactive `rclone config` command)
        token_dictionary = dict(
            access_token=RCLONE_DRIVE_ACCESS_TOKEN,
            token_type="Bearer",
            refresh_token=RCLONE_DRIVE_REFRESH_TOKEN,
            expiry=RCLONE_EXPIRY_TOKEN,
        )
        token_string = str(token_dictionary).replace("'", '"').replace(" ", "")
        rclone_config_contents = [
            "[test]\n",
            "type = drive\n",
            "scope = drive\n",
            f"token = {token_string}\n",
            "team_drive = \n",
            "\n",
        ]
        with open(path=test_config_file, mode="w") as io:
            io.writelines(rclone_config_contents)

    def test_run_conversion_from_yaml_cli(self):
        path_to_test_yml_files = Path(__file__).parent / "test_on_data" / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification.yml"

        with open(path=test_config_file, mode="r") as io:
            rclone_config_file_stream = io.read()

        os.environ["RCLONE_CONFIG"] = rclone_config_file_stream

        output = deploy_process(
            command=(
                "docker run -t "
                f"--volume {self.source_volume}:{self.source_volume} "
                f"--volume {self.test_folder}:{self.test_folder} "
                '-e RCLONE_CONFIG="$RCLONE_CONFIG" '
                "ghcr.io/catalystneuro/neuroconv:rclone_with_config "
                "rclone cp "  # TODO
                "--drive-shared-with-me "
                # f"--data-folder-path {self.source_volume}/{DATA_PATH} --output-folder-path {self.test_folder} --overwrite"
            ),
            catch_output=True,
        )
        print(output)

        # TODO: assert file downloaded from the Drive just fine
