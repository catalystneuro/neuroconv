MedPC Events data conversion
----------------------------

MedPC output files contain information about operant behavior such as nose pokes and rewards. Reading them needs no
dependencies beyond the core ones.

.. code-block:: bash

    pip install "neuroconv[medpc_events]"

Convert the discrete events of a MedPC output file to NWB using
:py:class:`~neuroconv.datainterfaces.events.medpc_events.medpceventsdatainterface.MedPCEventsInterface`.
Each event type is written as a ``pynwb.event.EventsTable`` into ``nwbfile.events``.

Where an event type's identity lives is decided by the MSN program that wrote the file, so the interface takes
either of the two layouts. In the **per-array** layout each lettered array holds the onset times of one event type,
and ``medpc_name_to_info_dict`` says which arrays to read and what to call them.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import MedPCEventsInterface
    >>>
    >>> # For this data interface we need to pass the output file from MedPC
    >>> file_path = f"{BEHAVIOR_DATA_PATH}/medpc/example_medpc_file_06_06_2024.txt"
    >>> # Change the file_path to the appropriate location in your system
    >>> session_conditions = {"Start Date": "04/09/19", "Start Time": "10:34:30"}
    >>> start_variable = "Start Date"
    >>> medpc_name_to_info_dict = {
    ...     "A": {"name": "left_nose_poke_times"},
    ...     "B": {"name": "left_reward_times"},
    ...     "C": {"name": "right_nose_poke_times"},
    ...     "D": {"name": "right_reward_times"},
    ...     # An entry naming a durations_name is durative: G holds the port entry onsets and E their durations
    ...     "G": {"name": "port_entries", "durations_name": "E"},
    ... }
    >>> interface = MedPCEventsInterface(
    ...     file_path=file_path,
    ...     session_conditions=session_conditions,
    ...     start_variable=start_variable,
    ...     medpc_name_to_info_dict=medpc_name_to_info_dict,
    ... )
    >>>
    >>> # Extract what metadata we can from the source file
    >>> metadata = interface.get_metadata()
    >>> # We add the time zone information, which is required by NWB
    >>> session_start_time = datetime(2019, 4, 9, 10, 34, 30).replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # A MedPC file carries no prose, so describing each event type is up to you
    >>> event_types = metadata["Events"]["medpc"]["event_types"]
    >>> event_types["A"]["event_description"] = "Left nose poke times."
    >>> event_types["G"]["event_description"] = "Time spent in the reward port."
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

An array holding one value per event, such as the type of each trial, rides along as a column of that event type's
table through ``value_names``, and what its codes mean is stated in the metadata through ``column_categories``.

.. code-block:: python

    >>> from neuroconv.datainterfaces import MedPCEventsInterface
    >>>
    >>> file_path = f"{BEHAVIOR_DATA_PATH}/medpc/medpc_tye_lab/!2022-10-06_14h12m.Subject cohort10-M3.3"
    >>> interface = MedPCEventsInterface(
    ...     file_path=file_path,
    ...     session_conditions={"Start Date": "10/06/22", "Subject": "cohort10-M3.3"},
    ...     start_variable="Start Date",
    ...     # S holds the time of each conditioned stimulus and K holds which one it was
    ...     medpc_name_to_info_dict={"S": {"name": "cs_presentations", "value_names": {"K": "cs_type"}}},
    ... )
    >>>
    >>> metadata = interface.get_metadata()
    >>> metadata["NWBFile"].update(session_start_time=datetime(2022, 10, 6, 14, 12, 35).astimezone())
    >>> metadata["Events"]["medpc"]["event_types"]["S"]["columns"]["K"]["column_categories"] = {
    ...     "labels": {1: "water", 2: "ethanol", 3: "both"},
    ...     "meanings": {
    ...         1: "The water bottle was extended.",
    ...         2: "The ethanol bottle was extended.",
    ...         3: "Both bottles were extended.",
    ...     },
    ... }
    >>> metadata["Subject"] = dict(subject_id="cohort10-M3.3", species="Mus musculus", sex="M", age="P90D")
    >>>
    >>> nwbfile_path = output_folder / "medpc_value_column.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

In the **packed-code** layout a single array holds every event as a ``TIME.EVENTCODE`` value, whose integer part is
the time in clock ticks and whose fractional digits are the code of the event type. The file does not carry the rate
its clock was counted at, so ``clock_ticks_per_second`` has to be stated, and the codes cannot be read off the MSN
program either, so ``code_to_info_dict`` names the ones you know. A code that is not named is still read, and takes
its digits as its name.

.. code-block:: python

    >>> from neuroconv.datainterfaces import MedPCEventsInterface
    >>>
    >>> file_path = f"{BEHAVIOR_DATA_PATH}/medpc/event_type_in_column_laubach_lab/ExampleFile2"
    >>> interface = MedPCEventsInterface(
    ...     file_path=file_path,
    ...     session_conditions={"Start Date": "09/25/15", "Subject": "ML03"},
    ...     start_variable="Start Date",
    ...     packed_code_configuration={
    ...         "clock_ticks_per_second": 500,  # this program clocks at 2 ms
    ...         "code_to_info_dict": {
    ...             "001": {"name": "lick"},
    ...             "011": {"name": "pump_a_on"},
    ...             "021": {"name": "pump_a_off"},
    ...         },
    ...     },
    ... )
    >>>
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2015, 9, 25, 10, 38, 46).replace(tzinfo=ZoneInfo("US/Eastern"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> metadata["Subject"] = dict(subject_id="ML03", species="Rattus norvegicus", sex="M", age="P90D")
    >>>
    >>> nwbfile_path = output_folder / "medpc_packed_code.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

.. seealso::

    :doc:`../behavior/medpc` is the deprecated interface that writes the same events as ``ndx-events`` objects into
    the behavior processing module.
