One way of deploying items on AWS Batch is to manually setup the entire workflow through AWS web UI, and to manually submit each jobs in that manner.

Deploying hundreds of jobs in this way would be cumbersome.

Here are two other methods that allow simpler deployment by using `boto3`


Semi-automated Deployment of NeuroConv on AWS Batch
---------------------------------------------------

Step 1: Transfer data to Elastic File System (EFS)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The nice thing about using EFS is that we are only ever billed for our literal amount of disk storage over time, and do not need to specify a particular fixed allocation or scaling stategy.

It is also relatively easy to mount across multiple AWS Batch jobs simultaneously.

Unfortunately, the one downside is that it's pricing per GB-month is significantly higher than either S3 or EBS.

To easily transfer data from a Google Drive (or theoretically any backend supported by `rclone`), set the following environment variables for rclone credentials: `DRIVE_NAME`, `TOKEN`, `REFRESH_TOKEN`, and `EXPIRY`.

.. note:

    I eventually hope to just be able to read and pass these directly from a local `rclone.conf` file, but 

.. note:

    All path references must point to `/mnt/data/` as the base in order to persist across jobs.

.. code:

    import os
    from datetime import datetime

    from neuroconv.tools.data_transfers import submit_aws_batch_job

    job_name = "<unique job name>"
    docker_container = "ghcr.io/catalystneuro/rclone_auto_config:latest"
    efs_name = "<your EFS volume name>"

    log_datetime = str(datetime.now()).replace(" ", ":")  # no spaces in CLI
    RCLONE_COMMAND = f"{os.environ['RCLONE_COMMAND']} -v --config /mnt/data/rclone.conf --log-file /mnt/data/submit-{log_datetime}.txt"

    environment_variables = [
        dict(name="DRIVE_NAME", value=os.environ["DRIVE_NAME"]),
        dict(name="TOKEN", value=os.environ["TOKEN"]),
        dict(name="REFRESH_TOKEN", value=os.environ["REFRESH_TOKEN"]),
        dict(name="EXPIRY", value=os.environ["EXPIRY"]),
        dict(name="RCLONE_COMMAND", value=RCLONE_COMMAND),
    ]

    submit_aws_batch_job(
        job_name=job_name,
        docker_container=docker_container,
        efs_name=efs_name,
        environment_variables=environment_variables,
    )


An example `RCLONE_COMMAND` for a drive named 'MyDrive' and the GIN testing data stored under `/ephy_testing_data/spikeglx/Noise4Sam_g0/` of that drive would be

.. code:

    RCLONE_COMMAND = f"sync MyDrive:/ephy_testing_data/spikeglx/Noise4Sam_g0 /mnt/data/Noise4Sam_g0"


Step 2: Run the YAML Conversion Specificattion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Continuing the example above, if we have the YAML file `test_batch.yml`

.. code:

    metadata:
      NWBFile:
        lab: My Lab
        institution: My Institution

    conversion_options:
      stub_test: True

    data_interfaces:
      ap: SpikeGLXRecordingInterface
      lf: SpikeGLXRecordingInterface

    experiments:
      ymaze:
        metadata:
          NWBFile:
            session_description: Testing batch deployment.

        sessions:
          - nwbfile_name: /mnt/data/test_batch_deployment.nwb
            source_data:
              ap:
                file_path: /mnt/data/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0.ap.bin
              lf:
                file_path: /mnt/data/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0.lf.bin
            metadata:
              NWBFile:
                session_id: test_batch_deployment
              Subject:
                subject_id: "1"
                sex: F
                age: P35D
                species: Mus musculus

then we can run the following stand-alone script to deploy the conversion after confirming Step 1 completed successfully.

.. code:

    from neuroconv.tools.data_transfers import submit_aws_batch_job

    job_name = "<unique job name>"
    docker_container = "ghcr.io/catalystneuro/neuroconv:dev_auto_yaml"
    efs_name = "<name of EFS>"

    yaml_file_path = "/path/to/test_batch.yml"

    with open(file=yaml_file_path) as file:
        YAML_STREAM = "".join(file.readlines()).replace('"', "'")

    environment_variables = [dict(name="YAML_STREAM", value=YAML_STREAM)]

    submit_aws_batch_job(
        job_name=job_name,
        docker_container=docker_container,
        efs_name=efs_name,
        environment_variables=environment_variables,
    )


Step 3: Ensure File Cleanup
~~~~~~~~~~~~~~~~~~~~~~~~~~~

TODO: write a dockerfile to perform this step with the API

It's a good idea to confirm that you have access to your EFS from on-demand resources in case you ever need to go in and perform a manual cleanup operation.

Boot up a EC2 t2.micro instance using AWS Linux 2 image with minimal resources.

Create 2 new security groups, `EFS Target` (no policies set) and `EFS Mount` (set inbound policy to NFS with the `EFS Target` as the source).

On the EC2 instance, change the security group to the `EFS Target`. On the EFS Network settings, add the `EFS Mount` group.

Connect to the EC2 instance and run

.. code:

    mkdir ~/efs-mount-point  # or any other name you want; I do recommend keeping this in the home directory (~) for ease of access though
    sudo mount -t nfs -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport fs-<efs number>.efs.us-east-2.amazonaws.com:/ ~/efs-mount-point  # Note that any operations performed on contents of the mounted volume must utilize sudo

and it _should_ work, but this step is known to have various issues. If you did everything exactly as illustrated above, hopefully it should work. At least it did on 4/2/2023.

You can now read, write, and importantly delete any contents on the EFS.

Until the automated DANDI upload is implemented in YAML functionality, you will need to use this method to manually remove the NWB file.

Even after, you should double check to ensure the `cleanup=True` flag to that function properly executed.



Fully Automated Deployment of NeuroConv on AWS Batch
----------------------------------------------------

Coming soon...

Approach is essentially the same as the semi-automated, I just submit all jobs at the same time with the jobs being dependent on the completion of one another.
