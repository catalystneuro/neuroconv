MedPC Events data conversion
----------------------------

MedPC output files contain information about operant behavior such as nose pokes and rewards. Reading them needs no
dependencies beyond the core ones.

.. code-block:: bash

    pip install "neuroconv[medpc_events]"

Each event type is written as a ``pynwb.event.EventsTable`` into ``nwbfile.events``.

Which interface you want
~~~~~~~~~~~~~~~~~~~~~~~~

MedPC defines only how a number is *printed*; ``DISKVARS``, ``DISKFORMAT`` and ``DISKCOLUMNS`` say which
variables are saved, how wide they print and how many sit on a row, and nothing in the format says what any
number means. What an array holds is decided entirely by the MSN program the experimenter wrote, so **read the
program, not the data**, and open the file to see which of the two shapes it is in.

**One array per event type.** Each lettered array is a plain list of times, and the array is the event type:

.. code-block:: text

    A:
         0:      175.150      270.750      762.050      762.900     1042.600
    C:
         0:      330.050      362.500      947.200     1232.100     1233.400

Use :py:class:`~neuroconv.datainterfaces.events.medpc_events.medpceventsdatainterface.MedPCArrayEventsInterface`,
and tell it which arrays hold events, since nothing in the file says that ``A`` is nose pokes.

**The event type carried in the data.** One array holds the times of every event of the session, and which type
each one is comes from the data. Either the code is packed into the time value, classically as
``TIME.EVENTCODE``:

.. code-block:: text

    A:
         0:    10602.001    10602.011    10602.051    10852.021    10900.001

or it sits in a companion array of the same length:

.. code-block:: text

    B:
         0:        1.900        7.510        7.870       17.200
    C:
         0:        3.000        1.000        1.000        3.000

Use :py:class:`~neuroconv.datainterfaces.events.medpc_events.medpceventsdatainterface.MedPCCodedEventsInterface`
for both. It finds the event types itself, since the codes are in the data, and you supply only how to read them
and whatever names you know.

What a value is worth
~~~~~~~~~~~~~~~~~~~~~

Both interfaces take the same two arguments for this, because a MedPC value is a time only after the program's
choices are applied and the file records none of them.

``time_unit`` is what one stored value is worth: a named unit, ``"seconds"``, ``"centiseconds"``,
``"deciseconds"``, ``"milliseconds"`` or ``"decaseconds"``, or a number of seconds. A program that stored the raw
``BTIME`` counter takes the box's timing resolution as that number, ``0.002`` on a 2 ms system and ``0.005`` on a
5 ms one, which is set when MED-PC is installed and appears in no file.

``relative_mode`` says whether each value is the interval since the previous event rather than the elapsed time.
Med Associates' own shipped example procedures use this, which they call relative or incremental mode, so it is
worth checking before assuming absolute times.

Get any of these wrong and the file still decodes, which is why both interfaces check that the times they read do
not run backwards and raise naming the likely cause when they do.

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

One coded array
~~~~~~~~~~~~~~~

The file does not carry what one of its ticks is worth, so the resolution has to be stated as ``time_unit``, and the
codes cannot be read off the MSN program either, since the copy that ships beside the data is often a later version
whose numbering disagrees with the file. ``event_code_names`` is a legend rather than a declaration of what to
read: it names the codes you know, and one you leave out is still read and takes its digits as its name.

.. code-block:: python

    >>> from neuroconv.datainterfaces import MedPCCodedEventsInterface
    >>>
    >>> file_path = f"{BEHAVIOR_DATA_PATH}/medpc/event_type_in_column_laubach_lab/ExampleFile2"
    >>> interface = MedPCCodedEventsInterface(
    ...     file_path=file_path,
    ...     session_header={"Start Date": "09/25/15", "Subject": "ML03"},
    ...     timestamps_variable="A",  # the array this program packs its events into
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

.. seealso::

    :doc:`../behavior/medpc` is the deprecated interface that writes the same events as ``ndx-events`` objects into
    the behavior processing module.
