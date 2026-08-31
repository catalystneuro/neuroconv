MedPC Events data conversion
----------------------------

MedPC output files contain information about operant behavior such as nose pokes and rewards. Reading them needs no
dependencies beyond the core ones.

.. code-block:: bash

    pip install "neuroconv[medpc_events]"

Each event type is written as a ``pynwb.event.EventsTable`` into ``nwbfile.events``.

Which interface you want
~~~~~~~~~~~~~~~~~~~~~~~~

NeuroConv currently reads two kinds of MedPC output, and which one you have was decided by the MSN program the
experimenter wrote, so open the file and look.

**One array per event type.** Each lettered array is a plain list of times, and the array is the event type:

.. code-block:: text

    A:
         0:      175.150      270.750      762.050      762.900     1042.600
    C:
         0:      330.050      362.500      947.200     1232.100     1233.400

Use :py:class:`~neuroconv.datainterfaces.events.medpc_events.medpceventsdatainterface.MedPCArrayEventsInterface`,
and tell it which arrays hold events, since nothing in the file says that ``A`` is nose pokes.

**The event type packed into the value.** One array holds every event of the session, and which type each one
is comes from the value itself, classically as ``TIME.EVENTCODE``, the code in the decimals and the time in the
integer part:

.. code-block:: text

    A:
         0:    10602.001    10602.011    10602.051    10852.021    10900.001

Use :py:class:`~neuroconv.datainterfaces.events.medpc_events.medpceventsdatainterface.MedPCPackedEventsInterface`.
It finds the event types itself, since the codes are in the data, and you supply only how to read them and
whatever names you know. Codes of different widths can sit in one array, since the file prints them all to the
same number of decimals.

What a value is worth
~~~~~~~~~~~~~~~~~~~~~

A MedPC value is a time only once the program's choices are applied, and the file records none of them, so both
interfaces take ``time_unit``, what one stored value is worth as a named unit or a number of seconds, and
``relative_mode``, for a program that stored the interval since the previous event rather than the elapsed time.

Get either wrong and the file still decodes, which is why both interfaces check the times they read for running
backwards and against the session length the header states, and name the likely cause when they raise.

One array per event type
~~~~~~~~~~~~~~~~~~~~~~~~

``event_configuration`` says which arrays to read, and how, since nothing in the file marks an array as events.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import MedPCArrayEventsInterface
    >>>
    >>> # For this data interface we need to pass the output file from MedPC
    >>> file_path = f"{BEHAVIOR_DATA_PATH}/medpc/example_medpc_file_06_06_2024.txt"
    >>> # Change the file_path to the appropriate location in your system
    >>> session_header = {"Start Date": "04/09/19", "Start Time": "10:34:30"}
    >>> event_configuration = {
    ...     "A": None,
    ...     "B": None,
    ...     "C": None,
    ...     "D": None,
    ...     # An entry naming a duration is durative: G holds the port entry onsets and E their durations
    ...     "G": {"duration": "E"},
    ... }
    >>> interface = MedPCArrayEventsInterface(
    ...     file_path=file_path,
    ...     session_header=session_header,
    ...     event_configuration=event_configuration,
    ... )
    >>>
    >>> # Extract what metadata we can from the source file, which includes the session's start time and its
    >>> # subject, read from the header of the session picked out by session_header
    >>> metadata = interface.get_metadata()
    >>> metadata["NWBFile"]["session_start_time"]
    datetime.datetime(2019, 4, 9, 10, 34, 30)
    >>> # The file states no time zone, so we add it
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # A MedPC variable is a slot rather than a label, so every event type arrives named after its
    >>> # variable and naming them is the first thing you do. The file carries no prose either, so the
    >>> # descriptions are yours to write.
    >>> event_types = metadata["Events"]["medpc"]["event_types"]
    >>> event_types["A"]["event_name"] = "left_nose_poke"
    >>> event_types["G"]["event_name"] = "port_entries"
    >>> event_types["A"]["event_description"] = "Left nose poke times."
    >>> event_types["G"]["event_description"] = "Time spent in the reward port."
    >>> # The subject_id comes from the file; the rest is required for DANDI upload
    >>> metadata["Subject"].update(species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

An array holding one value per event, such as the type of each trial, rides along as a column of that event
type's table through ``payload``. The column arrives named after its variable, and both what to call it and what
its codes mean are stated in the metadata.

.. code-block:: python

    >>> from neuroconv.datainterfaces import MedPCArrayEventsInterface
    >>>
    >>> file_path = f"{BEHAVIOR_DATA_PATH}/medpc/medpc_tye_lab/!2022-10-06_14h12m.Subject cohort10-M3.3"
    >>> interface = MedPCArrayEventsInterface(
    ...     file_path=file_path,
    ...     session_header={"Start Date": "10/06/22", "Subject": "cohort10-M3.3"},
    ...     # S holds the time of each conditioned stimulus and K holds which one it was
    ...     event_configuration={"S": {"payload": ["K"]}},
    ... )
    >>>
    >>> metadata = interface.get_metadata()
    >>> metadata["Events"]["medpc"]["event_types"]["S"]["event_name"] = "cs_presentation"
    >>> metadata["Events"]["medpc"]["event_types"]["S"]["columns"]["K"]["column_name"] = "cs_type"
    >>> metadata["Events"]["medpc"]["event_types"]["S"]["columns"]["K"]["column_categories"] = {
    ...     "labels": {1: "water", 2: "ethanol", 3: "both"},
    ...     "meanings": {
    ...         1: "The water bottle was extended.",
    ...         2: "The ethanol bottle was extended.",
    ...         3: "Both bottles were extended.",
    ...     },
    ... }
    >>> metadata["Subject"].update(species="Mus musculus", sex="M", age="P90D")
    >>>
    >>> nwbfile_path = output_folder / "medpc_value_column.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

One packed array
~~~~~~~~~~~~~~~~

The file does not carry what one of its ticks is worth, so the resolution has to be stated as ``time_unit``, and the
codes cannot be read off the MSN program either, since the copy that ships beside the data is often a later version
whose numbering disagrees with the file. Every code the array holds becomes an event type whether or not you name
it, so a code you say nothing about is still read and takes its digits as its name.

.. code-block:: python

    >>> from neuroconv.datainterfaces import MedPCPackedEventsInterface
    >>>
    >>> file_path = f"{BEHAVIOR_DATA_PATH}/medpc/event_type_in_column_laubach_lab/ExampleFile2"
    >>> interface = MedPCPackedEventsInterface(
    ...     file_path=file_path,
    ...     session_header={"Start Date": "09/25/15", "Subject": "ML03"},
    ...     events_variable="A",  # the array this program packs its events into
    ...     time_unit=0.002,  # a 2 ms system, so each stored tick is worth 0.002 s
    ... )
    >>>
    >>> # Every code the array holds becomes an event type named after its digits, so naming them is the
    >>> # first thing you do in the metadata
    >>> metadata = interface.get_metadata()
    >>> event_types = metadata["Events"]["medpc"]["event_types"]
    >>> event_types["001"]["event_name"] = "lick"
    >>> event_types["011"]["event_name"] = "pump_a_on"
    >>> event_types["021"]["event_name"] = "pump_a_off"
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Eastern"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> metadata["Subject"].update(species="Rattus norvegicus", sex="M", age="P90D")
    >>>
    >>> nwbfile_path = output_folder / "medpc_coded.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

Not supported yet
~~~~~~~~~~~~~~~~~

Two ways of carrying an event's type are not read yet, and both would be straightforward to add given files
written by them. If you have such files, please
`open an issue <https://github.com/catalystneuro/neuroconv/issues>`_ with the MSN program and a sample file.

**A companion array of codes.** One array holds the times and a second of the same length holds one code per
event, paired by index (``DIM B \All event times`` beside ``DIM C \All event identities``):

.. code-block:: text

    B:
         0:        1.900        7.510        7.870       17.200
    C:
         0:        3.000        1.000        1.000        3.000

This is the tidiest way to write the program and we expect it to be common, but the only published corpus we
found writing it stores two of its event types on time bases a factor of ten apart inside the one array, which
no single unit reads correctly. Rather than generalise from that one deposit, we are waiting for a file written
on a single clock.

**A code in the leading digits.** Some programs pack the code above the time instead of below it, by adding a
large constant (``^PeckLeft = 10000`` with ``set x(y) = ^PeckLeft + Btime/1"``), so a left peck at 64.54 s is
stored as ``10064.540``. A survey of about 7,000 published files found the page describing this convention but
not one file written by it.

.. seealso::

    :doc:`../behavior/medpc` is the deprecated interface that writes the same events as ``ndx-events`` objects into
    the behavior processing module.
