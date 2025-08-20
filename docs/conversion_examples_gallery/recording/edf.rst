European Data Format (EDF) conversion
-------------------------------------

Install NeuroConv with the additional dependencies necessary for reading EDF data.

.. code-block:: bash

    pip install "neuroconv[edf]"

Converting Electrode Channels
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :py:class:`~neuroconv.datainterfaces.ecephys.edf.edfdatainterface.EDFRecordingInterface` is designed specifically for electrode recording channels that will be stored as an ElectricalSeries in the NWB file. Non-electrical channels should be excluded using the ``channels_to_skip`` parameter.

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from neuroconv.datainterfaces import EDFRecordingInterface

    file_path = f"{ECEPHY_DATA_PATH}/edf/edf+C.edf"

    # Load the interface to inspect available channels
    interface = EDFRecordingInterface(file_path=file_path, verbose=False)

    # Get all channel IDs to identify which ones to skip
    all_channels = interface.channel_ids
    print(f"Available channels: {all_channels}")

    # Identify non-electrical channels that should be skipped
    # Users will recognize channels like TRIG, OSAT, PR, Pleth, etc.
    channels_to_skip = ["TRIG", "OSAT", "PR", "Pleth"]  # Example: trigger and physiological monitoring

    # Recreate interface with channels to skip
    interface = EDFRecordingInterface(
        file_path=file_path,
        channels_to_skip=channels_to_skip,
        verbose=False
    )

    # Extract what metadata we can from the source files
    metadata = interface.get_metadata()
    # For data provenance we add the time zone information to the conversion
    session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    metadata["NWBFile"].update(session_start_time=session_start_time)

    # Choose a path for saving the nwb file and run the conversion
    nwbfile_path = f"{path_to_save_nwbfile}"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

Converting Non-Electrical Channels as TimeSeries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Non-electrical channels (such as physiological monitoring signals, triggers, or auxiliary data) should be stored as generic TimeSeries objects rather than ElectricalSeries. Use the dedicated :py:class:`~neuroconv.datainterfaces.ecephys.edf.edfanaloginterface.EDFAnalogInterface` to handle these channels.

**Important**: TimeSeries objects in PyNWB require all channels to have the same physical unit. If your non-electrical channels have different units (e.g., triggers with no unit, OSAT in %, PR in bpm), you'll need to create separate EDFAnalogInterface instances for each unit type:

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from neuroconv.datainterfaces import EDFAnalogInterface

    file_path = f"{ECEPHY_DATA_PATH}/edf/edf+C.edf"

    # Example 1: Channels with percentage units
    percent_channels = ["OSAT"]  # Oxygen saturation in %

    interface_percent = EDFAnalogInterface(
        file_path=file_path,
        channels_to_include=percent_channels,
        verbose=False
    )

    # Example 2: Channels with beats per minute units
    bpm_channels = ["PR"]  # Pulse rate in bpm

    interface_bpm = EDFAnalogInterface(
        file_path=file_path,
        channels_to_include=bpm_channels,
        verbose=False
    )

    # Example 3: Trigger channels (no unit)
    trigger_channels = ["TRIG"]  # Trigger signals

    interface_trigger = EDFAnalogInterface(
        file_path=file_path,
        channels_to_include=trigger_channels,
        verbose=False
    )

    # Extract metadata and run conversions for each interface
    session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))

    for interface, suffix in [(interface_percent, "_percent"), (interface_bpm, "_bpm"), (interface_trigger, "_trigger")]:
        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=session_start_time)

        nwbfile_path = f"{path_to_save_nwbfile}{suffix}.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

Combining Electrode and Non-Electrical Channels
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To convert both electrode and non-electrical channels into a single NWB file, use the ConverterPipe with multiple interfaces. Remember to group non-electrical channels by their unit types:

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from neuroconv import ConverterPipe
    from neuroconv.datainterfaces import EDFRecordingInterface, EDFAnalogInterface

    file_path = f"{ECEPHY_DATA_PATH}/edf/edf+C.edf"

    # Define the channels to process
    all_non_electrical_channels = ["TRIG", "OSAT", "PR", "Pleth"]  # All non-electrical channels

    # Create electrode interface (skip all non-electrical channels)
    recording_interface = EDFRecordingInterface(
        file_path=file_path,
        channels_to_skip=all_non_electrical_channels,
        verbose=False
    )

    # Create separate analog interfaces for each unit type
    trigger_interface = EDFAnalogInterface(
        file_path=file_path,
        channels_to_include=["TRIG"],  # No unit
        verbose=False
    )

    percent_interface = EDFAnalogInterface(
        file_path=file_path,
        channels_to_include=["OSAT"],  # Percentage units
        verbose=False
    )

    bpm_interface = EDFAnalogInterface(
        file_path=file_path,
        channels_to_include=["PR"],  # Beats per minute units
        verbose=False
    )

    pleth_interface = EDFAnalogInterface(
        file_path=file_path,
        channels_to_include=["Pleth"],  # Plethysmography in uV
        verbose=False
    )

    # Combine all interfaces
    converter = ConverterPipe(
        data_interfaces=[recording_interface, trigger_interface, percent_interface, bpm_interface, pleth_interface],
        verbose=False
    )

    # Extract metadata and set session start time
    metadata = converter.get_metadata()
    session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    metadata["NWBFile"].update(session_start_time=session_start_time)

    # Convert all channel types to a single NWB file
    nwbfile_path = f"{path_to_save_nwbfile}"
    converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
