import os
from datetime import datetime
from pathlib import Path
from unittest import TestCase

from neuroconv.tools.data_transfers import (
    deploy_conversion_on_ec2,
    estimate_s3_conversion_cost,
    estimate_total_conversion_runtime,
    submit_aws_batch_job,
)

from .test_on_data.setup_paths import OUTPUT_PATH

RCLONE_DRIVE_ACCESS_TOKEN = os.environ["RCLONE_DRIVE_ACCESS_TOKEN"]
RCLONE_DRIVE_REFRESH_TOKEN = os.environ["RCLONE_DRIVE_REFRESH_TOKEN"]
RCLONE_EXPIRY_TOKEN = os.environ["RCLONE_EXPIRY_TOKEN"]


def test_estimate_s3_conversion_cost_standard():
    test_sizes = [
        1,
        100,
        1e3,  # 1 GB
        1e5,  # 100 GB
        1e6,  # 1 TB
        1e7,  # 10 TB
        1e8,  # 100 TB
    ]
    results = [estimate_s3_conversion_cost(total_mb=total_mb) for total_mb in test_sizes]
    assert results == [
        2.9730398740210563e-15,  # 1 MB
        2.973039874021056e-11,  # 100 MB
        2.9730398740210564e-09,  # 1 GB
        2.9730398740210563e-05,  # 100 GB
        0.002973039874021056,  # 1 TB
        0.2973039874021056,  # 10 TB
        29.73039874021056,  # 100 TB
    ]


def test_estimate_total_conversion_runtime():
    test_sizes = [
        1,
        100,
        1e3,  # 1 GB
        1e5,  # 100 GB
        1e6,  # 1 TB
        1e7,  # 10 TB
        1e8,  # 100 TB
    ]
    results = [estimate_total_conversion_runtime(total_mb=total_mb) for total_mb in test_sizes]
    assert results == [
        0.12352941176470589,
        12.352941176470589,
        123.52941176470588,
        12352.94117647059,
        123529.41176470589,
        1235294.1176470588,
        12352941.176470589,
    ]


def test_submit_aws_batch_job():
    job_name = "test_submit_aws_batch_job"
    docker_image = "ubuntu:latest"
    command = "echo 'Testing NeuroConv AWS Batch submission."

    submit_aws_batch_job(
        job_name=job_name,
        docker_image=docker_image,
        command=command,
    )


def test_submit_aws_batch_job_with_dependencies():
    job_name_1 = "test_submit_aws_batch_job_with_dependencies_1"
    docker_image = "ubuntu:latest"
    command_1 = "echo 'Testing NeuroConv AWS Batch submission."

    info = submit_aws_batch_job(
        job_name=job_name_1,
        docker_image=docker_image,
        command=command_1,
    )
    job_submission_info = info["job_submission_info"]

    job_name_2 = "test_submit_aws_batch_job_with_dependencies_1"
    command_2 = "echo 'Testing NeuroConv AWS Batch submission with dependencies."
    job_dependencies = [{"jobId": job_submission_info["jobId"], "type": "SEQUENTIAL"}]
    submit_aws_batch_job(
        job_name=job_name_2,
        docker_image=docker_image,
        command=command_2,
        job_dependencies=job_dependencies,
    )


class TestDeployConversionOnEC2(TestCase):
    """
    In order to run this test in CI successfully, whoever sets the Rclone credentials must use the following setup.

    1) On your Google Drive, create a folder named 'test_neuroconv_ec2_batch_deployment'
    2) Create a subfolder there named 'test_rclone_source_data'
    3) Copy the 'spikelgx/Noise4Sam' and 'phy/phy_example_0' folders from the 'ephy_testing_data' into that subfolder
    4) Locally, run `rclone config`, then copy the relevant token values into GitHub Action secrets
    """

    test_folder = OUTPUT_PATH / "deploy_conversion_on_ec2_tests"

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

    def test_deploy_conversion_on_ec2(self):
        path_to_test_yml_files = Path(__file__).parent.parent / "test_on_data" / "conversion_specifications"
        yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification.yml"

        transfer_commands = (
            "rclone copy test_google_drive_remote:test_neuroconv_ec2_batch_deployment {self.test_folder} "
            "--verbose --progress --config ./rclone.conf"
        )

        date_tag = datetime.now().strftime("%y%m%d")
        efs_volume_name = f"neuroconv_ci_tests_{date_tag}"

        deploy_conversion_on_ec2(
            specification_file_path=yaml_file_path,
            transfer_commands=transfer_commands,
            transfer_config_file_path=self.test_config_file,
            efs_volume_name=efs_volume_name,
            dandiset_id="200560",
        )

        # assert that EFS volume was cleaned up after some extended wait time
