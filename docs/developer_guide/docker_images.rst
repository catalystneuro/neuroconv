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
