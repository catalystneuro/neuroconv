"""Collection of helper functions for assessing and performing automated data transfers related to AWS."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4


def submit_aws_batch_job(
    *,
    job_name: str,
    docker_image: str,
    commands: Optional[List[str]] = None,
    environment_variables: Optional[Dict[str, str]] = None,
    job_dependencies: Optional[List[Dict[str, str]]] = None,
    status_tracker_table_name: str = "neuroconv_batch_status_tracker",
    iam_role_name: str = "neuroconv_batch_role",
    compute_environment_name: str = "neuroconv_batch_environment",
    job_queue_name: str = "neuroconv_batch_queue",
    job_definition_name: Optional[str] = None,
    minimum_worker_ram_in_gib: int = 4,
    minimum_worker_cpus: int = 4,
    submission_id: Optional[str] = None,
    region: Optional[str] = None,
) -> Dict[str, str]:  # pragma: no cover
    """
    Submit a job to AWS Batch for processing.

    Parameters
    ----------
    job_name : str
        The name of the job to submit.
    docker_image : str
        The name of the Docker image to use for the job.
    commands : str, optional
        The list of commands to run in the Docker container. Normal spaces are separate entries in the list.
        Current syntax only supports a single line; consecutive actions should be chained with the '&&' operator.
        E.g., `commands=["echo", "'Hello, World!'"]`.
    environment_variables : dict, optional
        A dictionary of environment variables to pass to the Docker container.
    job_dependencies : list of dict
        A list of job dependencies for this job to trigger. Structured as follows:
        [
            {"jobId": "job_id_1", "type": "N_TO_N"},
            {"jobId": "job_id_2", "type": "SEQUENTIAL"},
            ...
        ]

        Refer to the boto3 API documentation for latest syntax.
    status_tracker_table_name : str, default: "neuroconv_batch_status_tracker"
        The name of the DynamoDB table to use for tracking job status.
    iam_role_name : str, default: "neuroconv_batch_role"
        The name of the IAM role to use for the job.
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
    import boto3

    # Ensure all client parameters are set
    region = region or _attempt_to_load_region_from_config() or "us-east-2"

    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", None)
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", None)
    if aws_access_key_id is None or aws_secret_access_key is None:
        aws_access_key_id, aws_secret_access_key = _attempt_to_load_aws_credentials_from_config()
    if aws_access_key_id is None or aws_secret_access_key is None:
        raise EnvironmentError(
            "To use this function, both 'AWS_ACCESS_KEY_ID' and 'AWS_SECRET_ACCESS_KEY' must either be set in the "
            "local environment or set in the default AWS configuration file."
        )

    # Initialize all clients
    dynamodb_client = boto3.client(
        service_name="dynamodb",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    dynamodb_resource = boto3.resource(
        service_name="dynamodb",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    iam_client = boto3.client(
        service_name="iam",
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

    # Get the tracking table and IAM role
    table = _create_or_get_status_tracker_table(
        status_tracker_table_name=status_tracker_table_name,
        dynamodb_client=dynamodb_client,
        dynamodb_resource=dynamodb_resource,
    )
    role_info = _create_or_get_iam_role(iam_role_name=iam_role_name, iam_client=iam_client)

    # Ensure all job submission requirements are met
    _ensure_compute_environment_exists(compute_environment_name=compute_environment_name, batch_client=batch_client)
    _ensure_job_queue_exists(
        job_queue_name=job_queue_name, compute_environment_name=compute_environment_name, batch_client=batch_client
    )

    job_definition_name = job_definition_name or _generate_job_definition_name(
        docker_image=docker_image,
        minimum_worker_ram_in_gib=minimum_worker_ram_in_gib,
        minimum_worker_cpus=minimum_worker_cpus,
    )
    job_definition_arn = _ensure_job_definition_exists_and_get_arn(
        job_definition_name=job_definition_name,
        docker_image=docker_image,
        minimum_worker_ram_in_gib=minimum_worker_ram_in_gib,
        minimum_worker_cpus=minimum_worker_cpus,
        role_info=role_info,
        batch_client=batch_client,
    )

    # Submit job and update status tracker
    currently_running_jobs = batch_client.list_jobs(jobQueue=job_queue_name)
    if job_name in currently_running_jobs:
        raise ValueError(
            f"There is already a job named '{job_name}' running in the queue! "
            "If you are submitting multiple jobs, each will need a unique name."
        )

    # Set environment variables to the docker container as well as optional commands to run
    job_dependencies = job_dependencies or []
    container_overrides = dict()
    if environment_variables is not None:
        container_overrides["environment"] = [{key: value} for key, value in environment_variables.items()]
    if commands is not None:
        container_overrides["command"] = commands
    job_submission_info = batch_client.submit_job(
        jobName=job_name,
        dependsOn=job_dependencies,
        jobDefinition=job_definition_arn,
        jobQueue=job_queue_name,
        containerOverrides=container_overrides,
    )

    # Update status tracking table
    submission_id = submission_id or str(uuid4())
    table_submission_info = dict(
        id=submission_id,
        job_id=job_submission_info["jobId"],
        job_name=job_name,
        submitted_on=datetime.now().isoformat(),
        status="Job submitted...",
    )
    table.put_item(Item=table_submission_info)

    info = dict(job_submission_info=job_submission_info, table_submission_info=table_submission_info)
    return info


def _attempt_to_load_region_from_config() -> Optional[str]:  # pragma: no cover
    """
    Attempts to load the AWS region from the default configuration file.

    Returns `None` if any issue is encountered.

    Returns
    -------
    region : str or None
        The AWS region to use for all tasks.

        Returns `None` if:
        - The default file does not exist.
        - No line starts with 'region'.
        - Multiple lines start with 'region'.
    """
    default_config_file_path = Path.home() / ".aws" / "config"

    if not default_config_file_path.exists():
        return None

    with open(file=default_config_file_path, mode="r") as io:
        all_lines = io.readlines()
    lines_with_region = [line for line in all_lines if "region" == line[:7]]

    if len(lines_with_region) != 1:
        return None

    region = region_lines[0].split("=")[1].strip()

    return region


def _attempt_to_load_aws_credentials_from_config() -> Tuple[Optional[str], Optional[str]]:  # pragma: no cover
    """
    Attempts to load the AWS credentials from a configuration file.

    Returns
    -------
    aws_access_key_id : str or None
    aws_secret_access_key : str or None

        Returns `None` if:
        - The file does not exist
        - No line starts with either key.
        - Multiple lines start with either key.
    """
    default_credentials_file_path = Path.home() / ".aws" / "credentials"

    if not default_credentials_file_path.exists():
        return (None, None)

    with open(file=default_credentials_file_path, mode="r") as io:
        all_lines = io.readlines()
    lines_with_access_key_id = [line for line in all_lines if "aws_access_key_id" == line[:17]]
    lines_with_secret_access_key = [line for line in all_lines if "aws_secret_access_key" == line[:21]]

    if len(lines_with_access_key_id) != 1 or len(lines_with_secret_access_key) != 1:
        return (None, None)

    aws_access_key_id = lines_with_access_key_id[0].split("=")[1].strip()
    aws_secret_access_key = lines_with_secret_access_key[0].split("=")[1].strip()

    return (aws_access_key_id, aws_secret_access_key)


def _create_or_get_status_tracker_table(
    *,
    status_tracker_table_name: str,
    dynamodb_client: "boto3.client.dynamodb",
    dynamodb_resource: "boto3.resources.dynamodb",
) -> "boto3.resources.dynamodb.Table":  # pragma: no cover
    """
    Create or get the DynamoDB table for tracking the status of jobs submitted to AWS Batch.

    It is very useful to have a status tracker that is separate from the job environment.

    Detailed logs of inner workings of each instance are given in the CloudWatch, but that can only really be
    analyzed from the AWS web console.

    Parameters
    ----------
    status_tracker_table_name : str, default: "neuroconv_batch_status_tracker"
        The name of the DynamoDB table to use for tracking job status.
    dynamodb_client : boto3.client.dynamodb
        The DynamoDB client to use for the job.
    dynamodb_resource : boto3.resources.dynamodb
        The DynamoDB resource to use for the job.
    """
    current_tables = dynamodb_client.list_tables()["TableNames"]
    if status_tracker_table_name not in current_tables:
        table = dynamodb_resource.create_table(
            TableName=status_tracker_table_name,
            KeySchema=[dict(AttributeName="id", KeyType="HASH")],
            AttributeDefinitions=[dict(AttributeName="id", AttributeType="S")],
            ProvisionedThroughput=dict(ReadCapacityUnits=1, WriteCapacityUnits=1),
        )
    else:
        table = dynamodb_resource.Table(name=status_tracker_table_name)

    return table


def _create_or_get_iam_role(*, iam_role_name: str, iam_client: "boto3.client.iam") -> dict:  # pragma: no cover
    """
    Create or get the IAM role policy for the AWS Batch job.

    Parameters
    ----------
    iam_role_name : str
        The name of the IAM role to use for the job.
    iam_client : boto3.client.iam
        The IAM client to use for the job.

    Returns
    -------
    role_info : dict
        All associated information about the IAM role (including set policies).
    """
    # Normally try/except structures are not recommended
    # But making a targeted request for a named entity here incurs less AWS costs than listing all entities
    try:
        role_info = iam_client.get_role(RoleName=iam_role_name)
        return role_info
    except Exception as exception:
        if "NoSuchEntity" not in str(exception):
            raise exception

    assume_role_policy = dict(
        Version="2012-10-17",
        Statement=[
            dict(Effect="Allow", Principal=dict(Service="ecs-tasks.amazonaws.com"), Action="sts:AssumeRole"),
        ],
    )

    # iam_client.create_role() is synchronous and so there is no need to wait in this function
    role_info = iam_client.create_role(RoleName=iam_role_name, AssumeRolePolicyDocument=json.dumps(assume_role_policy))
    iam_client.attach_role_policy(
        RoleName=role_info["Role"]["RoleName"], PolicyArn="arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
    )
    iam_client.attach_role_policy(
        RoleName=role_info["Role"]["RoleName"], PolicyArn="arn:aws:iam::aws:policy/CloudWatchFullAccess"
    )

    return role_info


def _ensure_compute_environment_exists(
    *, compute_environment_name: str, batch_client: "boto3.client.Batch", max_retries: int = 12
) -> None:  # pragma: no cover
    """
    Ensure that the compute environment exists in AWS Batch.

    Parameters
    ----------
    compute_environment_name : str
        The name of the compute environment to use for the job.
    batch_client : boto3.client.Batch
        The AWS Batch client to use for the job.
    max_retries : int, default: 12
        If the compute environment does not already exist, then this is the maximum number of times to synchronously
        check for its successful creation before erroring.
        This is essential for a clean setup of the entire pipeline, or else later steps might error because they tried
        to launch before the compute environment was ready.
    """
    compute_environment_request = batch_client.describe_compute_environments(
        computeEnvironments=[compute_environment_name]
    )
    compute_environment_response = compute_environment_request["computeEnvironments"]

    if len(compute_environment_response) == 1:
        return compute_environment_response[0]

    if len(compute_environment_response) > 1:
        raise ValueError(
            f"Multiple compute environments with the name '{compute_environment_name}' were found! "
            "Please ensure that only one compute environment has this name."
        )

    # batch_client.create_compute_environment() is not synchronous and so we need to wait a bit afterwards
    batch_client.create_compute_environment(
        computeEnvironmentName=compute_environment_name,
        type="MANAGED",
        state="ENABLED",
        computeResources={
            "type": "EC2",
            "allocationStrategy": "BEST_FIT",  # Note: not currently supporting spot due to interruptibility
            "instanceTypes": ["optimal"],
            "minvCpus": 1,
            "maxvCpus": 8,  # Not: not currently exposing control over this since these are mostly I/O intensive
            "instanceRole": "ecsInstanceRole",
            # Security groups and subnets last updated on 8/4/2024
            "securityGroupIds": ["sg-001699e5b7496b226"],
            "subnets": [
                "subnet-0890a93aedb42e73e",  # us-east-2a
                "subnet-0e20bbcfb951b5387",  # us-east-2b
                "subnet-0680e07980538b786",  # us-east-2c
            ],
        },
    )

    compute_environment_request = batch_client.describe_compute_environments(
        computeEnvironments=[compute_environment_name]
    )
    compute_environment_response = compute_environment_request["computeEnvironments"]
    compute_environment_status = (
        compute_environment_response[0]["status"] if len(compute_environment_response) == 1 else ""
    )
    retry_count = 0
    while compute_environment_status != "VALID" and retry_count <= max_retries:
        retry_count += 1
        time.sleep(10)
        compute_environment_request = batch_client.describe_compute_environments(
            computeEnvironments=[compute_environment_name]
        )
        compute_environment_response = compute_environment_request["computeEnvironments"]
        compute_environment_status = (
            compute_environment_response[0]["status"] if len(compute_environment_response) == 1 else ""
        )

    if len(job_definition_response) != 1 and compute_environment_status != "VALID":
        raise ValueError(
            f"Compute environment '{compute_environment_name}' failed to launch after {max_retries} retries."
        )

    return None


def _ensure_job_queue_exists(
    *, job_queue_name: str, compute_environment_name: str, batch_client: "boto3.client.Batch", max_retries: int = 12
) -> None:  # pragma: no cover
    """
    Ensure that the job queue exists in AWS Batch.

    Parameters
    ----------
    job_queue_name : str
        The name of the job queue to use for the job.
    compute_environment_name : str
        The name of the compute environment to associate with the job queue.
    batch_client : boto3.client.Batch
        The AWS Batch client to use for the job.
    max_retries : int, default: 12
        If the job queue does not already exist, then this is the maximum number of times to synchronously
        check for its successful creation before erroring.
        This is essential for a clean setup of the entire pipeline, or else later steps might error because they tried
        to launch before the job queue was ready.
    """
    job_queue_request = batch_client.describe_job_queues(jobQueues=[job_queue_name])
    job_queue_response = job_queue_request["jobQueues"]

    if len(job_queue_response) == 1:
        return job_queue_response[0]

    if len(job_queue_response) > 1:
        raise ValueError(
            f"Multiple job queues with the name '{job_queue_name}' were found! "
            "Please ensure that only one job queue has this name."
        )

    # Note: jobs submitted to EC2 Batch can occasionally get stuck in 'runnable' status due to bad configuration of
    # worker memory/CPU or general resource contention.
    # Eventually consider exposing this for very long jobs?
    minimum_time_to_kill_in_days = 1
    minimum_time_to_kill_in_seconds = minimum_time_to_kill_in_days * 24 * 60 * 60

    # batch_client.create_job_queue() is not synchronous and so we need to wait a bit afterwards
    batch_client.create_job_queue(
        jobQueueName=job_queue_name,
        state="ENABLED",
        priority=1,
        computeEnvironmentOrder=[
            dict(order=1, computeEnvironment=compute_environment_name),
        ],
        jobStateTimeLimitActions=[
            dict(
                reason="Avoid zombie jobs.",
                state="RUNNABLE",
                maxTimeSeconds=minimum_time_to_kill_in_seconds,
                action="CANCEL",
            ),
        ],
    )

    job_queue_request = batch_client.describe_job_queues(jobQueues=[job_queue_name])
    job_queue_response = job_queue_request["jobQueues"]
    job_queue_status = job_queue_response[0]["status"] if len(job_queue_response) == 1 else ""
    retry_count = 0
    while job_queue_status != "VALID" and retry_count <= max_retries:
        retry_count += 1
        time.sleep(10)
        job_queue_request = batch_client.describe_job_queues(jobQueues=[job_queue_name])
        job_queue_response = job_queue_request["jobQueues"]
        job_queue_status = job_queue_response[0]["status"] if len(job_queue_response) == 1 else ""

    if len(job_definition_response) != 1 and job_queue_status != "VALID":
        raise ValueError(f"Job queue '{job_queue_status}' failed to launch after {max_retries} retries.")

    return None


def _generate_job_definition_name(
    *,
    docker_image: str,
    minimum_worker_ram_in_gib: int,
    minimum_worker_cpus: int,
) -> str:  # pragma: no cover
    """
    Generate a job definition name for the AWS Batch job.

    Note that Docker images don't strictly require a tag to be pulled or used - 'latest' is always used by default.

    Parameters
    ----------
    docker_image : str
        The name of the Docker image to use for the job.
    minimum_worker_ram_in_gib : int
        The minimum amount of base worker memory required to run this job.
        Determines the EC2 instance type selected by the automatic 'best fit' selector.
        Recommended to be several GiB to allow comfortable buffer space for data chunk iterators.
    minimum_worker_cpus : int
        The minimum number of CPUs required to run this job.
        A minimum of 4 is required, even if only one will be used in the actual process.
    """
    docker_tags = docker_image.split(":")[1:]
    docker_tag = docker_tags[0] if len(docker_tags) > 1 else None
    parsed_docker_image_name = docker_image.replace(":", "-")  # AWS Batch does not allow colons in job definition names

    job_definition_name = f"neuroconv_batch"
    job_definition_name += f"_{parsed_docker_image_name}-image"
    job_definition_name += f"_{minimum_worker_ram_in_gib}-GiB-RAM"
    job_definition_name += f"_{minimum_worker_cpus}-CPU"
    if docker_tag is None or docker_tag == "latest":
        date = datetime.now().strftime("%Y-%m-%d")
        job_definition_name += f"_created-on-{date}"

    return job_definition_name


def _ensure_job_definition_exists_and_get_arn(
    *,
    job_definition_name: str,
    docker_image: str,
    minimum_worker_ram_in_gib: int,
    minimum_worker_cpus: int,
    role_info: dict,
    batch_client: "boto3.client.Batch",
    max_retries: int = 12,
) -> str:  # pragma: no cover
    """
    Ensure that the job definition exists in AWS Batch and return the official ARN.

    Automatically generates a job definition name using the docker image, its tags, and worker configuration.
    The creation date is also appended if the docker image was not tagged or was tagged as 'latest'.

    Note that registering a job definition does not require either a compute environment or a job queue to exist.

    Also note that registration is strict; once created, a job definition is tagged with ':< revision index >' and
    any subsequent changes create a new revision index (and technically a new definition as well).

    Parameters
    ----------
    job_definition_name : str
        The name of the job definition to use for the job.
    docker_image : str
        The name of the Docker image to use for the job.
    minimum_worker_ram_in_gib : int
        The minimum amount of base worker memory required to run this job.
        Determines the EC2 instance type selected by the automatic 'best fit' selector.
        Recommended to be several GiB to allow comfortable buffer space for data chunk iterators.
    minimum_worker_cpus : int
        The minimum number of CPUs required to run this job.
        A minimum of 4 is required, even if only one will be used in the actual process.
    role_info : dict
        The IAM role information for the job.
    batch_client : boto3.client.Batch
        The AWS Batch client to use for the job.
    max_retries : int, default: 12
        If the job definition does not already exist, then this is the maximum number of times to synchronously
        check for its successful creation before erroring.
        This is essential for a clean setup of the entire pipeline, or else later steps might error because they tried
        to launch before the job definition was ready.

    Returns
    -------
    job_definition_arn : str
        The full ARN of the job definition.
    """
    revision = 1
    job_definition_with_revision = f"{job_definition_name}:{revision}"
    job_definition_request = batch_client.describe_job_definitions(jobDefinitions=[job_definition_with_revision])
    job_definition_response = job_definition_request["jobDefinitions"]

    # Increment revision until we either find one that is active or we fail to find one that exists
    while len(job_definition_response) == 1:
        if job_definition_response[0]["status"] == "ACTIVE":
            return job_definition_response[0]["jobDefinitionArn"]
        else:
            revision += 1

            job_definition_with_revision = f"{job_definition_name}:{revision}"
            job_definition_request = batch_client.describe_job_definitions(
                jobDefinitions=[job_definition_with_revision]
            )
            job_definition_response = job_definition_request["jobDefinitions"]

    resource_requirements = [
        {
            "value": str(int(minimum_worker_ram_in_gib * 1024)),  # boto3 expects memory in round MiB
            "type": "MEMORY",
        },
        {"value": str(minimum_worker_cpus), "type": "VCPU"},
    ]

    minimum_time_to_kill_in_days = 1  # Note: eventually consider exposing this for very long jobs?
    minimum_time_to_kill_in_seconds = minimum_time_to_kill_in_days * 24 * 60 * 60

    # batch_client.register_job_definition() is not synchronous and so we need to wait a bit afterwards
    batch_client.register_job_definition(
        jobDefinitionName=job_definition_name,
        type="container",
        timeout=dict(attemptDurationSeconds=minimum_time_to_kill_in_seconds),
        containerProperties=dict(
            image=docker_image,
            resourceRequirements=resource_requirements,
            jobRoleArn=role_info["Role"]["Arn"],
            executionRoleArn=role_info["Role"]["Arn"],
        ),
    )

    job_definition_request = batch_client.describe_job_definitions(jobDefinitions=[job_definition_with_revision])
    job_definition_response = job_definition_request["jobDefinitions"]
    job_definition_status = job_definition_response[0]["status"] if len(job_definition_response) == 1 else ""
    retry_count = 0
    while job_definition_status != "ACTIVE" and retry_count <= max_retries:
        retry_count += 1
        time.sleep(10)
        job_definition_request = batch_client.describe_job_definitions(jobDefinitions=[job_definition_with_revision])
        job_definition_response = job_definition_request["jobDefinitions"]
        job_definition_status = job_definition_response[0]["status"] if len(job_definition_response) == 1 else ""

    if len(job_definition_response) != 1 or job_definition_status != "ACTIVE":
        raise ValueError(
            f"Job definition '{job_definition_with_revision}' failed to launch after {max_retries} retries."
        )

    return job_definition_response[0]["jobDefinitionArn"]
