MedPC Events data conversion
----------------------------

MedPC output files contain information about operant behavior such as nose pokes and rewards. MedPC events need
only NeuroConv's core dependencies, but the ``medpc`` extra is available for a consistent install command.

.. code-block:: bash

    pip install "neuroconv[medpc]"

Each event type is written as a ``pynwb.event.EventsTable`` into ``nwbfile.events``.

MedPC stores its variables under single letters, and the MSN program decides what each one holds, so open the
file to see which of the two layouts below you have.

Each event type in its own variable
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The program gave each kind of event its own variable, so ``A`` holds the times of one event type and ``C`` the
times of another. Nothing is packed into the values.

.. code-block:: text

    A:
         0:      175.150      270.750      762.050      762.900     1042.600
    C:
         0:      330.050      362.500      947.200     1232.100     1233.400

Use :py:class:`~neuroconv.datainterfaces.events.medpc_events.medpceventsdatainterface.MedPCArrayEventsInterface`.
Nothing in the file marks a variable as events, so ``event_configuration`` lists the ones that hold them and
says how to read each.

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
    ...     # This program stored elapsed times in seconds, the default. Pass time_unit where yours used
    ...     # another unit, and relative_mode=True where it stored the gap since the previous event.
    ...     # The file records neither.
    ... )
    >>>
    >>> # Extract what metadata we can from the source file, which includes the session start time and the
    >>> # subject read from the header
    >>> metadata = interface.get_metadata()
    >>> # The file states no time zone, so we add it
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Event types arrive named after the variable that holds them, and the file carries no descriptions,
    >>> # so naming and describing them is the first thing you do
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

A variable holding one value per event, such as the type of each trial, is carried along as a column of that
event type's table through ``payload``. The column arrives named after its variable; rename it and label its
codes in the metadata.

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

Every event in one variable
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The program put every event into a single variable, with the time before the decimal point and a code for the
event type after it.

.. code-block:: text

    A:
         0:    10602.001    10602.011    10602.051    10852.021    10900.001

Use :py:class:`~neuroconv.datainterfaces.events.medpc_events.medpceventsdatainterface.MedPCPackedEventsInterface`.
``time_unit`` states what one stored value is worth, since the file does not record it, and every code in the
variable becomes an event type named after its digits, so a code you do not name is still read.

.. code-block:: python

    >>> from neuroconv.datainterfaces import MedPCPackedEventsInterface
    >>>
    >>> file_path = f"{BEHAVIOR_DATA_PATH}/medpc/event_type_in_column_laubach_lab/ExampleFile2"
    >>> interface = MedPCPackedEventsInterface(
    ...     file_path=file_path,
    ...     session_header={"Start Date": "09/25/15", "Subject": "ML03"},
    ...     events_variable="A",  # the array this program packs its events into
    ...     time_unit=0.002,  # a 2 ms system, so each stored tick is worth 0.002 s
    ...     # A wrong unit still decodes, so the times read are checked against the session length the
    ...     # header states and for running backwards
    ... )
    >>>
    >>> # Every code becomes an event type named after its digits, so naming them comes first
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

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as which behavior a variable
recorded, what an event code meant, or a semantically meaningful description of an event type. Follow
:ref:`the events how-to <annotate_events_metadata>` for a modality-relevant guide to adding this extra
metadata, which makes the data more useful for future users and for the community as a whole. Its
:ref:`section on a single interface <annotate_events_single_interface>` starts from scratch, and its
:ref:`section on shared tables <annotate_events_shared_table>` covers writing several interfaces into one
table.

Not supported yet
~~~~~~~~~~~~~~~~~

The MSN program decides how an event's type is stored, and it can do it in ways NeuroConv does not read yet. If
your file matches neither layout above, please
`open an issue <https://github.com/catalystneuro/neuroconv/issues>`_ with the MSN program and a sample file.
