"""Collection of helper functions for assessing and performing automated data transfers related to AWS."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import FilePath


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
    region: str = "us-east-2",
    job_name: str,
    docker_image: str,
    command: Optional[str] = None,
    job_dependencies: Optional[List[Dict[str, str]]] = None,
    iam_role_name: str = "neuroconv_batch_role",
    compute_environment_name: str = "neuroconv_batch_environment",
    job_queue_name: str = "neuroconv_batch_queue",
    job_definition_name: Optional[str] = None,
    minimum_worker_ram_in_gb: float = 4.0,
    minimum_worker_cpus: int = 4,
    efs_volume_name: Optional[str] = None,
    environment_variables: Optional[Dict[str, str]] = None,
    status_tracker_table_name: str = "neuroconv_batch_status_tracker",
    submission_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    Submit a job to AWS Batch for processing.

    Parameters
    ----------
    region : str, default: "us-east-2"
        The AWS region to use for the job.
        us-east-2 (Ohio) is the location of the DANDI Archive, and we recommend all operations be run in that region to
        remove cross-region transfer costs.
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
        Recommended to be several GB to allow comfortable buffer space for data chunk iterators.
    minimum_worker_cpus : int, default: 4
        The minimum number of CPUs required to run this job.
        A minimum of 4 is required, even if only one will be used in the actual process.
    efs_volume_name : str, optional
        The name of the EFS volume to attach to the jobs used by the operation.
    environment_variables : dict of str, optional
        A dictionary of key-value pairs to pass to the docker image.
    status_tracker_table_name : str, default: "neuroconv_batch_status_tracker"
        The name of the DynamoDB table to use for tracking job status.
    submission_id : str, optional
        The unique ID to pair with this job submission when tracking the status via DynamoDB.
        Defaults to a sampled UUID4.

    Returns
    -------
    info : dict
        A dictionary containing information about this AWS Batch job.

        info["job_submission_info"] is the return value of `boto3.client.submit_job` which contains the job ID.
        info["table_submission_info"] is the initial row data inserted into the DynamoDB status tracking table.
    """
    import boto3

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

    resource_requirements = [
        {
            "value": str(int(minimum_worker_ram_in_gb * 1e3 / 1.024**2)),  # boto3 expects memory in round MiB
            "type": "MEMORY",
        },
        {"value": str(minimum_worker_cpus), "type": "VCPU"},
    ]

    container_properties = dict(
        image=docker_image,
        resourceRequirements=resource_requirements,
        jobRoleArn=role["Role"]["Arn"],
        executionRoleArn=role["Role"]["Arn"],
        # environment=[
        #     dict(
        #         name="AWS_DEFAULT_REGION",
        #         value=region,
        #     )
        # ],
    )

    if efs_volume_name is not None:
        # Connect the job definition reference to the EFS mount
        job_definition_name += f"_{efs_volume_name}"

        efs_client = boto3.client(
            service_name="efs",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        all_efs_volumes = efs_client.describe_file_systems()
        all_efs_volumes_by_name = {efs_volume["Name"]: efs_volume for efs_volume in all_efs_volumes["FileSystems"]}
        efs_volume = all_efs_volumes_by_name[efs_volume_name]

        volumes = [
            dict(
                name=efs_volume_name,
                efsVolumeConfiguration=dict(fileSystemId=efs_volume["FileSystemId"]),
            )
        ]

        container_properties.update(volumes)

    current_job_definitions = [
        job_definition["jobDefinitionName"]
        for job_definition in batch_client.describe_job_definitions()["jobDefinitions"]
    ]
    if job_definition_name not in current_job_definitions:
        batch_client.register_job_definition(
            jobDefinitionName=job_definition_name, type="container", containerProperties=container_properties
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

    environment_variables_per_job = [
        dict(  # The burden is on the calling script to update the table status to finished
            name="STATUS_TRACKER_TABLE_NAME",
            value=status_tracker_table_name,
        ),
    ]
    if environment_variables is not None:
        environment_variables_per_job.extend([{key: value for key, value in environment_variables.items()}])

    container_overrides = dict(environment=environment_variables_per_job)
    if command is not None:
        container_overrides["command"] = [command]

    job_submission_info = batch_client.submit_job(
        jobQueue=job_queue_name,
        dependsOn=job_dependencies,
        jobDefinition=job_definition_name,
        jobName=job_name,
        containerOverrides=container_overrides,
    )

    # Update DynamoDB status tracking table
    submission_id = submission_id or str(uuid4())
    table_submission_info = dict(
        id=submission_id, job_name=job_name, submitted_on=datetime.now().isoformat(), status="submitted"
    )
    table.put_item(Item=table_submission_info)

    info = dict(job_submission_info=job_submission_info, table_submission_info=table_submission_info)
    return info


def update_table_status(
    *,
    status_tracker_table_name: str,
    submission_id: str,
    status: str,
    region: str = "us-east-2",
) -> None:
    """
    Helper function for updating a status value on a DynamoDB table tracking the status of EC2 jobs.

    Intended for use by the running job to indicate its completion.

    Parameters
    ----------
    status_tracker_table_name : str, default: "neuroconv_batch_status_tracker"
        The name of the DynamoDB table to use for tracking job status.
    submission_id : str
        The random hash that was assigned on submission of this job to the status tracker table.
    status : str
        The new status value to update.
    region : str, default: "us-east-2"
        The AWS region to use for the job.
        us-east-2 (Ohio) is the location of the DANDI Archive, and we recommend all operations be run in that region to
        remove cross-region transfer costs.
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

    table.update_item(Key={"id": submission_id}, AttributeUpdates={"status": {"Action": "PUT", "Value": status}})

    return


def delete_efs_volume(efs_volume_name: str) -> None:
    """
    Delete an EFS volume of a particular name.

    Parameters
    ----------
    efs_volume_name : str
        The name of the EFS volume to delete.
    """
    import boto3

    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

    efs_client = boto3.client(
        service_name="efs",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    all_efs_volumes = efs_client.describe_file_systems()
    all_efs_volumes_by_name = {efs_volume["Name"]: efs_volume for efs_volume in all_efs_volumes["FileSystems"]}

    efs_volume = all_efs_volumes_by_name[efs_volume_name]
    file_system_id = efs_volume["FileSystemId"]
    efs_client.delete_file_system(FileSystemId=file_system_id)

    return None


def deploy_conversion_on_ec2(
    specification_file_path: FilePath,
    transfer_commands: str,
    efs_volume_name: str,
    dandiset_id: str,
    region: str = "us-east-2",
    transfer_method: Literal["rclone"] = "rclone",
    transfer_config_file_path: Optional[FilePath] = None,
    efs_volume_creation_options: Optional[dict] = None,
    status_tracker_table_name: str = "neuroconv_batch_status_tracker",
    cleanup_efs_volume: bool = True,
) -> None:
    """
    Helper function for deploying a YAML-based NeuroConv data conversion in the cloud on AWS EC2 Batch.

    Parameters
    ----------
    specification_file_path : FilePathType
        File path leading to .yml specification file for NWB conversion.
    transfer_commands : str
        The syntax command to send to the transfer method.
        E.g., `transfer_command="rclone copy YOUR_REMOTE:YOUR_SOURCE"`
    efs_volume_name : str
        The name of the EFS volume to attach to the jobs used by the operation.
    dandiset_id : str
        The six-digit Dandiset ID to use when uploading the data.
    region : str, default: "us-east-2"
        The AWS region to use for the job.
        us-east-2 (Ohio) is the location of the DANDI Archive, and we recommend all operations be run in that region to
        remove cross-region transfer costs.
    transfer_method : Literal["rclone"]
        The type of transfer used to move the data from the cloud source to the EFS volume.
        Currently only supports Rclone.
    transfer_config_file_path : FilePath, optional
        Explicit path to the config file used by the transfer method.
        When using `transfer_method = "rclone"`, this defaults to `~/.config/rclone/rclone.conf`.
    efs_volume_creation_options : dict, optional
        The dictionary of keyword arguments to pass to `boto3.client.EFS.create_file_system` when the volmume does not
        already exist.
        These are ignored if the volume already exists.
    status_tracker_table_name : str, default: "neuroconv_batch_status_tracker"
        The name of the DynamoDB table to use for tracking job status.
    cleanup_efs_volume : bool, default: True
        Whether or not to schedule the deletion of the associated `efs_volume_name` when the deployment is complete.
        This is recommended to avoid unnecessary costs from leaving unused resources hanging indefinitely.
        It is also recommended to manually ensure periodically that this cleanup was successful.
    """
    import boto3

    dandi_api_token = os.getenv("DANDI_API_KEY")
    assert dandi_api_token is not None, (
        "Unable to find environment variable 'DANDI_API_KEY'. "
        "Please retrieve your token from DANDI and set this environment variable."
    )

    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

    transfer_config_file_path = transfer_config_file_path or Path().home() / ".config" / "rclone" / "rclone.conf"
    efs_volume_creation_options = efs_volume_creation_options or dict()

    if transfer_method != "rclone":
        raise NotImplementedError(f"The transfer method '{transfer_method}' is not yet supported!")
    if not transfer_config_file_path.exists():
        raise ValueError(f"The `transfer_config_file_path` located at '{transfer_config_file_path}' does not exist!")

    # Make EFS volume if it doesn't already exist
    efs_client = boto3.client(
        service_name="efs",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    all_efs_volumes = efs_client.describe_file_systems()
    all_efs_volumes_by_name = {efs_volume["Name"]: efs_volume for efs_volume in all_efs_volumes["FileSystems"]}

    efs_volume = all_efs_volumes_by_name.get(efs_volume_name, None)
    if efs_volume is None:
        efs_volume_default_creation_kwargs = dict(
            PerformanceMode="generalPurpose",
            # Setting AvailabilityZoneName sets the volume as 'One-Zone', which is cheaper
            AvailabilityZoneName="us-east-2b",
            Tags=[dict(Key="Name", Value=efs_volume_name)],
        )
        efs_volume_creation_kwargs = dict(efs_volume_default_creation_kwargs)
        efs_volume_creation_kwargs.update(**efs_volume_creation_options)

        efs_volume = efs_client.create_file_system(**efs_volume_creation_kwargs)

    # To avoid errors related to name collisions, append all job names with a small unique reference
    unique_job_reference = str(uuid4())[:8]

    # Job 1: Transfer data from source to EFS
    with open(file=transfer_config_file_path) as io:
        rclone_config_file_content = io.read()

    transfer_job_submission_info = submit_aws_batch_job(
        transfer_job_name=Path(specification_file_path).stem + "_transfer_" + unique_job_reference,
        docker_container="ghcr.io/catalystneuro/rclone_with_config:latest",
        efs_volume_name=efs_volume_name,
        environment_variables=[
            dict(name="RCLONE_CONFIG", value=rclone_config_file_content),
            dict(name="RCLONE_COMMANDS", value=transfer_commands),
        ],
        status_tracker_table_name=status_tracker_table_name,
    )

    # Job 2: Run YAML specification on transferred data and upload to DANDI
    with open(file=specification_file_path) as io:
        specification_file_content = io.read()

    submit_aws_batch_job(
        conversion_job_name=Path(specification_file_path).stem + "_conversion_" + unique_job_reference,
        job_dependencies=[{"jobId": transfer_job_submission_info["jobId"], "type": "SEQUENTIAL"}],
        docker_container="ghcr.io/catalystneuro/neuroconv_for_ec2_deployment:dev",
        efs_volume_name=efs_volume_name,
        environment_variables=[
            dict(name="NEUROCONV_YAML", value=specification_file_content),
            dict(name="NEUROCONV_DATA_PATH", value=""),
            dict(name="NEUROCONV_OUTPUT_PATH", value=""),
            dict(name="DANDI_API_KEY", value=dandi_api_token),
            dict(name="DANDISET_ID", value=dandiset_id),
            dict(name="AWS_ACCESS_KEY_ID", value=aws_access_key_id),
            dict(name="AWS_SECRET_ACCESS_KEY", value=aws_secret_access_key),
            dict(name="TRACKING_TABLE", value=status_tracker_table_name),
            dict(name="SUBMISSION_ID", value=transfer_job_submission_info["table_submission_info"]["id"]),
            dict(name="EFS_VOLUME", value=efs_volume_name),
        ],
    )

    return None
