pyPhotometry Fiber Photometry data conversion
---------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading pyPhotometry data.

.. code-block:: bash

    pip install "neuroconv[pyphotometry]"

pyPhotometry is an open acquisition system, also sold as hardware by Open Ephys, which writes a binary
``.ppd`` file holding every signal the board recorded. How many signals that is depends on the
acquisition mode the recording was made in, and ``get_available_streams`` reports them before
construction, each named for the photodetector that was read and the excitation source that was lit.
Streams sharing a ``detector`` prefix came off one fiber.

The board reads its analog inputs one after the other rather than at the same instant, so each signal is
written with the start time its own slot in the sampling cycle implies. In the continuous modes that gap
is not recorded anywhere in the file, and the pyPhotometry developers measured it at about 393
microseconds on `their issue tracker <https://github.com/pyPhotometry/code/issues/39>`_. It is not
included in the timestamps, and each series states it in its ``comments``.

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
    ['detector_1_excitation_1', 'detector_2_excitation_2', 'digital_1', 'digital_2']

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
    ['detector_1_excitation_1', 'detector_1_excitation_2']

    >>> # One interface reads one signal.
    >>> interface = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="detector_1_excitation_1", metadata_key="signal")
    >>> metadata = interface.get_metadata()
    >>> # The recording start time is in the file's header, so it does not have to be supplied.
    >>> metadata["NWBFile"]["session_start_time"]
    datetime.datetime(2021, 6, 8, 16, 52, 48)

    >>> # The subject id comes from the header here too; the rest is required for DANDI upload.
    >>> metadata["Subject"].update(species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

In the strobed modes the analog inputs are read one per tick of a timer running at the number of inputs
times the header's rate, so the second signal of a 130 Hz recording starts 1/260 of a second after the
first:

.. code-block:: python

    >>> control = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="detector_1_excitation_2", metadata_key="control")
    >>> float(round(control.get_timestamps()[0], 6))
    0.003846

NeuroConv usually gathers a system's regions into the columns of one series, and that is not possible
here: the board reads one input at a time, so two fibers on the two analog inputs were never sampled
together and a ``FiberPhotometryResponseSeries`` carries one time axis. Each signal is written as its
own series instead, referencing its own row of the same ``FiberPhotometryTable``.

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as the anatomical location,
the meaning of the values, or a semantically meaningful description of the data. Follow
:ref:`the fiber photometry how-to <annotate_fiber_photometry_metadata>` for a modality-relevant guide to adding
this extra metadata, which makes the data more useful for future users and for the community as a whole.
Its :ref:`section on templates <how_to_annotate_from_a_template>` starts from scratch, and the
:ref:`reference template <fiber_photometry_metadata_template>` lists every element the metadata accepts.

.. seealso::

    - :doc:`../events/pyphotometry_events` to convert the digital lines carried in the same words.
