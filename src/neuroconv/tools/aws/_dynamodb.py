"""Helper functions for operations on DynamoDB tables."""

import os


def update_table_status(
    *,
    submission_id: str,
    status: str,
    status_tracker_table_name: str = "neuroconv_batch_status_tracker",
    region: str = "us-east-2",
) -> None:
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
    region : str, default: "us-east-2"
        The AWS region to use for the job.
    """
    import boto3

    aws_access_key_id = os.environ["AWS_ACCESS_KEY_ID"]
    aws_secret_access_key = os.environ["AWS_SECRET_ACCESS_KEY"]

    dynamodb_resource = boto3.resource(
        service_name="dynamodb",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    table = dynamodb_resource.Table(name=status_tracker_table_name)

    table.update_item(Key={"id": submission_id}, AttributeUpdates={"status": {"Action": "PUT", "Value": status}})

    return None
