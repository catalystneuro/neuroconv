Backend Configuration
=====================

NeuroConv offers highly convenient control over the type of file backend and the way its datasets are configured.

Find out more about possible backend formats in the `main NWB documentation <https://nwb-overview.readthedocs.io/en/latest/faq_details/why_hdf5.html#why-use-hdf5-as-the-primary-backend-for-nwb>`_.

Find out more about chunking and compression in the `advanced NWB tutorials for dataset I/O settings <https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/h5dataio.html#sphx-glr-tutorials-advanced-io-h5dataio-py>`_.

Find out more about memory buffering of large source files in the `advanced NWB tutorials for iterative data write <https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/plot_iterative_write.html#sphx-glr-tutorials-advanced-io-plot-iterative-write-py>`_.



Default configuration
---------------------

To retrieve a default configuration for an in-memory ``pynwb.NWBFile`` object, use the ``get_default_backend_configuration`` function...

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

    default_backend_configuration = get_default_backend_configuration(
        nwbfile=nwbfile, backend="hdf5"
    )

From which a printout of the contents looks like...

.. code-block:: python

    print(default_backend_configuration)

.. code-block:: bash

    Configurable datasets identified using the hdf5 backend
    -------------------------------------------------------

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

Let's demonstrate this by modifying everything we can for the ``data`` field of the ``TimeSeries`` object generated above...

.. code-block:: python

    dataset_configurations = default_backend_configuration.dataset_configurations
    dataset_configuration = dataset_configurations["acquisition/MyTimeSeries/data"]
    dataset_configuration.chunk_shape = (1,)
    dataset_configuration.buffer_shape = (2,)
    dataset_configuration.compression_method = "Zstd"
    dataset_configuration.compression_options = dict(clevel=3)

Some details to note about what can be changed...

.. note::

    Core fields such as the maximum shape and data type of the source data cannot be altered using this method.

.. note::

    The ``buffer_shape`` must be a multiple of the ``chunk_shape`` along each axis.

.. note::

    You can see what compression methods are available on your installation by examining the following...

    .. code-block:: python

      from neuroconv.tools.nwb_helpers import AVAILABLE_HDF5_COMPRESSION_METHODS

      AVAILABLE_HDF5_COMPRESSION_METHODS

    .. code-block:: bash

      {'gzip': 'gzip',
       ...
       'Zstd': hdf5plugin._filters.Zstd}

    And likewise for ``AVAILABLE_ZARR_COMPRESSION_METHODS``.

We can confirm these values are saved by re-printing that particular dataset configuration...

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


Interfaces and Converters
-------------------------

The normal workflow when writing an NWB file using a ``DataInterface`` or ``NWBConverter`` is simple to configure.

The following example uses the :ref:`example data <example_data>` available from the testing repo...

.. code-block:: python

    from datetime import datetime

    from dateutil import tz
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

    # Create the in-memory NWBFile object and retrieve a default configuration
    backend="hdf5"

    nwbfile = converter.create_nwbfile(metadata=metadata)
    backend_configuration = converter.get_default_backend_configuration(
        nwbfile=nwbfile,
        backend=backend,
    )

    # Make any modifications to the configuration in this step, for example...
    backend_configuration["acquisition/ElectricalSeriesAP/data"].compression_method = "Blosc"

    # Configure and write the NWB file
    nwbfile_path = "./my_nwbfile_name.nwb"
    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        nwbfile=nwbfile,
        backend=backend,
        backend_configuration=backend_configuration,
    )

.. note::

    If you do not intend to make any alterations to the default configuration for the given backend type, then you can follow the classic workflow...

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

    and all datasets in the NWB file will automatically use the default configuration!


Generic tools
-------------

If you are not using data interfaces or converters you can still use the general tools to configure the backend of any in-memory ``pynwb.NWBFile``....
created from data interfaces and converters, would have the following structure...

.. code-block:: python

    from uuid import uuid4
    from datetime import datetime

    from dateutil import tz
    from neuroconv.tools.nwb_helpers import make_or_load_nwbfile, get_default_backend_configuration, configure_backend
    from pynwb import TimeSeries

    nwbfile_path = "./my_nwbfile.nwb"

    session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    nwbfile = pynwb.NWBFile(
        session_start_time=session_start_time,
        session_description="My description...",
        identifier=str(uuid4()),
    )

    # Add neurodata objects to the NWBFile, for example...
    time_series = TimeSeries(
        name="MyTimeSeries",
        description="A time series from my experiment.",
        unit="cm/s",
        data=[1., 2., 3.],
        timestamps=[0.0, 0.2, 0.4],
    )
    nwbfile.add_acquisition(time_series)

    with make_or_load_nwbfile(
        nwbfile_path=nwbfile_path,
        nwbfile=nwbfile,
        overwrite=True,
        backend="hdf5",
        verbose=True,
    ):
        backend_configuration = get_default_backend_configuration(
            nwbfile=nwbfile, backend="hdf5"
        )

        # Make any modifications to the configuration in this step, for example...
        backend_configuration["acquisition/MyTimeSeries/data"].compression_options = dict(level=7)

        configure_backend(
            nwbfile=nwbfile, backend_configuration=backend_configuration
        )
