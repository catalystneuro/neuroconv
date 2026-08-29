pyPhotometry Events data conversion
-----------------------------------

Install NeuroConv with the additional dependencies necessary for reading pyPhotometry data.

.. code-block:: bash

    pip install "neuroconv[pyphotometry_events]"

A pyPhotometry ``.ppd`` file carries its digital lines inside the same words as the fluorescence, so this
interface reads the same file as ``PyPhotometryFiberPhotometryInterface``. Each line is sampled at the
rate of the analog input it travels with instead of being logged as a list of onsets, so an edge is
located only to within one sample of that input's clock.

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
the recording and nothing fired. To read only some of the lines, or to read one of them differently, pass
a ``detection_configuration``, which :ref:`extract_events_from_signals` documents.

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as what a line was wired to,
what a pulse on it meant, or a semantically meaningful description of an event type. Follow
:ref:`the events how-to <annotate_events_metadata>` for a modality-relevant guide to adding this extra
metadata, which makes the data more useful for future users and for the community as a whole. Its
:ref:`section on a single interface <annotate_events_single_interface>` starts from scratch, and its
:ref:`section on shared tables <annotate_events_shared_table>` covers writing several interfaces into one
table.

.. seealso::

    - :doc:`../fiberphotometry/pyphotometry_fp` to convert the fluorescence carried in the same words.
