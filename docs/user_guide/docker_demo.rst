Docker Demo
-----------

The following is an explicit demonstration of how to use the Docker-based CLI for NeuroConv.

It relies on some of the GIN data from the main testing suite, see :ref:`example_data` for more details.

1. Make a new folder for the demo conversion named ``demo_neuroconv_docker``.

2. Make a subfolder in ``demo_neuroconv_docker`` called ``demo_output``.

3. Make a new file in this folder named ``demo_neuroconv_docker_yaml.yml``.

4. Open this YAML file in a text editor, then copy and paste the following section into that file.

.. code::

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


5. To make things easier for volume mounting, copy and paste the ``Noise4Sam_g0`` and ``phy_example_0`` folders into this Docker demo folder so that you have the following folder structure...

.. code::

    | demo_neuroconv_docker/
    |-- demo_output/
    |-- demo_neuroconv_docker_yaml.yml
    |-- spikeglx/
    |---- Noise4Sam_g0/
    |------ Noise4Sam_g0_imec0/
    |-------- Noise4Sam_g0_t0.imec0.ap.bin
    |-------- Noise4Sam_g0_t0.imec0.ap.meta
    |-- phy/
    |---- phy_example_0/
    |------ ...  # The various file contents from the example Phy folder

6. Pull the latest NeuroConv docker image from GitHub...

.. code::

    docker pull ghcr.io/catalystneuro/neuroconv:latest

7. Run the command line interface on the YAML file using the docker container (instead of a local installation of the Python package)...

.. code::

    docker run -t --volume <insert your system dependent absolute path to the demo folder>/demo_neuroconv_docker:/demo_neuroconv_docker/ ghcr.io/catalystneuro/neuroconv:latest neuroconv test_docker_yaml.yml

.. note:: Docker relies heavily on absolute system paths, but these can vary depending on your system. For Windows, this might be something like ``C:/Users/MyUser/Downloads/``, for MacOSX it might be ``/Users/username/``.

For example, assuming a MacOSX user with username 'MyUser', and assuming the ``demo_neuroconv_docker`` folder was created in the home directory, this would look like

.. code::

    docker run -t --volume /Users/MyUser/demo_neuroconv_docker:/demo_neuroconv_docker/ ghcr.io/catalystneuro/neuroconv:latest neuroconv /demo_neuroconv_docker/test_docker_yaml.yml --output-folder demo_output
