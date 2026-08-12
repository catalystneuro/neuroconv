pyPhotometry Fiber Photometry data conversion
---------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading pyPhotometry data.

.. code-block:: bash

    pip install "neuroconv[pyphotometry]"

pyPhotometry is an open acquisition system, also sold as hardware by Open Ephys, whose ``.ppd`` file
holds every signal the board recorded interleaved word by word. Which signals a file holds is decided by
its acquisition mode, and the same acquisition has been spelled three different ways as the format
evolved: ``GCaMP/RFP`` in the earliest headers, ``2 colour continuous`` in the middle era and
``2EX_2EM_continuous`` today. A file whose mode is not recognized is refused rather than read with a
default layout, because a mode that multiplexes more colors than the default assumes decodes into
interleaved traces that look like a signal.

``PyPhotometryFiberPhotometryInterface`` reads one signal into a single
``FiberPhotometryResponseSeries``, so instantiate one interface per signal, with distinct
``metadata_key`` values, and combine them in a converter. This is not a stylistic choice: the board has
no simultaneous analog-to-digital conversion, so no two signals in a ``.ppd`` were sampled at the same
instants and a response series carries one time axis.

``get_available_streams`` reports what to pass, callable before construction. Signals are named after
the analog input they came off, the way pyPhotometry's own reader names them.

Convert pyPhotometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert pyPhotometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.pyphotometry.pyphotometrydatainterface.PyPhotometryFiberPhotometryInterface`.

.. code-block:: python

    >>> from neuroconv.datainterfaces import PyPhotometryFiberPhotometryInterface

    >>> folder_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "pyphotometry" / "legacy_one_colour_time_division"
    >>> file_path = next(folder_path.glob("*.ppd"))

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

Each signal is written with the start time the acquisition gave it, which is what a shared timebase
would throw away. In the pulsed modes the sampling timer advances one analog input per tick, so the
second signal of a 130 Hz recording starts 1/260 of a second after the first:

.. code-block:: python

    >>> control = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_2", metadata_key="control", verbose=False)
    >>> float(round(control.get_timestamps()[0], 6))
    0.003846

The continuous modes are the exception. The board reads its inputs sequentially there too, but by an
amount the file does not record and no pyPhotometry document states, so those signals keep the timebase
the header states and say why in their description.

Recordings made with header version 1.1 or later store two measurements per sample in the pulsed modes,
the LED-on value and the LED-off baseline it is corrected against. The response series carries their
difference, which is what earlier firmware computed on the board, and the two measurements are written
beside it as plain ``TimeSeries``.

The full metadata format (device models, devices, indicators, the ``FiberPhotometryTable``, and the
per-interface response series) is shared across the fiber photometry interfaces and documented at
:ref:`fiber_photometry_metadata_structure`.
