NeuroConv AWS Demo
------------------

The :ref:`neuroconv.tools.aws <api_docs_aws_tools>` submodule provides a number of tools for deploying NWB conversions
within AWS cloud services. These tools are primarily for facilitating source data transfers from cloud storage
sources to AWS, where the NWB conversion takes place, following by immediate direct upload to the `Dandi Archive <https://dandiarchive.org/>`_.

The following is an explicit demonstration of how to use these to create a pipeline to run a remote data conversion.

This tutorial relies on setting up several cloud-based aspects ahead of time:

a. Download some of the GIN data from the main testing suite, see :ref:`example_data` for more
details. Specifically, you will need the ``spikeglx`` and ``phy`` folders.

b. Have access to a `Google Drive <https://wwww.drive.google.com>`_ folder to mimic a typical remote storage
location. The example data from (a) only takes up about 20 MB of space, so ensure you have that available. In
practice, any `cloud storage provider that can be accessed via Rclone <https://rclone.org/#providers>`_ can be used.

c. Install `Rclone <https://rclone.org>`_,  run ``rclone config``, and follow all instructions while giving your
remote the name ``test_google_drive_remote``. This step is necessary to provide the necessary credentials to access
the Google Drive folder from other locations by creating a file called ``rclone.conf``. You can find the path to
file, which you will need for a later step, by running ``rclone config file``.

d. Have access to an `AWS account <https://aws.amazon.com/resources/create-account/>`_. Then, from
the `AWS console <https://aws.amazon.com/console/>`_, sign in and navigate to the "IAM" page. Here, you will
generate some credentials by creating a new user with programmatic access. Save your access key and secret key
somewhere safe (such as installing the `AWS CLI <https://aws.amazon.com/cli>`_ and running ``aws configure``
to store the values on your local device).

e. Have access to an account on both the `staging/testing server <https://gui-staging.dandiarchive.org/>`_ (you
will probably want one on the main archive as well, but please do not upload demonstration data to the primary
server). This request can take a few days for the admin team to process. Once you have access, you will need
to create a new Dandiset on the staging server and record the six-digit Dandiset ID.

.. warning::

    *Cloud costs*. While the operations deployed on your behalf by NeuroConv are optimized to the best extent we can, cloud services can still become expensive. Please be aware of the costs associated with running these services and ensure you have the necessary permissions and budget to run these operations. While NeuroConv makes every effort to ensure there are no stalled resources, it is ultimately your responsibility to monitor and manage these resources. We recommend checking the AWS dashboards regularly while running these operations, manually removing any spurious resources, and setting up billing alerts to ensure you do not exceed your budget.

Then, to setup the remaining steps of the tutorial:

1. In your Google Drive, make a new folder for this demo conversion named ``demo_neuroconv_aws`` at the outermost
level (not nested in any other folders).

2. Create a file on your local device named ``demo_neuroconv_aws.yml`` with the following content:

.. code-block:: yaml

    metadata:
      NWBFile:
        lab: My Lab
        institution: My Institution

    data_interfaces:
      ap: SpikeGLXRecordingInterface
      phy: PhySortingInterface

    upload_to_dandiset: "< enter your six-digit Dandiset ID here >"

    experiments:
      my_experiment:
        metadata:
          NWBFile:
            session_description: My session.

        sessions:
          - source_data:
              ap:
                file_path: spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0.ap.bin
            metadata:
              NWBFile:
                session_start_time: "2020-10-10T21:19:09+00:00"
              Subject:
                subject_id: "1"
                sex: F
                age: P35D
                species: Mus musculus
          - metadata:
              NWBFile:
                session_start_time: "2020-10-10T21:19:09+00:00"
              Subject:
                subject_id: "002"
                sex: F
                age: P35D
                species: Mus musculus
            source_data:
              phy:
                folder_path: phy/phy_example_0/


3. Copy and paste the ``Noise4Sam_g0`` and ``phy_example_0`` folders from the :ref:`example_data` into this demo
folder so that you have the following structure...

.. code::

    demo_neuroconv_aws/
    ¦   demo_output/
    ¦   spikeglx/
    ¦   +-- Noise4Sam_g0/
    ¦   +-- ... # .nidq streams
    ¦   ¦   +-- Noise4Sam_g0_imec0/
    ¦   ¦   +-- Noise4Sam_g0_t0.imec0.ap.bin
    ¦   ¦   +-- Noise4Sam_g0_t0.imec0.ap.meta
    ¦   ¦   +-- ...  # .lf streams
    ¦   phy/
    ¦   +-- phy_example_0/
    ¦   ¦   +--  ...  # The various file contents from the example Phy folder

4. Now run the following Python code to deploy the AWS Batch job:

.. code:: python

        from neuroconv.tools.aws import deploy_neuroconv_batch_job

        rclone_command = (
            "rclone copy test_google_drive_remote:demo_neuroconv_aws /mnt/efs/source "
            "--verbose --progress --config ./rclone.conf"
        )

        # Remember - you can find this via `rclone config file`
        rclone_config_file_path = "/path/to/rclone.conf"

        yaml_specification_file_path = "/path/to/demo_neuroconv_aws.yml"

        job_name = "demo_deploy_neuroconv_batch_job"
        efs_volume_name = "demo_deploy_neuroconv_batch_job"
        deploy_neuroconv_batch_job(
            rclone_command=rclone_command,
            yaml_specification_file_path=yaml_specification_file_path,
            job_name=job_name,
            efs_volume_name=efs_volume_name,
            rclone_config_file_path=rclone_config_file_path,
        )

Voilà! If everything occurred successfully, you should eventually (~2-10 minutes) see the files uploaded to your
Dandiset on the staging server. You should also be able to monitor the resources running in the AWS Batch dashboard
as well as on the DynamoDB table.
