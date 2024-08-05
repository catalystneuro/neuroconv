import os
import time

import boto3

from neuroconv.tools.aws import submit_aws_batch_job


def test_submit_aws_batch_job():
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
        region_name="us-east-2",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    job_name = "test_submit_aws_batch_job"
    docker_image = "ubuntu:latest"
    command = "echo 'Testing NeuroConv AWS Batch submission."

    info = submit_aws_batch_job(
        job_name=job_name,
        docker_image=docker_image,
        command=command,
    )

    # Wait for AWS to process the job
    time.sleep(60)

    job_id = info["job_submission_info"]["jobId"]

    all_jobs_response = batch_client.describe_jobs(jobs=[job_id])
    assert all_jobs_response["ResponseMetadata"]["HTTPStatusCode"] == 200

    jobs = jobs_response["jobs"]
    assert len(jobs) == 1

    job = jobs[0]
    assert job["jobName"] == job_name
    assert "neuroconv_batch_queue" in job["jobQueue"]
    assert "neuroconv_batch_ubuntu-latest-image_4-GiB-RAM_4-CPU" in job["jobDefinition"]
    assert job["status"] == "SUCCEEDED"

    status_tracker_table_name = "neuroconv_batch_status_tracker"
    table = dynamodb_resource.Table(name=status_tracker_table_name)
    submission_id = info["table_submission_info"]["submission_id"]

    table_item_response = table.get_item(Key={"id": submission_id})
    assert table_item_response["ResponseMetadata"]["HTTPStatusCode"] == 200

    table_item = table_item_response["Item"]
    assert table_item["job_name"] == job_name
    assert table_item["status"] == "Job submitted..."

    table.update_item(
        Key={"id": submission_id}, AttributeUpdates={"status": {"Action": "PUT", "Value": "Test passed."}}
    )


def test_submit_aws_batch_job_with_dependencies():
    job_name_1 = "test_submit_aws_batch_job_with_dependencies_1"
    docker_image = "ubuntu:latest"
    command_1 = "echo 'Testing NeuroConv AWS Batch submission."

    job_info_1 = submit_aws_batch_job(
        job_name=job_name_1,
        docker_image=docker_image,
        command=command_1,
    )

    job_name_2 = "test_submit_aws_batch_job_with_dependencies_1"
    command_2 = "echo 'Testing NeuroConv AWS Batch submission with dependencies."
    job_dependencies = [{"jobId": job_submission_info["jobId"], "type": "SEQUENTIAL"}]
    job_info_2 = submit_aws_batch_job(
        job_name=job_name_2,
        docker_image=docker_image,
        command=command_2,
        job_dependencies=job_dependencies,
    )

    # Wait for AWS to process the jobs
    time.sleep(120)

    job_id_1 = job_info_1["job_submission_info"]["jobId"]
    job_id_2 = job_info_2["job_submission_info"]["jobId"]

    all_jobs_response = batch_client.describe_jobs(jobs=[job_id_1, job_id_2])
    assert all_jobs_response["ResponseMetadata"]["HTTPStatusCode"] == 200

    jobs_by_id = {job["jobId"]: job for job in jobs_response["jobs"]}
    assert len(jobs_by_id) == 2

    job_1 = jobs_by_id[job_id_1]
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

    submission_id_1 = job_info_1["table_submission_info"]["submission_id"]
    table_item_response_1 = table.get_item(Key={"id": submission_id_1})
    assert table_item_response_1["ResponseMetadata"]["HTTPStatusCode"] == 200

    table_item_1 = table_item_response_1["Item"]
    assert table_item_1["job_name"] == job_name
    assert table_item_1["status"] == "Job submitted..."

    submission_id_2 = job_info_2["table_submission_info"]["submission_id"]
    table_item_response_2 = table.get_item(Key={"id": submission_id_2})
    assert table_item_response_2["ResponseMetadata"]["HTTPStatusCode"] == 200

    table_item_2 = table_item_response_2["Item"]
    assert table_item_2["job_name"] == job_name
    assert table_item_2["status"] == "Job submitted..."

    table.update_item(
        Key={"id": submission_id_1}, AttributeUpdates={"status": {"Action": "PUT", "Value": "Test passed."}}
    )
    table.update_item(
        Key={"id": submission_id_2}, AttributeUpdates={"status": {"Action": "PUT", "Value": "Test passed."}}
    )
