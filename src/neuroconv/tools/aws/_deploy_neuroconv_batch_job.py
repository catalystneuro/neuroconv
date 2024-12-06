"""Collection of helper functions for deploying NeuroConv in EC2 Batch jobs on AWS."""

import os
import time
import uuid
import warnings
from typing import Optional

import boto3
from pydantic import FilePath, validate_call

from ._rclone_transfer_batch_job import rclone_transfer_batch_job
from ._submit_aws_batch_job import submit_aws_batch_job

_RETRY_STATES = ["RUNNABLE", "PENDING", "STARTING", "RUNNING"]


@validate_call
def deploy_neuroconv_batch_job(
    *,
    rclone_command: str,
    yaml_specification_file_path: FilePath,
    job_name: str,
    efs_volume_name: str,
    rclone_config_file_path: Optional[FilePath] = None,
    status_tracker_table_name: str = "neuroconv_batch_status_tracker",
    compute_environment_name: str = "neuroconv_batch_environment",
    job_queue_name: str = "neuroconv_batch_queue",
    job_definition_name: Optional[str] = None,
    minimum_worker_ram_in_gib: int = 16,  # Higher than previous recommendations for safer buffering room
    minimum_worker_cpus: int = 4,
    region: Optional[str] = None,
) -> dict[str, str]:
    """
    Submit a job to AWS Batch for processing.

    Requires AWS credentials saved to files in the `~/.aws/` folder or set as environment variables.

    Parameters
    ----------
    rclone_command : str
        The command to pass directly to Rclone running on the EC2 instance.
            E.g.: "rclone copy my_drive:testing_rclone /mnt/efs/source"
        Must move data from or to '/mnt/efs/source'.
    yaml_specification_file_path : FilePath
        The path to the YAML file containing the NeuroConv specification.
    job_name : str
        The name of the job to submit.
    efs_volume_name : str
        The name of an EFS volume to be created and attached to the job.
        The path exposed to the container will always be `/mnt/efs`.
    rclone_config_file_path : FilePath, optional
        The path to the Rclone configuration file to use for the job.
        If unspecified, method will attempt to find the file in `~/.rclone` and will raise an error if it cannot.
    status_tracker_table_name : str, default: "neuroconv_batch_status_tracker"
        The name of the DynamoDB table to use for tracking job status.
    compute_environment_name : str, default: "neuroconv_batch_environment"
        The name of the compute environment to use for the job.
    job_queue_name : str, default: "neuroconv_batch_queue"
        The name of the job queue to use for the job.
    job_definition_name : str, optional
        The name of the job definition to use for the job.
        If unspecified, a name starting with 'neuroconv_batch_' will be generated.
    minimum_worker_ram_in_gib : int, default: 4
        The minimum amount of base worker memory required to run this job.
        Determines the EC2 instance type selected by the automatic 'best fit' selector.
        Recommended to be several GiB to allow comfortable buffer space for data chunk iterators.
    minimum_worker_cpus : int, default: 4
        The minimum number of CPUs required to run this job.
        A minimum of 4 is required, even if only one will be used in the actual process.
    region : str, optional
        The AWS region to use for the job.
        If not provided, we will attempt to load the region from your local AWS configuration.
        If that file is not found on your system, we will default to "us-east-2", the location of the DANDI Archive.

    Returns
    -------
    info : dict
        A dictionary containing information about this AWS Batch job.

        info["rclone_job_submission_info"] is the return value of `neuroconv.tools.aws.rclone_transfer_batch_job`.
        info["neuroconv_job_submission_info"] is the return value of `neuroconv.tools.aws.submit_job`.
    """
    efs_volume_name = efs_volume_name or f"neuroconv_batch_efs_volume_{uuid.uuid4().hex[:4]}"
    region = region or "us-east-2"

    if "/mnt/efs/source" not in rclone_command:
        message = (
            f"The Rclone command '{rclone_command}' does not contain a reference to '/mnt/efs/source'. "
            "Without utilizing the EFS mount, the instance is unlikely to have enough local disk space. "
            "The subfolder 'source' is also required to eliminate ambiguity in the transfer process."
        )
        raise ValueError(message)

    rclone_job_name = f"{job_name}_rclone_transfer"
    rclone_job_submission_info = rclone_transfer_batch_job(
        rclone_command=rclone_command,
        job_name=rclone_job_name,
        efs_volume_name=efs_volume_name,
        rclone_config_file_path=rclone_config_file_path,
        region=region,
    )
    rclone_job_id = rclone_job_submission_info["job_submission_info"]["jobId"]

    # Give the EFS and other aspects time to spin up before submitting next dependent job
    # (Otherwise, good chance that duplicate EFS will be created)
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", None)
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", None)

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

    available_efs_volumes = efs_client.describe_file_systems()
    matching_efs_volumes = [
        file_system
        for file_system in available_efs_volumes["FileSystems"]
        for tag in file_system["Tags"]
        if tag["Key"] == "Name" and tag["Value"] == efs_volume_name
    ]
    max_iterations = 10
    iteration = 0
    while len(matching_efs_volumes) == 0 and iteration < max_iterations:
        iteration += 1
        time.sleep(30)

        matching_efs_volumes = [
            file_system
            for file_system in available_efs_volumes["FileSystems"]
            for tag in file_system["Tags"]
            if tag["Key"] == "Name" and tag["Value"] == efs_volume_name
        ]

    if len(matching_efs_volumes) == 0:
        message = f"Unable to create EFS volume '{efs_volume_name}' after {max_iterations} attempts!"
        raise ValueError(message)

    docker_image = "ghcr.io/catalystneuro/neuroconv_yaml_variable:latest"

    with open(file=yaml_specification_file_path, mode="r") as io:
        yaml_specification_file_stream = io.read()

    neuroconv_job_name = f"{job_name}_neuroconv_deployment"
    job_dependencies = [{"jobId": rclone_job_id, "type": "SEQUENTIAL"}]
    neuroconv_job_submission_info = submit_aws_batch_job(
        job_name=neuroconv_job_name,
        docker_image=docker_image,
        environment_variables={
            "NEUROCONV_YAML": yaml_specification_file_stream,
            "NEUROCONV_DATA_PATH": "/mnt/efs/source",
            # TODO: would prefer this to use subfolders for source and output, but need logic for YAML
            # related code to create them if missing (hard to send EFS this command directly)
            # (the code was included in this PR, but a release cycle needs to complete for the docker images before
            # it can be used here)
            # "NEUROCONV_OUTPUT_PATH": "/mnt/efs/output",
            "NEUROCONV_OUTPUT_PATH": "/mnt/efs",
        },
        efs_volume_name=efs_volume_name,
        job_dependencies=job_dependencies,
        status_tracker_table_name=status_tracker_table_name,
        compute_environment_name=compute_environment_name,
        job_queue_name=job_queue_name,
        job_definition_name=job_definition_name,
        minimum_worker_ram_in_gib=minimum_worker_ram_in_gib,
        minimum_worker_cpus=minimum_worker_cpus,
        region=region,
    )

    info = {
        "rclone_job_submission_info": rclone_job_submission_info,
        "neuroconv_job_submission_info": neuroconv_job_submission_info,
    }

    # TODO: would be better to spin up third dependent job to clean up EFS volume after neuroconv job completes
    neuroconv_job_id = neuroconv_job_submission_info["job_submission_info"]["jobId"]
    job = None
    max_retries = 60 * 12  # roughly 12 hours max runtime (aside from internet loss) for checking cleanup
    sleep_time = 60  # 1 minute
    retry = 0.0
    time.sleep(sleep_time)
    while retry < max_retries:
        job_description_response = batch_client.describe_jobs(jobs=[neuroconv_job_id])
        if job_description_response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            # sleep but only increment retry by a small amount
            # (really should only apply if internet connection is temporarily lost)
            retry += 0.1
            time.sleep(sleep_time)

        job = job_description_response["jobs"][0]
        if job["status"] in _RETRY_STATES:
            retry += 1.0
            time.sleep(sleep_time)
        elif job["status"] == "SUCCEEDED":
            break

    if retry >= max_retries:
        message = (
            "Maximum retries reached for checking job completion for automatic EFS cleanup! "
            "Please delete the EFS volume manually."
        )
        warnings.warn(message=message, stacklevel=2)

        return info

    # Cleanup EFS after job is complete - must clear mount targets first, then wait before deleting the volume
    efs_volumes = efs_client.describe_file_systems()
    matching_efs_volumes = [
        file_system
        for file_system in efs_volumes["FileSystems"]
        for tag in file_system["Tags"]
        if tag["Key"] == "Name" and tag["Value"] == efs_volume_name
    ]
    if len(matching_efs_volumes) != 1:
        message = (
            f"Expected to find exactly one EFS volume with name '{efs_volume_name}', "
            f"but found {len(matching_efs_volumes)}\n\n{matching_efs_volumes=}\n\n!"
            "You will have to delete these manually."
        )
        warnings.warn(message=message, stacklevel=2)

        return info

    efs_volume = matching_efs_volumes[0]
    efs_id = efs_volume["FileSystemId"]
    mount_targets = efs_client.describe_mount_targets(FileSystemId=efs_id)
    for mount_target in mount_targets["MountTargets"]:
        efs_client.delete_mount_target(MountTargetId=mount_target["MountTargetId"])

    time.sleep(sleep_time)
    efs_client.delete_file_system(FileSystemId=efs_id)

    return info
