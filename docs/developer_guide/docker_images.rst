Manually Build Docker Images
----------------------------

.. note: It is highly recommended to build the docker image on the same basic system or architecture type that you intend to run it on, *i.e.*, AWS Linux AMI 64-bit (x86), as it may experience difficulties running on other radically different systems (like an M1 Mac).

.. note: The NeuroConv docker container comes prepackaged with all required installations, *i.e.*, equivalent to `pip install neuroconv[full]`. As such it is fairly heavy, so be sure that whatever system (or specifically CI environment) you build with has sufficient disk space.

.. code:

    docker build -f neuroconv_dockerfile -t neuroconv .



Publish Container to GitHub
---------------------------

The `LABEL` is the important item here. In each docker file we wish to publish on the GitHub Container Registry (GHCR), we will label them such as

.. code:

    LABEL org.opencontainers.image.source=https://github.com/OWNER/REPO

After building the image, publish the container with

.. code:

    docker tag IMAGE_NAME ghcr.io/catalystneuro/neuroconv:TAG
    export CR_PAT="<YOUR GITHUB SECRET TOKEN>"
    echo $CR_PAT | docker login ghcr.io -u <YOUR GITHUB USERNAME> --password-stdin
    docker push ghcr.io/catalystneuro/neuroconv:TAG



Running Docker Container (Linux)
--------------------------------

You can either perform a manual build locally following the instructions above, or pull the container from the GitHub Container Registry (GHCR) with

.. code:

    docker pull ghcr.io/catalystneuro/neuroconv:latest
    
and can then run the entrypoint (equivalent to the usual CLI usage) on a YAML specification file (named `your_specification_file.yml`) with

.. code:

    docker run -it --volume /your/local/drive/:/desired/alias/of/drive/ ghcr.io/catalystneuro/neuroconv:latest neuroconv /desired/alias/of/drive/your_specification_file.yml
