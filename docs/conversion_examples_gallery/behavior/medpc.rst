MedPC data conversion
---------------------

MedPC output files contain information about operant behavior such as nose pokes and rewards.
Install NeuroConv with the additional dependencies necessary for writing medpc behavioral data.

.. code-block:: bash

    pip install neuroconv[medpc]

Convert MedPC output data to NWB using
:py:class:`~.neuroconv.datainterfaces.behavior.medpc.medpcdatainterface.MedPCInterface`.

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from neuroconv.datainterfaces import MedPCInterface

    # For this data interface we need to pass the output file from MedPC
    file_path = f"{BEHAVIOR_DATA_PATH}/medpc/example_medpc_file_06_06_2024.txt"
    # Change the folder_path to the appropriate location in your system
    session_conditions = {"Start Date": "04/18/19", "Start Time": "10:41:42"}
    start_variable = "Start Date",
    metadata_medpc_name_to_info_dict = dict(
        "Start Date": {"name": "start_date", "is_array": False},
        "Start Time": {"name": "start_time", "is_array": False},
        "Subject": {"name": "subject", "is_array": False},
        "Box": {"name": "box", "is_array": False},
        "MSN": {"name": "MSN", "is_array": False},
    )
    interface = MedPCInterface(
        file_path=file_path,
        session_conditions=session_conditions,
        start_variable=start_variable,
        metadata_medpc_name_to_info_dict=metadata_medpc_name_to_info_dict
    )

    # Extract what metadata we can from the source file
    metadata = interface.get_metadata()
    # We add the time zone information, which is required by NWB
    session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    metadata["NWBFile"].update(session_start_time=session_start_time)
    metadata["MedPC"]["medpc_name_to_info_dict"] = {
            "A": {"name": "left_nose_poke_times", "is_array": True},
            "B": {"name": "left_reward_times", "is_array": True},
            "C": {"name": "right_nose_poke_times", "is_array": True},
            "D": {"name": "right_reward_times", "is_array": True},
            "E": {"name": "duration_of_port_entry", "is_array": True},
            "G": {"name": "port_entry_times", "is_array": True},
            "H": {"name": "footshock_times", "is_array": True},
    }
    metadata["MedPC"]["Events"] = [
        {
            "name": "left_nose_poke_times",
            "description": "Left nose poke times.",
        },
        {
            "name": "left_reward_times",
            "description": "Left reward times.",
        },
        {
            "name": "right_nose_poke_times",
            "description": "Right nose poke times.",
        },
        {
            "name": "right_reward_times",
            "description": "Right reward times.",
        },
        {
            "name": "footshock_times",
            "description": "Footshock times.",
        },
    ]
    metadata["MedPC"]["IntervalSeries"] = [
        {
            "name": "reward_port_intervals",
            "description": "Interval of time spent in reward port (1 is entry, -1 is exit).",
            "onset_name": "port_entry_times",
            "duration_name": "duration_of_port_entry",
        },
    ]

    # Choose a path for saving the nwb file and run the conversion
    nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
