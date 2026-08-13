pyPhotometry Fiber Photometry data conversion
---------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading pyPhotometry data.

.. code-block:: bash

    pip install "neuroconv[pyphotometry_fp]"

pyPhotometry is an open acquisition system, also sold as hardware by Open Ephys, which writes a binary
``.ppd`` file holding every signal the board recorded. How many signals that is depends on the
acquisition mode the recording was made in, and ``get_available_streams`` reports them before
construction, named after the analog input they came off.

``PyPhotometryFiberPhotometryInterface`` reads one signal into a single
``FiberPhotometryResponseSeries``.

Convert pyPhotometry Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert pyPhotometry Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.pyphotometry.pyphotometrydatainterface.PyPhotometryFiberPhotometryInterface`.

.. code-block:: python

    >>> from neuroconv.datainterfaces import PyPhotometryFiberPhotometryInterface

    >>> file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "pyphotometry" / "mode_named_in_prose" / "one_colour_time_division.ppd"

    >>> # Which signals a file holds depends on the acquisition mode it was recorded in.
    >>> PyPhotometryFiberPhotometryInterface.get_available_streams(file_path=file_path)
    ['analog_1', 'analog_2']

    >>> # One interface reads one signal.
    >>> interface = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_1", metadata_key="signal")
    >>> metadata = interface.get_metadata()
    >>> # The recording start time is in the file's header, so it does not have to be supplied.
    >>> metadata["NWBFile"]["session_start_time"]
    datetime.datetime(2021, 6, 8, 16, 52, 48)

    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

Each signal is written with the start time it was sampled at. In the strobed modes the analog inputs
are read one per tick of a timer running at the number of inputs times the header's rate, so the second
signal of a 130 Hz recording starts 1/260 of a second after the first:

.. code-block:: python

    >>> control = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_2", metadata_key="control")
    >>> float(round(control.get_timestamps()[0], 6))
    0.003846

The continuous modes are the exception: the offset is real there too but its size is not recorded
anywhere, so those signals keep the header's timebase and say so in their description.

Since a response series carries one time axis, and no two signals of a recording share one, each signal
is its own interface and its own series. To write all of them into one file, sharing a single
``FiberPhotometryTable``, pass one interface per signal to a
:py:class:`~neuroconv.nwbconverter.ConverterPipe`:

.. code-block:: python

    >>> from neuroconv import ConverterPipe
    >>> signal_metadata_key = "signal"
    >>> isosbestic_metadata_key = "isosbestic"
    >>> signal = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_1", metadata_key=signal_metadata_key)
    >>> isosbestic = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_2", metadata_key=isosbestic_metadata_key)

    >>> converter = ConverterPipe(data_interfaces=dict(signal=signal, isosbestic=isosbestic))
    >>> metadata = converter.get_metadata()

    >>> # Every interface names its series ``FiberPhotometryResponseSeries`` by default, so give each
    >>> # one a name of its own before writing them into the same file.
    >>> metadata["FiberPhotometry"][signal_metadata_key]["name"] = "FiberPhotometryResponseSeriesSignal"
    >>> metadata["FiberPhotometry"][isosbestic_metadata_key]["name"] = "FiberPhotometryResponseSeriesIsosbestic"

    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> converter.run_conversion(nwbfile_path=f"{path_to_save_nwbfile}", metadata=metadata, overwrite=True)

How to fill in the metadata a conversion needs, the device models, devices, indicators and the
``FiberPhotometryTable``, is shared across the fiber photometry interfaces and covered in
:ref:`annotate_fiber_photometry_metadata`.
