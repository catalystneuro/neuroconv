Manually Build Docker Images
----------------------------

.. note::

    It is recommended to build the docker image on the same system architecture that you intend to run it on, *i.e.*, AWS Linux AMI 64-bit (x86), as it may experience difficulties running on other significantly different systems (like an M1 Mac).

.. note::

    The NeuroConv docker container comes prepackaged with all required installations, equivalent to running ``pip install "neuroconv[full]"``. As such it is relatively heavy, so be sure that whatever environment you intend to use it in (such as in continuous integration) has sufficient disk space.


Latest Release
~~~~~~~~~~~~~~

To manually build the most recent release, navigate to the ``neuroconv/dockerfiles`` folder and run...

.. code::

    docker build -f neuroconv_latest_release_dockerfile -t neuroconv_latest_release .


Dev Branch
~~~~~~~~~~

Checkout to a specific branch on a local clone, then...

.. code::

    docker build -f neuroconv_dev_dockerfile -t neuroconv_dev .



Publish Container to GitHub
---------------------------

The ``LABEL`` is important to include as it determines the host repository on the GitHub Container Registry (GHCR). In each dockerfile we wish to publish on the GHCR, we will add this label right after the ``FROM`` clause...

.. code::

    FROM PARENT_IMAGE:TAG
    LABEL org.opencontainers.image.source=https://github.com/catalystneuro/neuroconv

After building the image itself, we can publish the container with...

.. code::

    docker tag IMAGE_NAME ghcr.io/catalystneuro/IMAGE_NAME:TAG
    export CR_PAT="<YOUR GITHUB SECRET TOKEN>"
    echo $CR_PAT | docker login ghcr.io -u <YOUR GITHUB USERNAME> --password-stdin
    docker push ghcr.io/catalystneuro/IMAGE_NAME:TAG

.. note::

    Though it may appear confusing, the use of the ``IMAGE_NAME`` in these steps determines only the _name_ of the package as available from the 'packages' screen of the host repository; the ``LABEL`` itself ensured the upload and linkage to the NeuroConv GHCR.

All our docker images can be built in GitHub Actions (for Ubuntu) and pushed automatically to the GHCR by manually triggering their respective workflow. Keep in mind that most of them are on semi-regular CRON schedules, though.



Run Docker container on local YAML conversion specification file
----------------------------------------------------------------

You can either perform a manual build locally following the instructions above, or pull the container from the GitHub Container Registry (GHCR) with...

.. code::

    docker pull ghcr.io/catalystneuro/neuroconv:latest

and can then run the entrypoint (equivalent to the usual command line usage) on a YAML specification file (named ``your_specification_file.yml``) with...

.. code::

    docker run -it --volume /your/local/volume/:/desired/alias/of/volume/ ghcr.io/catalystneuro/neuroconv:latest neuroconv /desired/alias/of/drive/your_specification_file.yml



.. _developer_docker_details:

Run Docker container on YAML conversion specification environment variable
--------------------------------------------------------------------------

An alternative approach that simplifies usage on systems such as AWS Batch is to specify the YAML contents as an environment variable. The YAML file is constructed in the first step of the container launch.

The only potential downside with this usage is the maximum size of an environment variable (~13,000 characters). Typical YAML specification files should not come remotely close to this limit. This is contrasted to the limits on the CMD line of any docker container, which is either 8192 characters for Windows or either 64 or 128 KiB depending on UNIX build.

Otherwise, in any cloud deployment, the YAML file transfer will have to be managed separately, likely as a part of the data transfer or an entirely separate step.

To use this alternative image on a local environment, you no longer need to invoke the ``neuroconv`` entrypoint pointing to a file. Instead, just set the environment variables and run the docker container on the mounted volume...

.. code::

    export YAML_STREAM="<copy and paste contents of YAML file (manually replace instances of double quotes with single quotes)>"
    export NEUROCONV_DATA_PATH="/desired/alias/of/volume/"
    export NEUROCONV_OUTPUT_PATH="/desired/alias/of/volume/"
    docker run -it --volume /your/local/volume/:/desired/alias/of/volume/ ghcr.io/catalystneuro/neuroconv:yaml_variable

.. note::

    On Windows, use ``set`` instead of ``export``.
