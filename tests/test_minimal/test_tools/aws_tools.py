import datetime
import os
import pathlib
import time

import boto3

from neuroconv.tools.aws import (
    deploy_neuroconv_batch_job,
    rclone_transfer_batch_job,
    submit_aws_batch_job,
)

_RETRY_STATES = ["RUNNABLE", "PENDING", "STARTING", "RUNNING"]


def test_submit_aws_batch_job():
    region = "us-east-2"
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", None)
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", None)

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

    job_name = "test_submit_aws_batch_job"
    docker_image = "ubuntu:latest"
    commands = ["echo", "'Testing NeuroConv AWS Batch submission.'"]

    # TODO: to reduce costs even more, find a good combinations of memory/CPU to minimize size of instance
    info = submit_aws_batch_job(job_name=job_name, docker_image=docker_image, commands=commands)

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

    assert job["jobName"] == job_name
    assert "neuroconv_batch_queue" in job["jobQueue"]
    assert "neuroconv_batch_ubuntu-latest-image_4-GiB-RAM_4-CPU" in job["jobDefinition"]
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
        Key={"id": table_submission_id}, AttributeUpdates={"status": {"Action": "PUT", "Value": "Test passed."}}
    )


def test_submit_aws_batch_job_with_dependencies():
    region = "us-east-2"
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", None)
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", None)

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

    job_name_1 = "test_submit_aws_batch_job_with_dependencies_1"
    docker_image = "ubuntu:latest"
    commands_1 = ["echo", "'Testing NeuroConv AWS Batch submission.'"]

    # TODO: to reduce costs even more, find a good combinations of memory/CPU to minimize size of instance
    job_info_1 = submit_aws_batch_job(
        job_name=job_name_1,
        docker_image=docker_image,
        commands=commands_1,
    )
    job_submission_info_1 = job_info_1["job_submission_info"]

    job_name_2 = "test_submit_aws_batch_job_with_dependencies_1"
    commands_2 = ["echo", "'Testing NeuroConv AWS Batch submission with dependencies.'"]
    job_dependencies = [{"jobId": job_submission_info_1["jobId"], "type": "SEQUENTIAL"}]
    job_info_2 = submit_aws_batch_job(
        job_name=job_name_2,
        docker_image=docker_image,
        commands=commands_2,
        job_dependencies=job_dependencies,
    )

    # Wait for AWS to process the jobs
    time.sleep(60)

    job_id_1 = job_info_1["job_submission_info"]["jobId"]
    job_id_2 = job_info_2["job_submission_info"]["jobId"]
    job_1 = None
    max_retries = 10
    retry = 0
    while retry < max_retries:
        all_job_descriptions_response = batch_client.describe_jobs(jobs=[job_id_1, job_id_2])
        assert all_job_descriptions_response["ResponseMetadata"]["HTTPStatusCode"] == 200

        jobs_by_id = {job["jobId"]: job for job in all_job_descriptions_response["jobs"]}
        assert len(jobs_by_id) == 2

        job_1 = jobs_by_id[job_id_1]
        job_2 = jobs_by_id[job_id_2]

        if job_1["status"] in _RETRY_STATES or job_2["status"] in _RETRY_STATES:
            retry += 1
            time.sleep(60)
        else:
            break

    assert job_1["jobName"] == job_name_1
    assert "neuroconv_batch_queue" in job_1["jobQueue"]
    assert "neuroconv_batch_ubuntu-latest-image_4-GiB-RAM_4-CPU" in job_1["jobDefinition"]
    assert job_1["status"] == "SUCCEEDED"

    job_2 = jobs_by_id[job_id_2]
    assert job_2["jobName"] == job_name_2
    assert "neuroconv_batch_queue" in job_2["jobQueue"]
    assert "neuroconv_batch_ubuntu-latest-image_4-GiB-RAM_4-CPU" in job_2["jobDefinition"]
    assert job_2["status"] == "SUCCEEDED"

    status_tracker_table_name = "neuroconv_batch_status_tracker"
    table = dynamodb_resource.Table(name=status_tracker_table_name)

    table_submission_id_1 = job_info_1["table_submission_info"]["id"]
    table_item_response_1 = table.get_item(Key={"id": table_submission_id_1})
    assert table_item_response_1["ResponseMetadata"]["HTTPStatusCode"] == 200

    table_item_1 = table_item_response_1["Item"]
    assert table_item_1["job_name"] == job_name_1
    assert table_item_1["job_id"] == job_id_1
    assert table_item_1["status"] == "Job submitted..."

    table_submission_id_2 = job_info_2["table_submission_info"]["id"]
    table_item_response_2 = table.get_item(Key={"id": table_submission_id_2})
    assert table_item_response_2["ResponseMetadata"]["HTTPStatusCode"] == 200

    table_item_2 = table_item_response_2["Item"]
    assert table_item_2["job_name"] == job_name_2
    assert table_item_2["job_id"] == job_id_2
    assert table_item_2["status"] == "Job submitted..."

    table.update_item(
        Key={"id": table_submission_id_1}, AttributeUpdates={"status": {"Action": "PUT", "Value": "Test passed."}}
    )
    table.update_item(
        Key={"id": table_submission_id_2}, AttributeUpdates={"status": {"Action": "PUT", "Value": "Test passed."}}
    )


def test_submit_aws_batch_job_with_efs_mount():
    """
    It was confirmed manually that a job using this definition will fail if the /mnt/efs/ directory does not exist.

    It is, however, prohibitively difficult to automatically check if the file exists on the EFS volume.

    If desired, you can manually check the EFS volume by following these instructions:
        https://repost.aws/knowledge-center/efs-mount-automount-unmount-steps
    """
    region = "us-east-2"
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", None)
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", None)

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
    efs_client = boto3.client(
        service_name="efs",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    job_name = "test_submit_aws_batch_job_with_efs"
    docker_image = "ubuntu:latest"
    date = datetime.datetime.now().date().strftime("%y%m%d")
    commands = ["touch", f"/mnt/efs/test_{date}.txt"]

    # TODO: to reduce costs even more, find a good combinations of memory/CPU to minimize size of instance
    efs_volume_name = f"test_neuroconv_batch_with_efs_{date}"
    info = submit_aws_batch_job(
        job_name=job_name,
        docker_image=docker_image,
        commands=commands,
        efs_volume_name=efs_volume_name,
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
    efs_id = efs_volume["FileSystemId"]

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

    # Cleanup EFS after testing is complete - must clear mount targets first, then wait before deleting the volume
    # TODO: cleanup job definitions? (since built daily)
    mount_targets = efs_client.describe_mount_targets(FileSystemId=efs_id)
    for mount_target in mount_targets["MountTargets"]:
        efs_client.delete_mount_target(MountTargetId=mount_target["MountTargetId"])

    time.sleep(60)
    efs_client.delete_file_system(FileSystemId=efs_id)

    table.update_item(
        Key={"id": table_submission_id}, AttributeUpdates={"status": {"Action": "PUT", "Value": "Test passed."}}
    )


class TestRcloneTransferBatchJob(TestCase):
    """
    To allow this test to work, the developer must create a folder on the outer level of their personal Google Drive
    called 'testing_rclone_spikeglx' with the following structure:

    testing_rclone_spikeglx
    ├── ci_tests
    ├────── Noise4Sam_g0

    Where 'Noise4Sam' is from the 'spikeglx/Noise4Sam_g0' GIN ephys dataset.

    Then the developer must install Rclone and call `rclone config` to generate tokens in their own `rclone.conf` file.
    The developer can easily find the location of the config file on their system using `rclone config file`.
    """

    test_folder = OUTPUT_PATH / "aws_rclone_tests"
    test_config_file_path = test_folder / "rclone.conf"

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

    def test_rclone_transfer_batch_job(self):
        region = "us-east-2"
        aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", None)
        aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", None)

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
        efs_client = boto3.client(
            service_name="efs",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        rclone_command = "rclone copy test_google_drive_remote:testing_rclone_spikeglx /mnt/efs"
        rclone_config_file_path = self.test_config_file_path

        info = rclone_transfer_batch_job(
            rclone_command=rclone_command,
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
        efs_id = efs_volume["FileSystemId"]

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

        # Cleanup EFS after testing is complete - must clear mount targets first, then wait before deleting the volume
        # TODO: cleanup job definitions? (since built daily)
        mount_targets = efs_client.describe_mount_targets(FileSystemId=efs_id)
        for mount_target in mount_targets["MountTargets"]:
            efs_client.delete_mount_target(MountTargetId=mount_target["MountTargetId"])

        time.sleep(60)
        efs_client.delete_file_system(FileSystemId=efs_id)

        table.update_item(
            Key={"id": table_submission_id}, AttributeUpdates={"status": {"Action": "PUT", "Value": "Test passed."}}
        )

    def test_deploy_neuroconv_batch_job(self):
        region = "us-east-2"
        aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", None)
        aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", None)

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
        efs_client = boto3.client(
            service_name="efs",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        rclone_command = "rclone copy test_google_drive_remote:testing_rclone_spikeglx /mnt/efs"

        testing_base_folder_path = pathlib.Path(__file__).parent.parent.parent
        yaml_specification_file_path = (
            testing_base_folder_path
            / "test_on_data"
            / "test_yaml"
            / "conversion_specifications"
            / "GIN_conversion_specification.yml"
        )

        rclone_config_file_path = self.test_config_file_path

        job_name = "test_deploy_neuroconv_batch_job"
        all_info = deploy_neuroconv_batch_job(
            rclone_command=rclone_command,
            yaml_specification_file_path=yaml_specification_file_path,
            job_name=job_name,
            rclone_config_file_path=rclone_config_file_path,
        )

        # Wait for AWS to process the job
        time.sleep(120)

        info = all_info["neuroconv_job_submission_info"]
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
        efs_id = efs_volume["FileSystemId"]

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

        # Cleanup EFS after testing is complete - must clear mount targets first, then wait before deleting the volume
        # TODO: cleanup job definitions? (since built daily)
        mount_targets = efs_client.describe_mount_targets(FileSystemId=efs_id)
        for mount_target in mount_targets["MountTargets"]:
            efs_client.delete_mount_target(MountTargetId=mount_target["MountTargetId"])

        time.sleep(60)
        efs_client.delete_file_system(FileSystemId=efs_id)

        table.update_item(
            Key={"id": table_submission_id}, AttributeUpdates={"status": {"Action": "PUT", "Value": "Test passed."}}
        )
