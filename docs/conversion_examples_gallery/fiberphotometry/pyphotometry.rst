pyPhotometry Fiber Photometry data conversion
---------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading pyPhotometry data.

.. code-block:: bash

    pip install "neuroconv[pyphotometry]"

pyPhotometry is an open acquisition system, also sold as hardware by Open Ephys, which writes a binary
``.ppd`` file holding every signal the board recorded. How many signals that is depends on the
acquisition mode the recording was made in, and ``get_available_streams`` reports them before
construction, named after the analog input they came off.

``PyPhotometryFiberPhotometryInterface`` reads one signal into a single
``FiberPhotometryResponseSeries``, so instantiate one interface per signal, with distinct
``metadata_key`` values, and combine them in a converter. The signals cannot share a series because they
were not sampled at the same instants: the board reads its analog inputs one after another.

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
    >>> interface = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_1", metadata_key="signal", verbose=False)
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

    >>> control = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_2", metadata_key="control", verbose=False)
    >>> float(round(control.get_timestamps()[0], 6))
    0.003846

The continuous modes are the exception: the offset is real there too but its size is not recorded
anywhere, so those signals keep the header's timebase and say so in their description.

Recordings made with header version 1.1 or later store an LED-on value and the LED-off baseline it is
corrected against. The response series carries their difference, which is what earlier firmware computed
on the board, and both measurements are written beside it as response series of their own. The LED-on
trace references the same ``FiberPhotometryTable`` row as the difference; the baseline references none,
since a row states an excitation source and wavelength and neither applies to a measurement taken in the
dark. Such a recording also warns on read: no file of that version was available when this interface was
written, so that path is untested.

The full metadata format (device models, devices, indicators, the ``FiberPhotometryTable``, and the
per-interface response series) is shared across the fiber photometry interfaces and documented at
:ref:`fiber_photometry_metadata_structure`.
