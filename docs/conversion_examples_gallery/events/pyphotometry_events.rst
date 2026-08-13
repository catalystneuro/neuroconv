pyPhotometry Events data conversion
-----------------------------------

Install NeuroConv with the additional dependencies necessary for reading pyPhotometry data.

.. code-block:: bash

    pip install "neuroconv[pyphotometry_events]"

A pyPhotometry ``.ppd`` file has no digital stream of its own. Every word it holds carries fifteen bits of
an analog sample and one bit of a digital line, and the words cycle through the board's analog inputs, so
a digital line rides in the low bit of the words of the input it shares a slot with and is sampled on that
input's clock. Reading the lines therefore means reading the same file the fluorescence comes from, and
each line arrives as a sampled ``0``/``1`` signal rather than as a list of onsets.

Convert pyPhotometry Events data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use :py:class:`~neuroconv.datainterfaces.events.pyphotometry_events.pyphotometryeventsdatainterface.PyPhotometryEventsInterface`.
Each line is edge-detected and written as one ``pynwb.event.EventsTable`` into ``nwbfile.events``; by
default it is read as a ``high_period`` (onset at the rising edge, duration to the falling edge). Lines are
named the way pyPhotometry's own reader names them, and ``session_start_time`` comes from the header.

.. code-block:: python

    >>> from neuroconv.datainterfaces import PyPhotometryEventsInterface

    >>> file_path = OPHYS_DATA_PATH / "events_datasets" / "pyphotometry" / "narrow_pulses_and_idle_line" / "one_colour_time_division_window.ppd"

    >>> interface = PyPhotometryEventsInterface(file_path=file_path, verbose=False)

    >>> # Every digital line the file carries becomes an event type, named after its digital input.
    >>> metadata = interface.get_metadata()
    >>> list(metadata["Events"]["pyphotometry_events"]["event_types"])
    ['digital_1', 'digital_2']

    >>> # The recording start time is in the file's header, so it does not have to be supplied.
    >>> metadata["NWBFile"]["session_start_time"]
    datetime.datetime(2021, 6, 8, 16, 52, 48)

    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)

A line that never toggles is written as a zero-row table rather than dropped, since the type existed in
the recording and nothing fired. To read only some of the lines, or to read one of them differently, name
them in ``detection_configuration``:

.. code-block:: python

    >>> interface = PyPhotometryEventsInterface(
    ...     file_path=file_path,
    ...     detection_configuration={
    ...         "digital_1": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}]
    ...     },
    ... )
    >>> list(interface.get_metadata()["Events"]["pyphotometry_events"]["event_types"])
    ['digital_1']

.. seealso::

    - :doc:`../fiberphotometry/pyphotometry` to convert the fluorescence carried in the same words.
