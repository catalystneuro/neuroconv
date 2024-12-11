"""Collection of helper functions for assessing and performing automated data transfers related to AWS."""

import warnings
from typing import Optional

from pydantic import FilePath, validate_call

from ._submit_aws_batch_job import submit_aws_batch_job


@validate_call
def rclone_transfer_batch_job(
    *,
    rclone_command: str,
    job_name: str,
    efs_volume_name: str,
    rclone_config_file_path: Optional[FilePath] = None,
    status_tracker_table_name: str = "neuroconv_batch_status_tracker",
    compute_environment_name: str = "neuroconv_batch_environment",
    job_queue_name: str = "neuroconv_batch_queue",
    job_definition_name: Optional[str] = None,
    minimum_worker_ram_in_gib: int = 4,
    minimum_worker_cpus: int = 4,
    submission_id: Optional[str] = None,
    region: Optional[str] = None,
) -> dict[str, str]:
    """
    Submit a job to AWS Batch for processing.

    Requires AWS credentials saved to files in the `~/.aws/` folder or set as environment variables.

    Parameters
    ----------
    rclone_command : str
        The command to pass directly to Rclone running on the EC2 instance.
            E.g.: "rclone copy my_drive:testing_rclone /mnt/efs"
        Must move data from or to '/mnt/efs'.
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
    submission_id : str, optional
        The unique ID to pair with this job submission when tracking the status via DynamoDB.
        Defaults to a random UUID4.
    region : str, optional
        The AWS region to use for the job.
        If not provided, we will attempt to load the region from your local AWS configuration.
        If that file is not found on your system, we will default to "us-east-2", the location of the DANDI Archive.

    Returns
    -------
    info : dict
        A dictionary containing information about this AWS Batch job.

        info["job_submission_info"] is the return value of `boto3.client.submit_job` which contains the job ID.
        info["table_submission_info"] is the initial row data inserted into the DynamoDB status tracking table.
    """
    docker_image = "ghcr.io/catalystneuro/rclone_with_config:latest"

    if "/mnt/efs" not in rclone_command:
        message = (
            f"The Rclone command '{rclone_command}' does not contain a reference to '/mnt/efs'. "
            "Without utilizing the EFS mount, the instance is unlikely to have enough local disk space."
        )
        warnings.warn(message=message, stacklevel=2)

    rclone_config_file_path = rclone_config_file_path or pathlib.Path.home() / ".rclone" / "rclone.conf"
    if not rclone_config_file_path.exists():
        raise FileNotFoundError(
            f"Rclone configuration file not found at: {rclone_config_file_path}! "
            "Please check that `rclone config` successfully created the file."
        )
    with open(file=rclone_config_file_path, mode="r") as io:
        rclone_config_file_stream = io.read()

    region = region or "us-east-2"

    info = submit_aws_batch_job(
        job_name=job_name,
        docker_image=docker_image,
        environment_variables={"RCLONE_CONFIG": rclone_config_file_stream, "RCLONE_COMMAND": rclone_command},
        efs_volume_name=efs_volume_name,
        status_tracker_table_name=status_tracker_table_name,
        compute_environment_name=compute_environment_name,
        job_queue_name=job_queue_name,
        job_definition_name=job_definition_name,
        minimum_worker_ram_in_gib=minimum_worker_ram_in_gib,
        minimum_worker_cpus=minimum_worker_cpus,
        submission_id=submission_id,
        region=region,
    )

    return info
