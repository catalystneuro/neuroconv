import datetime
import os
import time
import unittest

import boto3

from neuroconv.tools.aws import rclone_transfer_batch_job

from ..setup_paths import OUTPUT_PATH

_RETRY_STATES = ["RUNNABLE", "PENDING", "STARTING", "RUNNING"]


class TestRcloneTransferBatchJob(unittest.TestCase):
    """
    To allow this test to work, the developer must create a folder on the outer level of their personal Google Drive
    called 'testing_rclone_spikegl_and_phy' with the following structure:

    testing_rclone_spikeglx_and_phy
    ├── ci_tests
    ├──── spikeglx
    ├────── Noise4Sam_g0
    ├──── phy
    ├────── phy_example_0

    Where 'Noise4Sam' is from the 'spikeglx/Noise4Sam_g0' GIN ephys dataset and 'phy_example_0' is likewise from the
    'phy' folder of the same dataset.

    Then the developer must install Rclone and call `rclone config` to generate tokens in their own `rclone.conf` file.
    The developer can easily find the location of the config file on their system using `rclone config file`.
    """

    test_folder = OUTPUT_PATH / "aws_rclone_tests"
    test_config_file_path = test_folder / "rclone.conf"
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", None)
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", None)
    region = "us-east-2"
    efs_id = None

    def setUp(self):
        self.test_folder.mkdir(exist_ok=True)

        # Pretend as if .conf file already exists on the system (created via interactive `rclone config` command)
        token_dictionary = dict(
            access_token=os.environ["RCLONE_DRIVE_ACCESS_TOKEN"],
            token_type="Bearer",
            refresh_token=os.environ["RCLONE_DRIVE_REFRESH_TOKEN"],
            expiry=os.environ["RCLONE_EXPIRY_TOKEN"],
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
        with open(file=self.test_config_file_path, mode="w") as io:
            io.writelines(rclone_config_contents)

        self.efs_client = boto3.client(
            service_name="efs",
            region_name=self.region,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        )

    def tearDown(self) -> None:
        if self.efs_id is None:
            return None
        efs_client = self.efs_client

        # Cleanup EFS after testing is complete - must clear mount targets first, then wait before deleting the volume
        # TODO: cleanup job definitions? (since built daily)
        mount_targets = efs_client.describe_mount_targets(FileSystemId=self.efs_id)
        for mount_target in mount_targets["MountTargets"]:
            efs_client.delete_mount_target(MountTargetId=mount_target["MountTargetId"])

        time.sleep(60)
        efs_client.delete_file_system(FileSystemId=self.efs_id)

    def test_rclone_transfer_batch_job(self):
        region = self.region
        aws_access_key_id = self.aws_access_key_id
        aws_secret_access_key = self.aws_secret_access_key

        dynamodb_resource = boto3.resource(
            service_name="dynamodb",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        batch_client = boto3.client(
            service_name="batch",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        efs_client = self.efs_client

        rclone_command = (
            "rclone copy test_google_drive_remote:testing_rclone_spikeglx_and_phy /mnt/efs "
            "--verbose --progress --config ./rclone.conf"  # TODO: should just include this in helper function?
        )
        rclone_config_file_path = self.test_config_file_path

        today = datetime.datetime.now().date().isoformat()
        job_name = f"test_rclone_transfer_batch_job_{today}"
        efs_volume_name = "test_rclone_transfer_batch_efs"

        info = rclone_transfer_batch_job(
            rclone_command=rclone_command,
            job_name=job_name,
            efs_volume_name=efs_volume_name,
            rclone_config_file_path=rclone_config_file_path,
        )

        # Wait for AWS to process the job
        time.sleep(60)

        job_id = info["job_submission_info"]["jobId"]
        job = None
        max_retries = 10
        retry = 0
        while retry < max_retries:
            job_description_response = batch_client.describe_jobs(jobs=[job_id])
            assert job_description_response["ResponseMetadata"]["HTTPStatusCode"] == 200

            jobs = job_description_response["jobs"]
            assert len(jobs) == 1

            job = jobs[0]

            if job["status"] in _RETRY_STATES:
                retry += 1
                time.sleep(60)
            else:
                break

        # Check EFS specific details
        efs_volumes = efs_client.describe_file_systems()
        matching_efs_volumes = [
            file_system
            for file_system in efs_volumes["FileSystems"]
            for tag in file_system["Tags"]
            if tag["Key"] == "Name" and tag["Value"] == efs_volume_name
        ]
        assert len(matching_efs_volumes) == 1
        efs_volume = matching_efs_volumes[0]
        self.efs_id = efs_volume["FileSystemId"]

        # Check normal job completion
        assert job["jobName"] == job_name
        assert "neuroconv_batch_queue" in job["jobQueue"]
        assert "fs-" in job["jobDefinition"]
        assert job["status"] == "SUCCEEDED"

        status_tracker_table_name = "neuroconv_batch_status_tracker"
        table = dynamodb_resource.Table(name=status_tracker_table_name)
        table_submission_id = info["table_submission_info"]["id"]

        table_item_response = table.get_item(Key={"id": table_submission_id})
        assert table_item_response["ResponseMetadata"]["HTTPStatusCode"] == 200

        table_item = table_item_response["Item"]
        assert table_item["job_name"] == job_name
        assert table_item["job_id"] == job_id
        assert table_item["status"] == "Job submitted..."

        table.update_item(
            Key={"id": table_submission_id},
            AttributeUpdates={"status": {"Action": "PUT", "Value": "Test passed - cleaning up..."}},
        )

        table.update_item(
            Key={"id": table_submission_id}, AttributeUpdates={"status": {"Action": "PUT", "Value": "Test passed."}}
        )
