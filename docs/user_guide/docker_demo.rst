NeuroConv Docker Demo
---------------------

The following is an explicit demonstration of how to use the Docker-based NeuroConv YAML specification via the command line.

It relies on some of the GIN data from the main testing suite, see :ref:`example_data` for more details.


.. note::

    Docker relies heavily on absolute system paths, but these can vary depending on your system.

    For Windows, this might be something like: ``C:/Users/MyUser/Downloads/``.

    For MacOSX it might be: ``/Users/username/``.

    For this demo, we will use the home directory of an Ubuntu (Linux) system for a user named 'MyUser' as our base: ``/home/MyUser``.


.. note::

    For Unix systems (MacOSX/Linux) you will likely require sudo access in order to run the ``docker`` based commands.

    If this is the case for your system, then any time you see the ``docker`` usage on the command like you will need to prepend as ``sudo docker``.


1. In your base directory (which this demo will refer to as ``/home/MyUser/``), make a new folder for the demo conversion named ``demo_neuroconv_docker``.

2. Make a subfolder in ``demo_neuroconv_docker`` called ``demo_output``.

3. Create a file in this folder named ``demo_neuroconv_docker_yaml.yml`` with the following content...

.. code-block:: yaml

    metadata:
      NWBFile:
        lab: My Lab
        institution: My Institution

    data_interfaces:
      ap: SpikeGLXRecordingInterface
      phy: PhySortingInterface

    experiments:
      my_experiment:
        metadata:
          NWBFile:
            session_description: My session.

        sessions:
          - nwbfile_name: spikeglx_from_docker_yaml.nwb
            source_data:
              ap:
                file_path: /demo_neuroconv_docker/spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0.ap.bin
            metadata:
              NWBFile:
                session_start_time: "2020-10-10T21:19:09+00:00"
              Subject:
                subject_id: "1"
                sex: F
                age: P35D
                species: Mus musculus
          - nwbfile_name: phy_from_docker_yaml.nwb
            metadata:
              NWBFile:
                session_start_time: "2020-10-10T21:19:09+00:00"
              Subject:
                subject_id: "002"
                sex: F
                age: P35D
                species: Mus musculus
            source_data:
              phy:
                folder_path: /demo_neuroconv_docker/phy/phy_example_0/


4. To make things easier for volume mounting, copy and paste the ``Noise4Sam_g0`` and ``phy_example_0`` folders into this Docker demo folder so that you have the following folder structure...

.. code::

    demo_neuroconv_docker/
    ¦   demo_output/
    ¦   demo_neuroconv_docker_yaml.yml
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

5. Pull the latest NeuroConv docker image from GitHub...

.. code::

    docker pull ghcr.io/catalystneuro/neuroconv:latest

6. Run the command line interface on the YAML file using the docker container (instead of a local installation of the Python package)...

.. code::

    docker run -t \
        --volume /home/user/demo_neuroconv_docker:/demo_neuroconv_docker \
        ghcr.io/catalystneuro/neuroconv:latest \
        neuroconv /demo_neuroconv_docker/demo_neuroconv_docker_yaml.yml \
        --output-folder-path /demo_neuroconv_docker/demo_output

Voilà! If everything occurred successfully, you should see...

.. code::

    Source data is valid!
    Metadata is valid!
    conversion_options is valid!
    NWB file saved at /demo_neuroconv_docker/demo_output/spikeglx_from_docker_yaml.nwb!
    Source data is valid!
    Metadata is valid!
    conversion_options is valid!
    NWB file saved at /demo_neuroconv_docker/demo_output/phy_from_docker_yaml.nwb!




RClone With Config Docker Demo
------------------------------

NeuroConv also supports a convenient Docker image for running data transfers via `Rclone <https://rclone.org>`_.

To use this image, you must first configure the remote locally by calling:

.. code::

    rclone config

And following all interactive instructions (defaults are usually sufficient).

The Docker image requires two environment variables to be set (see :ref:`developer_docker_details` for more details in a related process).

- ``RCLONE_CONFIG``: The full file content of the rclone.conf file on your system. You can find this by calling ``rclone config file``. On UNIX, for example, you can set this variable using ``RCLONE_CONFIG=$(<rclone.conf)`` from the folder containing the file
- ``RCLONE_COMMAND``: The Rclone command to run. For example, ``remote_name:source_folder destination_folder --verbose --progress --config ./rclone.conf``, where ``remote_name`` is the name used during initial setup through ``rclone config``, ``source_folder`` is the name of the folder you wish to transfer data from on that remote, and ``destination_folder`` is the local folder to transfer the data to.

Then, you can use the following command to run the Rclone Docker image:

.. code::

    docker run -t \
        --volume destination_folder:destination_folder \
        -e RCLONE_CONFIG="$RCLONE_CONFIG" \
        -e RCLONE_COMMAND="$RCLONE_COMMAND" \
        ghcr.io/catalystneuro/rclone_with_config:latest

This image is particularly designed for convenience with AWS Batch (EC2) tools that rely heavily on atomic Docker operations. Alternative AWS approaches would have relied on transferring the Rclone configuration file to the EC2 instances using separate transfer protocols or dependent steps, both of which add complexity to the workflow.
