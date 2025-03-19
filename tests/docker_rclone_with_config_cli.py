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

from hdmf.testing import TestCase

from neuroconv.tools import deploy_process

from .test_on_data.setup_paths import OUTPUT_PATH

RCLONE_DRIVE_ACCESS_TOKEN = os.environ["RCLONE_DRIVE_ACCESS_TOKEN"]
RCLONE_DRIVE_REFRESH_TOKEN = os.environ["RCLONE_DRIVE_REFRESH_TOKEN"]
RCLONE_EXPIRY_TOKEN = os.environ["RCLONE_EXPIRY_TOKEN"]


class TestRcloneWithConfig(TestCase):
    test_folder = OUTPUT_PATH / "rclone_tests"

    # Save the .conf file in a separate folder to avoid the potential of the container using the locally mounted file
    adjacent_folder = OUTPUT_PATH / "rclone_conf"
    test_config_file = adjacent_folder / "rclone.conf"

    def setUp(self):
        self.test_folder.mkdir(exist_ok=True)
        self.adjacent_folder.mkdir(exist_ok=True)

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
        with open(file=self.test_config_file, mode="w") as io:
            io.writelines(rclone_config_contents)

    def test_direct_usage_of_rclone_with_config(self):
        with open(file=self.test_config_file, mode="r") as io:
            rclone_config_file_stream = io.read()

        os.environ["RCLONE_CONFIG"] = rclone_config_file_stream
        os.environ["RCLONE_COMMAND"] = (
            f"rclone copy test_google_drive_remote:testing_rclone_with_config {self.test_folder} "
            "--verbose --progress --config ./rclone.conf"
        )

        command = (
            "docker run -t "
            f"--volume {self.test_folder}:{self.test_folder} "
            '-e RCLONE_CONFIG="$RCLONE_CONFIG" '
            '-e RCLONE_COMMAND="$RCLONE_COMMAND" '
            "ghcr.io/catalystneuro/rclone_with_config:latest"
        )
        deploy_process(command=command)

        # The .conf file created inside the container should not be viewable outside the running container
        # (it was not saved to mounted location)

        test_folder_contents_after_call = list(self.test_folder.iterdir())
        assert len(test_folder_contents_after_call) != 0, f"Test folder {self.test_folder} is empty!"

        testing_file_path = self.test_folder / "ci_tests" / "test_text_file.txt"
        assert testing_file_path.is_file(), "The specific test transfer file does not exist!"

        with open(file=testing_file_path, mode="r") as io:
            file_content = io.read()
            assert (
                file_content == "This is a test file for the Rclone (with config) docker image hosted on NeuroConv!"
            ), "The file content does not match expectations!"
