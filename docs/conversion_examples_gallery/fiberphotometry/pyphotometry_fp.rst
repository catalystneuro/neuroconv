pyPhotometry Fiber Photometry data conversion
---------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading pyPhotometry data.

.. code-block:: bash

    pip install "neuroconv[pyphotometry_fp]"

pyPhotometry is an open acquisition system, also sold as hardware by Open Ephys, which writes a binary
``.ppd`` file holding every signal the board recorded. How many signals that is depends on the
acquisition mode the recording was made in, and ``get_available_streams`` reports them before
construction, named after the analog input they came off.

``PyPhotometryConverter`` writes a recording whole, every fluorescence signal and every digital line, in
one call. ``PyPhotometryFiberPhotometryInterface`` reads one signal on its own, and the
:doc:`pyPhotometry events interface <../events/pyphotometry_events>` reads the digital lines on their
own, for when one of those is all you want.

Convert pyPhotometry Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert pyPhotometry Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.pyphotometry.pyphotometryconverter.PyPhotometryConverter`,
which reads the acquisition mode and builds one interface per fluorescence signal, plus one for the
digital lines that ride in the same words.

.. code-block:: python

    >>> from neuroconv.converters import PyPhotometryConverter

    >>> recording_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "pyphotometry" / "mode_named_in_prose" / "two_colour_time_division.ppd"

    >>> # The fluorescence signals first, then the digital lines that ride beside them.
    >>> PyPhotometryConverter.get_available_streams(file_path=recording_path)
    ['analog_1', 'analog_2', 'digital_1', 'digital_2']

    >>> converter = PyPhotometryConverter(file_path=recording_path)
    >>> metadata = converter.get_metadata()

    >>> # The header names the animal, so the subject id is already filled in.
    >>> metadata["Subject"]["subject_id"]
    'm28_DMS_L'

    >>> # The rest of the subject information is nowhere in the file, and DANDI requires it.
    >>> metadata["Subject"].update(species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> converter.run_conversion(nwbfile_path=f"{path_to_save_nwbfile}", metadata=metadata, overwrite=True)

Every signal shares one ``FiberPhotometryTable``, and each digital line is written as its own
``EventsTable``, read as a ``high_period`` unless told otherwise. Passing ``detection_configuration``
hands it to the events interface, which documents it and which the
:doc:`pyPhotometry events page <../events/pyphotometry_events>` covers; naming only some of the lines
there is also how the rest are left out.

Convert a single signal
~~~~~~~~~~~~~~~~~~~~~~~

To write one signal and nothing else, use
:py:class:`~neuroconv.datainterfaces.fiber_photometry.pyphotometry.pyphotometrydatainterface.PyPhotometryFiberPhotometryInterface`,
which reads the signal named by ``stream_name``.

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

    >>> # The subject id comes from the header here too; the rest is required for DANDI upload.
    >>> metadata["Subject"].update(species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

Each signal is written with the start time it was sampled at. In the strobed modes the analog inputs are
read one per tick of a timer running at the number of inputs times the header's rate, so the second
signal of a 130 Hz recording starts 1/260 of a second after the first:

.. code-block:: python

    >>> control = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_2", metadata_key="control")
    >>> float(round(control.get_timestamps()[0], 6))
    0.003846

The continuous modes are the exception: the offset is real there too but its size is not recorded
anywhere, so those signals keep the header's timebase and say so in their description.

NeuroConv usually gathers a system's regions into the columns of one series, and that is not possible
here: the board reads one input at a time, so two fibers on the two analog inputs were never sampled
together and a ``FiberPhotometryResponseSeries`` carries one time axis. Each signal is written as its
own series instead, referencing its own row of the same ``FiberPhotometryTable``.

How to fill in the metadata a conversion needs, the device models, devices, indicators and the
``FiberPhotometryTable``, is shared across the fiber photometry interfaces and covered in
:ref:`annotate_fiber_photometry_metadata`. For the structure to fill in rather than the reasoning behind
it, :ref:`metadata_templates` shows what ``get_metadata_template()`` returns and carries the same thing
as a YAML or JSON file to edit by hand.
