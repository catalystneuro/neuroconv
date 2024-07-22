from neuroconv.tools.data_transfers import (
    estimate_s3_conversion_cost,
    estimate_total_conversion_runtime,
    submit_aws_batch_job,
)


def test_estimate_s3_conversion_cost_standard():
    test_sizes = [
        1,
        100,
        1e3,  # 1 GB
        1e5,  # 100 GB
        1e6,  # 1 TB
        1e7,  # 10 TB
        1e8,  # 100 TB
    ]
    results = [estimate_s3_conversion_cost(total_mb=total_mb) for total_mb in test_sizes]
    assert results == [
        2.9730398740210563e-15,  # 1 MB
        2.973039874021056e-11,  # 100 MB
        2.9730398740210564e-09,  # 1 GB
        2.9730398740210563e-05,  # 100 GB
        0.002973039874021056,  # 1 TB
        0.2973039874021056,  # 10 TB
        29.73039874021056,  # 100 TB
    ]


def test_estimate_total_conversion_runtime():
    test_sizes = [
        1,
        100,
        1e3,  # 1 GB
        1e5,  # 100 GB
        1e6,  # 1 TB
        1e7,  # 10 TB
        1e8,  # 100 TB
    ]
    results = [estimate_total_conversion_runtime(total_mb=total_mb) for total_mb in test_sizes]
    assert results == [
        0.12352941176470589,
        12.352941176470589,
        123.52941176470588,
        12352.94117647059,
        123529.41176470589,
        1235294.1176470588,
        12352941.176470589,
    ]


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
