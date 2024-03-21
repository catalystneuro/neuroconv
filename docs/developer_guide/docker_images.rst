Manually Build Docker Images
----------------------------

.. note:: It is recommended to build the docker image on the same system architecture that you intend to run it on, *i.e.*, AWS Linux AMI 64-bit (x86), as it may experience difficulties running on other significantly different systems (like an M1 Mac).

.. note:: The NeuroConv docker container comes prepackaged with all required installations, *i.e.*, equivalent to `pip install neuroconv[full]`. As such it is relatively heavy, so be sure that whatever environment you intend to use it in (such as in continuous integration) has sufficient disk space.


Latest Release
~~~~~~~~~~~~~~

To manually build the most recent release, navigate to the 'neuroconv/dockerfiles' folder and run...

.. code::

    docker build -f neuroconv_latest_release_dockerfile -t neuroconv_latest_release .


Dev Branch
~~~~~~~~~~

Checkout to a specific branch on a local clone, then

.. code::

    docker build -f neuroconv_developer_build_dockerfile -t neuroconv_dev .



Publish Container to GitHub
---------------------------

The `LABEL` is the important item here; it determines the host repository on the GitHub Container Registry (GHCR). In each docker file we wish to publish on the GHCR, we will add this label right after the `FROM` clause

.. code::

    FROM PARENT_IMAGE:TAG
    LABEL org.opencontainers.image.source=https://github.com/catalystneuro/neuroconv

After building the image itself, we can publish the container with

.. code::

    docker tag IMAGE_NAME ghcr.io/catalystneuro/IMAGE_NAME:TAG
    export CR_PAT="<YOUR GITHUB SECRET TOKEN>"
    echo $CR_PAT | docker login ghcr.io -u <YOUR GITHUB USERNAME> --password-stdin
    docker push ghcr.io/catalystneuro/IMAGE_NAME:TAG

.. note:: Though it may appear confusing, the use of the `IMAGE_NAME` in these steps determines only the _name_ of the package as available from the 'packages' screen of the host repository; the `LABEL` itself ensured the upload and linkage to the NeuroConv GHCR.



Running Docker Container on local YAML (Linux)
----------------------------------------------

You can either perform a manual build locally following the instructions above, or pull the container from the GitHub Container Registry (GHCR) with

.. code::

    docker pull ghcr.io/catalystneuro/neuroconv:latest

and can then run the entrypoint (equivalent to the usual CLI usage) on a YAML specification file (named `your_specification_file.yml`) with

.. code::

    docker run -it --volume /your/local/drive/:/desired/alias/of/drive/ ghcr.io/catalystneuro/neuroconv:latest neuroconv /desired/alias/of/drive/your_specification_file.yml



Running Docker Container with a YAML_STREAM (Linux)
---------------------------------------------------

An alternative approach that simplifies usage on AWS Batch is to specify the YAML contents as an environment variable. The file is constructed in the first step of the container launch. The only potential downside with this usage is maximum file size (~13,000 characters; current example files do not come remotely close to this).

Otherwise, the YAML file transfer will have to be managed separately, likely as a part of the data transfer or an entirely separate transfer step.

To use manually outside of AWS Batch,

.. code::

    export YAML_STREAM="<copy and paste contents of YAML file (manually replace instances of double quotes with single quotes)>"
    docker run -it --volume /your/local/drive/:/desired/alias/of/drive/ ghcr.io/catalystneuro/neuroconv:dev_auto_yaml

To use automatically via a Python helper function (coming in a separate PR)

.. code::

    import os

    with open(file="my_yaml_file.yml") as file:
        yaml_stream = "".join(file.readlines()).replace("\"", "'")

    os.environ["YAML_STREAM"] = yaml_stream

.. note::

    When  using YAML files through the docker containers, always be sure that the NWB file paths are absolute paths stemming from the mounted volume; otherwise, the NWB file will indeed be written inside the container but will not be accessible outside of it.


Demo
----

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

    docker run -t --volume /Users/MyUser/demo_neuroconv_docker:/demo_neuroconv_docker/ ghcr.io/catalystneuro/neuroconv:latest neuroconv /demo_neuroconv_docker/test_docker_yaml.yml
