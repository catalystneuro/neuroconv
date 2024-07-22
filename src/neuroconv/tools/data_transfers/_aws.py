"""Collection of helper functions for assessing and performing automated data transfers related to AWS."""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4


def estimate_s3_conversion_cost(
    total_mb: float,
    transfer_rate_mb: float = 20.0,
    conversion_rate_mb: float = 17.0,
    upload_rate_mb: float = 40.0,
    compression_ratio: float = 1.7,
):
    """
    Estimate potential cost of performing an entire conversion on S3 using full automation.

    Parameters
    ----------
    total_mb: float
        The total amount of data (in MB) that will be transferred, converted, and uploaded to dandi.
    transfer_rate_mb : float, default: 20.0
        Estimate of the transfer rate for the data.
    conversion_rate_mb : float, default: 17.0
        Estimate of the conversion rate for the data. Can vary widely depending on conversion options and type of data.
        Figure of 17MB/s is based on extensive compression of high-volume, high-resolution ecephys.
    upload_rate_mb : float, default: 40.0
        Estimate of the upload rate of a single file to the DANDI Archive.
    compression_ratio : float, default: 1.7
        Estimate of the final average compression ratio for datasets in the file. Can vary widely.
    """
    c = 1 / compression_ratio  # compressed_size = total_size * c
    total_mb_s = total_mb**2 / 2 * (1 / transfer_rate_mb + (2 * c + 1) / conversion_rate_mb + 2 * c**2 / upload_rate_mb)
    cost_gb_m = 0.08 / 1e3  # $0.08 / GB Month
    cost_mb_s = cost_gb_m / (1e3 * 2.628e6)  # assuming 30 day month; unsure how amazon weights shorter months?
    return cost_mb_s * total_mb_s


def submit_aws_batch_job(
    *,
    job_name: str,
    docker_image: str,
    command: Optional[str] = None,
    job_dependencies: Optional[List[Dict[str, str]]] = None,
    region: str = "us-east-2",
    status_tracker_table_name: str = "neuroconv_batch_status_tracker",
    iam_role_name: str = "neuroconv_batch_role",
    compute_environment_name: str = "neuroconv_batch_environment",
    job_queue_name: str = "neuroconv_batch_queue",
    job_definition_name: Optional[str] = None,
    minimum_worker_ram_in_gb: float = 4.0,
    minimum_worker_cpus: int = 4,
) -> Dict[str, str]:
    """
    Submit a job to AWS Batch for processing.

    Parameters
    ----------
    job_name : str
        The name of the job to submit.
    docker_image : str
        The name of the Docker image to use for the job.
    command : str, optional
        The command to run in the Docker container.
        Current syntax only supports a single line; consecutive actions should be chained with the '&&' operator.
    job_dependencies : list of dict
        A list of job dependencies for this job to trigger. Structured as follows:
        [
            {"jobId": "job_id_1", "type": "N_TO_N"},
            {"jobId": "job_id_2", "type": "SEQUENTIAL"},
            ...
        ]
    region : str, default: "us-east-2"
        The AWS region to use for the job.
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
        Defaults to f"neuroconv_batch_{ name of docker image }",
        but replaces any colons from tags in the docker image name with underscores.
    minimum_worker_ram_in_gb : int, default: 4.0
        The minimum amount of base worker memory required to run this job.
        Determines the EC2 instance type selected by the automatic 'best fit' selector.
    minimum_worker_cpus : int, default: 4
        The minimum number of CPUs required to run this job.
        A minimum of 4 is required, even if only one will be used in the actual process.

    Returns
    -------
    info : dict
        A dictionary containing information about this AWS Batch job.

        info["job_submission_info"] is the return value of `boto3.client.submit_job` which contains the job ID.
        info["table_submission_info"] is the initial row data inserted into the DynamoDB status tracking table.
    """
    import boto3

    job_dependencies = job_dependencies or []

    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if aws_access_key_id is None or aws_secret_access_key is None:
        raise EnvironmentError(
            "'AWS_ACCESS_KEY_ID' and 'AWS_SECRET_ACCESS_KEY' must both be set in the environment to use this function."
        )

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

    # It is very useful to have a status tracker that is separate from the job environment
    # Technically detailed logs of inner workings are given in the CloudWatch, but that can only really be
    # analyzed from the AWS web console
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

    # Ensure role policy is set
    current_roles = [role["RoleName"] for role in iam_client.list_roles()["Roles"]]
    if iam_role_name not in current_roles:
        assume_role_policy = dict(
            Version="2012-10-17",
            Statement=[
                dict(Effect="Allow", Principal=dict(Service="ecs-tasks.amazonaws.com"), Action="sts:AssumeRole"),
            ],
        )

        role = iam_client.create_role(RoleName=iam_role_name, AssumeRolePolicyDocument=json.dumps(assume_role_policy))
        iam_client.attach_role_policy(
            RoleName=role["Role"]["RoleName"], PolicyArn="arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
        )
        iam_client.attach_role_policy(
            RoleName=role["Role"]["RoleName"], PolicyArn="arn:aws:iam::aws:policy/CloudWatchFullAccess"
        )
    else:
        role = iam_client.get_role(RoleName=iam_role_name)

    # Ensure compute environment is setup
    current_compute_environments = [
        environment["computeEnvironmentName"]
        for environment in batch_client.describe_compute_environments()["computeEnvironments"]
    ]
    if compute_environment_name not in current_compute_environments:
        batch_client.create_compute_environment(
            computeEnvironmentName=compute_environment_name,
            type="MANAGED",
            state="ENABLED",
            computeResources={
                "type": "EC2",
                "allocationStrategy": "BEST_FIT",
                "minvCpus": 0,
                "maxvCpus": 256,
                "subnets": ["subnet-0be50d51", "subnet-3fd16f77", "subnet-0092132b"],
                "instanceRole": "ecsInstanceRole",
                "securityGroupIds": ["sg-851667c7"],
                "instanceTypes": ["optimal"],
            },
        )

    # Ensure job queue exists
    current_job_queues = [queue["jobQueueName"] for queue in batch_client.describe_job_queues()["jobQueues"]]
    if job_queue_name not in current_job_queues:
        batch_client.create_job_queue(
            jobQueueName=job_queue_name,
            state="ENABLED",
            priority=1,
            computeEnvironmentOrder=[
                dict(order=100, computeEnvironment="dynamodb_import_environment"),
            ],
        )

    # Ensure job definition exists
    # By default, keep name unique by incorporating the name of the container
    job_definition_docker_name = docker_image.replace(":", "_")
    job_definition_name = job_definition_name or f"neuroconv_batch_{job_definition_docker_name}"
    current_job_definitions = [
        definition["jobDefinitionName"] for definition in batch_client.describe_job_definitions()["jobDefinitions"]
    ]
    resource_requirements = [
        {"value": str(minimum_worker_ram_in_gb * 1e3 / 1.024**2), "type": "MEMORY"},  # boto3 expects memory in MiB
        {"value": str(minimum_worker_cpus), "type": "VCPU"},
    ]
    if job_definition not in current_job_definitions:
        batch_client.register_job_definition(
            jobDefinitionName=job_definition_name,
            type="container",
            containerProperties=dict(
                image=docker_image,
                resourceRequirements=resource_requirements,
                jobRoleArn=role["Role"]["Arn"],
                executionRoleArn=role["Role"]["Arn"],
                environment=[
                    dict(
                        name="AWS_DEFAULT_REGION",
                        value=region,
                    )
                ],
            ),
        )
    else:
        # Should we also check that memory/vcpu values resolve with any previously defined job definitions in this event?
        pass

    # Submit job and update status tracker
    currently_running_jobs = batch_client.list_jobs(jobQueue=job_queue_name)
    if job_name in currently_running_jobs:
        raise ValueError(
            f"There is already a job named '{job_name}' running in the queue! "
            "If you are submitting multiple jobs, each will need a unique name."
        )

    # Set environment variables to the docker container
    # as well as optional command to run
    container_overrides = dict(
        # Set environment variables
        environment=[
            dict(  # The burden is on the calling script to update the table status to finished
                name="STATUS_TRACKER_TABLE_NAME",
                value=status_tracker_table_name,
            ),
        ]
    )
    if command is not None:
        container_overrides["command"] = [command]
    job_submission_info = batch_client.submit_job(
        jobQueue=job_queue_name,
        dependsOn=job_dependencies,
        jobDefinition=job_definition,
        jobName=job_name,
        containerOverrides=container_overrides,
    )

    # Update DynamoDB status tracking table
    table_submission_info = dict(id=uuid4(), job_name=job_name, submitted_on=datetime.now(), status="submitted")
    table.put_item(Item=table_submission_info)

    info = dict(job_submission_info=job_submission_info, table_submission_info=table_submission_info)
    return info


def update_table_status(*, submission_id: str, status: str, status_tracker_table_name: str = "neuroconv_batch_status_tracker") -> None:
    """
    Helper function for updating a status value on a DynamoDB table tracking the status of EC2 jobs.

    Intended for use by the running job to indicate its completion.

    Parameters
    ----------
    submission_id : str
        The random hash that was assigned on submission of this job to the status tracker table.
    status : str
        The new status value to update.
    status_tracker_table_name : str, default: "neuroconv_batch_status_tracker"
        The name of the DynamoDB table to use for tracking job status.
    """
    import boto3
    
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

    dynamodb_resource = boto3.resource(
        service_name="dynamodb",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    table = dynamodb_resource.Table(name=status_tracker_table_name)

    item = table.update_item(Key={"id": submission_id}, AttributeUpdates={"status": {"Action": "PUT", "Value": status}})

    return
