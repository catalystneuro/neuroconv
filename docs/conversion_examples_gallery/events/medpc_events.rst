MedPC Events data conversion
----------------------------

MedPC output files contain information about operant behavior such as nose pokes and rewards. Reading them needs no
dependencies beyond the core ones.

.. code-block:: bash

    pip install "neuroconv[medpc_events]"

Each event type is written as a ``pynwb.event.EventsTable`` into ``nwbfile.events``.

Which interface you want
~~~~~~~~~~~~~~~~~~~~~~~~

Where an event type's identity lives is decided by the MSN program that wrote the file, not by MedPC, so there are
two shapes a file can be in and one interface for each. Open your file and look at the arrays to tell which you
have.

**One array per event type.** Each lettered array is a plain list of times, and the array is the event type:

.. code-block:: text

    A:
         0:      175.150      270.750      762.050      762.900     1042.600
    C:
         0:      330.050      362.500      947.200     1232.100     1233.400

Use :py:class:`~neuroconv.datainterfaces.events.medpc_events.medpceventsdatainterface.MedPCArrayEventsInterface`,
and tell it which arrays hold events, since nothing in the file says that ``A`` is nose pokes.

**One coded array.** A single array holds every event as a ``TIME.EVENTCODE`` value, the integer part being the
time in clock ticks and the fractional digits the code of the event type:

.. code-block:: text

    A:
         0:    10602.001    10602.011    10602.051    10852.021    10900.001

Use :py:class:`~neuroconv.datainterfaces.events.medpc_events.medpceventsdatainterface.MedPCCodedEventsInterface`,
which finds the event types itself, since the codes are in the data. You supply the clock rate and whatever names
you know for the codes.

One array per event type
~~~~~~~~~~~~~~~~~~~~~~~~

``event_configuration`` says which arrays to read and what to call them.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import MedPCArrayEventsInterface
    >>>
    >>> # For this data interface we need to pass the output file from MedPC
    >>> file_path = f"{BEHAVIOR_DATA_PATH}/medpc/example_medpc_file_06_06_2024.txt"
    >>> # Change the file_path to the appropriate location in your system
    >>> session_header = {"Start Date": "04/09/19", "Start Time": "10:34:30"}
    >>> event_configuration = {
    ...     "A": {"name": "left_nose_poke_times"},
    ...     "B": {"name": "left_reward_times"},
    ...     "C": {"name": "right_nose_poke_times"},
    ...     "D": {"name": "right_reward_times"},
    ...     # An entry naming a duration is durative: G holds the port entry onsets and E their durations
    ...     "G": {"name": "port_entries", "duration": "E"},
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
    >>> # A MedPC file carries no prose, so describing each event type is up to you
    >>> event_types = metadata["Events"]["medpc"]["event_types"]
    >>> event_types["A"]["event_description"] = "Left nose poke times."
    >>> event_types["G"]["event_description"] = "Time spent in the reward port."
    >>> # The subject_id comes from the file; the rest is required for DANDI upload
    >>> metadata["Subject"].update(species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

An array holding one value per event, such as the type of each trial, rides along as a column of that event
type's table through ``payload``, and what its codes mean is stated in the metadata through ``column_categories``.

.. code-block:: python

    >>> from neuroconv.datainterfaces import MedPCArrayEventsInterface
    >>>
    >>> file_path = f"{BEHAVIOR_DATA_PATH}/medpc/medpc_tye_lab/!2022-10-06_14h12m.Subject cohort10-M3.3"
    >>> interface = MedPCArrayEventsInterface(
    ...     file_path=file_path,
    ...     session_header={"Start Date": "10/06/22", "Subject": "cohort10-M3.3"},
    ...     # S holds the time of each conditioned stimulus and K holds which one it was
    ...     event_configuration={"S": {"name": "cs_presentations", "payload": {"K": "cs_type"}}},
    ... )
    >>>
    >>> metadata = interface.get_metadata()
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

The file does not carry the rate its clock was counted at, so ``clock_ticks_per_second`` has to be stated, and the
codes cannot be read off the MSN program either, since the copy that ships beside the data is often a later version
whose numbering disagrees with the file. ``event_configuration`` names the codes you know; one you leave out is
still read and takes its digits as its name.

.. code-block:: python

    >>> from neuroconv.datainterfaces import MedPCCodedEventsInterface
    >>>
    >>> file_path = f"{BEHAVIOR_DATA_PATH}/medpc/event_type_in_column_laubach_lab/ExampleFile2"
    >>> interface = MedPCCodedEventsInterface(
    ...     file_path=file_path,
    ...     session_header={"Start Date": "09/25/15", "Subject": "ML03"},
    ...     variable_name="A",  # the array this program packs its events into
    ...     clock_ticks_per_second=500,  # this program clocks at 2 ms
    ...     event_configuration={
    ...         "001": {"name": "lick"},
    ...         "011": {"name": "pump_a_on"},
    ...         "021": {"name": "pump_a_off"},
    ...     },
    ... )
    >>>
    >>> metadata = interface.get_metadata()
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Eastern"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> metadata["Subject"].update(species="Rattus norvegicus", sex="M", age="P90D")
    >>>
    >>> nwbfile_path = output_folder / "medpc_coded.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

.. seealso::

    :doc:`../behavior/medpc` is the deprecated interface that writes the same events as ``ndx-events`` objects into
    the behavior processing module.
