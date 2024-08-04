from neuroconv.tools.data_transfers import submit_aws_batch_job


def test_submit_aws_batch_job():
    job_name = "test_submit_aws_batch_job"
    docker_image = "ubuntu:latest"
    command = "echo 'Testing NeuroConv AWS Batch submission."

    submit_aws_batch_job(
        job_name=job_name,
        docker_image=docker_image,
        command=command,
    )


def test_submit_aws_batch_job_with_dependencies():
    job_name_1 = "test_submit_aws_batch_job_with_dependencies_1"
    docker_image = "ubuntu:latest"
    command_1 = "echo 'Testing NeuroConv AWS Batch submission."

    info = submit_aws_batch_job(
        job_name=job_name_1,
        docker_image=docker_image,
        command=command_1,
    )
    job_submission_info = info["job_submission_info"]

    job_name_2 = "test_submit_aws_batch_job_with_dependencies_1"
    command_2 = "echo 'Testing NeuroConv AWS Batch submission with dependencies."
    job_dependencies = [{"jobId": job_submission_info["jobId"], "type": "SEQUENTIAL"}]
    submit_aws_batch_job(
        job_name=job_name_2,
        docker_image=docker_image,
        command=command_2,
        job_dependencies=job_dependencies,
    )
