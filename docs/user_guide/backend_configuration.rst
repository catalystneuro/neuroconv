Backend Configuration
=====================

NeuroConv offers convenient control over the type of file backend and the way each dataset is configured.

Find out more about possible backend formats in the `main NWB documentation <https://nwb-overview.readthedocs.io/en/latest/faq_details/why_hdf5.html#why-use-hdf5-as-the-primary-backend-for-nwb>`_.

Find out more about chunking and compression in the `advanced NWB tutorials for dataset I/O settings <https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/h5dataio.html#sphx-glr-tutorials-advanced-io-h5dataio-py>`_.

Find out more about memory buffering of large source files in the `advanced NWB tutorials for iterative data write <https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/plot_iterative_write.html#sphx-glr-tutorials-advanced-io-plot-iterative-write-py>`_.



Default configuration
---------------------

To retrieve a default configuration for an in-memory ``pynwb.NWBFile`` object, use the :py:meth:`~neuroconv.tools.nwb_helpers.get_default_backend_configuration` function:

.. code-block:: python

    from datetime import datetime
    from uuid import uuid4

    from neuroconv.tools.nwb_helpers import get_default_backend_configuration
    from pynwb import NWBFile, TimeSeries

    session_start_time = datetime(2020, 1, 1, 12, 30, 0)
    nwbfile = NWBFile(
        identifier=str(uuid4()),
        session_start_time=session_start_time,
        session_description="A session of my experiment.",
    )

    time_series = TimeSeries(
        name="MyTimeSeries",
        description="A time series from my experiment.",
        unit="cm/s",
        data=[1., 2., 3.],
        timestamps=[0.0, 0.2, 0.4],
    )
    nwbfile.add_acquisition(time_series)

    backend_configuration = get_default_backend_configuration(
        nwbfile=nwbfile, backend="hdf5"
    )

From which a printout of the contents:

.. code-block:: python

    print(backend_configuration)

returns:

.. code-block:: bash

    HDF5 dataset configurations
    ---------------------------

    acquisition/MyTimeSeries/data
    -----------------------------
      dtype : float64
      full shape of source array : (3,)
      full size of source array : 24 B

      buffer shape : (3,)
      expected RAM usage : 24 B

      chunk shape : (3,)
      disk space usage per chunk : 24 B

      compression method : gzip

    acquisition/MyTimeSeries/timestamps
    -----------------------------------
      dtype : float64
      full shape of source array : (3,)
      full size of source array : 24 B

      buffer shape : (3,)
      expected RAM usage : 24 B

      chunk shape : (3,)
      disk space usage per chunk : 24 B

      compression method : gzip



Customization
-------------

To modify the chunking or buffering patterns and compression method or options, change those values in the ``.dataset_configurations`` object using the location of each dataset as a specifier.

Let's demonstrate this by modifying everything we can for the ``data`` field of the ``TimeSeries`` object generated above:

.. code-block:: python


    dataset_configurations = backend_configuration.dataset_configurations
    dataset_configuration = dataset_configurations["acquisition/MyTimeSeries/data"]

    dataset_configuration.chunk_shape = (1,)
    dataset_configuration.buffer_shape = (2,)
    dataset_configuration.compression_method = "Zstd"
    dataset_configuration.compression_options = dict(clevel=3)

We can confirm these values are saved by re-printing that particular dataset configuration:

.. code-block:: python

    print(dataset_configuration)

.. code-block:: bash

    acquisition/MyTimeSeries/data
    -----------------------------
      dtype : float64
      full shape of source array : (3,)
      full size of source array : 24 B

      buffer shape : (2,)
      expected RAM usage : 16 B

      chunk shape : (1,)
      disk space usage per chunk : 8 B

      compression method : Zstd
      compression options : {'clevel': 3}

Then we can use this configuration to write the NWB file:

.. code-block:: python

    from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile

    dataset_configurations["acquisition/MyTimeSeries/data"] = dataset_configuration

    configure_and_write_nwbfile(nwbfile=nwbfile, backend_configuration=backend_configuration, output_filepath="output.nwb")


Interfaces and Converters
-------------------------

A similar workflow can be used when writing an NWB file using a ``DataInterface`` or ``NWBConverter`` is simple to configure.

Having get_default_backend_configuration as a method of the DataInterface and NWBConverter classes allows descending
classes to override the default configuration.

The following example uses the :ref:`example data <example_data>` available from the testing repo:

.. code-block:: python

    from datetime import datetime

    from zoneinfo import ZoneInfo
    from neuroconv import ConverterPipe
    from neuroconv.datainterfaces import SpikeGLXRecordingInterface, PhySortingInterface
    from neuroconv.tools.nwb_helpers import (
        make_or_load_nwbfile,
        get_default_backend_configuration,
        configure_backend,
    )

    # Instantiate interfaces and converter
    ap_interface = SpikeGLXRecordingInterface(
        file_path=".../spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0.ap.bin"
    )
    phy_interface = PhySortingInterface(
        folder_path=".../phy/phy_example_0"
    )

    data_interfaces = [ap_interface, phy_interface]
    converter = ConverterPipe(data_interfaces=data_interfaces)

    # Fetch available metadata
    metadata = converter.get_metadata()

    # Create the in-memory NWBFile object and retrieve a default configuration for the backend
    nwbfile = converter.create_nwbfile(metadata=metadata)
    backend_configuration = converter.get_default_backend_configuration(
        nwbfile=nwbfile,
        backend="hdf5",
    )

    # Make any modifications to the configuration in this step, for example...
    dataset_configurations = backend_configuration.dataset_configurations
    dataset_configuration = dataset_configurations["acquisition/ElectricalSeriesAP/data"]
    dataset_configuration.compression_method = "Blosc"

    # Configure and write the NWB file
    nwbfile_path = "./my_nwbfile_name.nwb"
    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        nwbfile=nwbfile,
        backend_configuration=backend_configuration,
    )

If you do not intend to make any alterations to the default configuration for the given backend type, then you can follow a more streamlined approach:

    .. code-block:: python

        converter = ConverterPipe(data_interfaces=data_interfaces)

        # Fetch available metadata
        metadata = converter.get_metadata()

        # Create the in-memory NWBFile object and apply the default configuration for HDF5
        backend="hdf5"

        # Configure and write the NWB file
        nwbfile_path = "./my_nwbfile_name.nwb"
        converter.run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            backend=backend,
        )

and all datasets in the NWB file will automatically use the default configurations!


FAQ
---

**How do I see what compression methods are available on my system?**

You can see what compression methods are available on your installation by printing out the following variable:

    .. code-block:: python

      from neuroconv.tools.nwb_helpers import AVAILABLE_HDF5_COMPRESSION_METHODS

      AVAILABLE_HDF5_COMPRESSION_METHODS

    .. code-block:: bash

      {'gzip': 'gzip',
       ...
       'Zstd': hdf5plugin._filters.Zstd}

    And likewise for ``AVAILABLE_ZARR_COMPRESSION_METHODS``.


**Can I modify the maximum shape or data type through the NeuroConv backend configuration?**

Core fields such as the maximum shape and data type of the source data cannot be altered using the NeuroConv backend configuration.

Instead, they would have to be changed at the level of the read operation; these are sometimes exposed to the initialization inputs or source data options.


**Can I specify a buffer shape that incompletely spans the chunks?**

The ``buffer_shape`` must be a multiple of the ``chunk_shape`` along each axis.

This was found to give significant performance increases compared to previous data iterators that caused repeated I/O operations through partial chunk writes.


**How do I disable chunking and compression completely?**

To completely disable chunking for HDF5 backends (i.e., 'contiguous' layout), set both ``chunk_shape=None`` and ``compression_method=None``. Zarr requires all datasets to be chunked.

You could also delete the entry from the NeuroConv backend configuration, which would cause the neurodata object to fallback to whatever default method wrapped the dataset field when it was added to the in-memory ``pynwb.NWBFile``.


**How do I confirm that the backend configuration has been applied?**

The easiest way to check this information is to open the resulting file in ``h5py`` or ``zarr`` and print out the dataset properties.

For example, we can confirm that the dataset was written to disk according to our instructions by using ``h5py`` library to read the file we created in the previous section:

.. code-block:: python

    import h5py

    with h5py.File("my_nwbfile.nwb", "r") as file:
        chunks = file["acquisition/MyTimeSeries/data"].chunks
        compression = file["acquisition/MyTimeSeries/data"].compression
        compression_options = file["acquisition/MyTimeSeries/data"].compression_opts

        print(f"{chunks=}")
        print(f"{compression=}")
        print(f"{compression_options=}")

Which prints out:

.. code-block:: bash

    chunks=(1,)
    compression='zstd'
    compression_options=7

.. note::

    You may have noticed that the name of the key for that compression option got lost in translation; this is because
    HDF5 implicitly forces the order of each option in the tuple (or in this case, a scalar).
