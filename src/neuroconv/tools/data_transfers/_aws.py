"""Collection of helper functions for assessing and performing automated data transfers related to AWS."""

import json
from datetime import datetime
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
    job_name: str,
    docker_container: str,
    # rclone_config_file_path: Optional[str] = None,
    region: str = "us-east-2",
    status_tracker_table_name: str = "neuroconv_batch_status_tracker",
    iam_role_name: str = "neuroconv_batch_role",
    compute_environment_name: str = "neuroconv_batch_environment",
    job_queue_name: str = "neuroconv_batch_queue",
) -> None:
    # assert (
    #     "DANDI_API_KEY" in os.environ
    # ), "You must set your DANDI API key as the environment variable 'DANDI_API_KEY' to submit this job!"
    #
    # default_rclone_config_file_path = pathlib.Path.home() / ".config" / "rclone" / "rclone.conf"
    # rclone_config_file_path = rclone_config_file_path or default_rclone_config_file_path
    # if not rclone_config_file_path.exists():
    #     raise ValueError("You must configure rclone on your local system to submit this job!")
    # with open(file=rclone_config_file_path, mode="r") as io:
    #     rclone_config_file_stream = io.read()

    import boto3

    dynamodb_client = boto3.client("dynamodb", region)
    dynamodb_resource = boto3.resource("dynamodb", region)
    iam_client = boto3.client("iam", region)
    batch_client = boto3.client("batch", region)

    # It is extremely useful to have a status tracker that is separate from the job environment
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
                dict(Effect="Allow", Principal=dict(Service="ecs-tasks.amazonaws.com"), Action="sts:AssumeRole")
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
                "minvCpus": 0,  # TODO, control
                "maxvCpus": 256,  # TODO, control
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
    job_definition = f"neuroconv_batch_{docker_container}"  # Keep unique by incorporating name of container
    current_job_definitions = [
        definition["jobDefinitionName"] for definition in batch_client.describe_job_queues()["jobDefinitions"]
    ]
    if job_definition not in current_job_definitions:
        batch_client.register_job_definition(
            jobDefinitionName=job_definition,
            type="container",
            containerProperties=dict(
                image=docker_container,
                memory=256,  # TODO, control
                vcpus=16,  # TODO, control
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
        # TODO: would also need to check that memory/vcpu values resolve with previously defined name
        pass

    # Submit job and update status tracker
    currently_running_jobs = batch_client.list_jobs(jobQueue=job_queue_name)
    if job_name not in currently_running_jobs:
        batch_client.submit_job(
            jobQueue=job_queue_name,
            jobDefinition=job_definition,
            jobName=job_name,
            containerOverrides=dict(
                # Set environment variables
                environment=[
                    dict(  # The burden is on the calling script to update the table status to finished
                        name="STATUS_TRACKER_TABLE_NAME",
                        value=status_tracker_table_name,
                    ),
                    # dict(  # For rclone transfers
                    #     name="RCLONE_CREDENTIALS",
                    #     value=os.environ["RCLONE_CREDENTIALS"],
                    # ),
                    # dict(  # For rclone transfers
                    #     name="DANDI_API_KEY",
                    #     value=os.environ["DANDI_API_KEY"],
                    # ),
                ]
            ),
        )
        table.put_item(Item=dict(id=uuid4(), job_name=job_name, submitted_on=datetime.now(), status="submitted"))
    else:
        raise ValueError(
            f"There is already a job named '{job_name}' running in the queue! "
            "If you are submitting multiple jobs, each will need a unique name."
        )
