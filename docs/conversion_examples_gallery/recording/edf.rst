European Data Format (EDF) conversion
-------------------------------------

Install NeuroConv with the additional dependencies necessary for reading EDF data.

.. code-block:: bash

    pip install "neuroconv[edf]"

Converting EDF Electrode Channels
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :py:class:`~neuroconv.datainterfaces.ecephys.edf.edfdatainterface.EDFRecordingInterface` is designed specifically for electrode recording channels that will be stored as an ElectricalSeries in the NWB file.
Other auxiliary signal channels should be excluded using the ``channels_to_skip`` parameter.

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from neuroconv.datainterfaces import EDFRecordingInterface

    file_path = f"{ECEPHY_DATA_PATH}/edf/electrode_and_analog_data/electrode_and_analog_data.edf"

    # Get all channel IDs to identify which ones to skip
    all_channels = EDFRecordingInterface.get_available_channel_ids(file_path)
    print(f"Available channels: {all_channels}")

    # Identify non-electrode channels that should be skipped
    # We don't have an automatic way to detect non-electrode channels, user passes this knowledge here
    channels_to_skip = ["TRIG", "OSAT", "PR", "Pleth"]  # Example: trigger and physiological monitoring

    # Create interface with channels to skip
    interface = EDFRecordingInterface(
        file_path=file_path,
        channels_to_skip=channels_to_skip
    )

    # Extract what metadata we can from the source files
    metadata = interface.get_metadata()
    # For data provenance we add the time zone information to the conversion
    session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    metadata["NWBFile"].update(session_start_time=session_start_time)
    # Add subject information (required for DANDI upload)
    metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    # Choose a path for saving the nwb file and run the conversion
    nwbfile_path = f"{path_to_save_nwbfile}"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

Handling Channels with Heterogeneous Offsets
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The NWB ``ElectricalSeries`` stores a single scalar ``offset`` that is shared by all of its channels.
Some EDF files contain electrode channels whose physical-to-digital offsets differ from one another,
which cannot be represented in a single ``ElectricalSeries``. In that case a normal ``run_conversion`` call
raises ``ValueError: Recording extractors with heterogeneous offsets are not supported.``

To convert such a file, use :py:meth:`~neuroconv.datainterfaces.ecephys.baserecordingextractorinterface.BaseRecordingExtractorInterface.run_conversion_split_by_offset`.
It partitions the channels by their offset value and writes one NWB file per distinct offset. The output
paths are derived from the given ``nwbfile_path`` by inserting an ``_offset{index}`` suffix
(e.g. ``recording.nwb`` becomes ``recording_offset0.nwb``, ``recording_offset1.nwb``, ...). When all channels
share the same offset, a single file is written to ``nwbfile_path`` unchanged.

.. code-block:: python

    from zoneinfo import ZoneInfo
    from neuroconv.datainterfaces import EDFRecordingInterface

    file_path = f"{ECEPHY_DATA_PATH}/edf/heterogeneous_offsets.edf"

    interface = EDFRecordingInterface(file_path=file_path)

    metadata = interface.get_metadata()
    session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    metadata["NWBFile"].update(session_start_time=session_start_time)
    metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    # Writes one NWB file per distinct channel offset and returns the written paths
    nwbfile_path = f"{path_to_save_nwbfile}"
    written_paths = interface.run_conversion_split_by_offset(
        nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True
    )
    print(f"Wrote: {written_paths}")

If you need finer control over the per-file naming or metadata, call
:py:meth:`~neuroconv.datainterfaces.ecephys.baserecordingextractorinterface.BaseRecordingExtractorInterface.split_by_offset`
directly to obtain one sub-interface per offset and run the conversion on each yourself:

.. code-block:: python

    sub_interfaces = interface.split_by_offset()
    for index, sub_interface in enumerate(sub_interfaces):
        sub_interface.run_conversion(
            nwbfile_path=f"recording_offset{index}.nwb", metadata=metadata, overwrite=True
        )

Converting Auxiliary EDF Channels as TimeSeries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Auxiliary signals such as physiological monitoring signals, triggers, or auxiliary data should be stored as generic TimeSeries objects
rather than ElectricalSeries. Use the dedicated :py:class:`~neuroconv.datainterfaces.ecephys.edf.edfanaloginterface.EDFAnalogInterface`
to handle these channels.

**Important**: TimeSeries objects in PyNWB require all channels to have the same physical unit.
If your auxiliary channels have different units (e.g., triggers with no unit, OSAT in %, PR in bpm),
you'll need to create separate EDFAnalogInterface instances for each unit type:

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from neuroconv.datainterfaces import EDFAnalogInterface

    file_path = f"{ECEPHY_DATA_PATH}/edf/electrode_and_analog_data/electrode_and_analog_data.edf"

    # Example: Trigger channels (no unit)
    trigger_channels = ["TRIG"]  # Trigger signals

    interface = EDFAnalogInterface(
        file_path=file_path,
        channels_to_include=trigger_channels
    )

    # Extract metadata and add timezone information
    metadata = interface.get_metadata()
    # For data provenance we add the time zone information to the conversion
    session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    metadata["NWBFile"].update(session_start_time=session_start_time)
    # Add subject information (required for DANDI upload)
    metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    # Choose a path for saving the nwb file and run the conversion
    nwbfile_path = f"{path_to_save_nwbfile}"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

Combining Electrode and Auxiliary Channels
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To convert both electrode and auxiliary channels into a single NWB file, use the ConverterPipe with multiple interfaces.
Remember to group auxiliary channels by their unit types:

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from neuroconv import ConverterPipe
    from neuroconv.datainterfaces import EDFRecordingInterface, EDFAnalogInterface
    from neuroconv.utils import dict_deep_update

    file_path = f"{ECEPHY_DATA_PATH}/edf/electrode_and_analog_data/electrode_and_analog_data.edf"

    # Define the channels to process
    all_non_electrical_channels = ["TRIG", "OSAT", "PR", "Pleth"]  # All auxiliary channels

    # Create electrode interface (skip all auxiliary channels)
    recording_interface = EDFRecordingInterface(
        file_path=file_path,
        channels_to_skip=all_auxiliary_channels,

    )

    # Create separate analog interfaces for each unit type
    trigger_channels_metadata_key = "time_series_trigger"  # No unit
    trigger_interface = EDFAnalogInterface(
        file_path=file_path,
        channels_to_include=["TRIG"],  # No unit
        metadata_key=trigger_channels_metadata_key
    )

    percent_channels_metadata_key = "time_series_oxygen"  # Percentage unit
    percent_interface = EDFAnalogInterface(
        file_path=file_path,
        channels_to_include=["OSAT"],  # Percentage units
        metadata_key=percent_channels_metadata_key,
    )

    # Combine all interfaces
    converter = ConverterPipe(
        data_interfaces=[recording_interface, trigger_interface, percent_interface],

    )

    # Extract metadata and add timezone information
    metadata = converter.get_metadata()
    # For data provenance we add the time zone information to the conversion
    session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    metadata["NWBFile"].update(session_start_time=session_start_time)
    # Add subject information (required for DANDI upload)
    metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    # REQUIRED: Customize TimeSeries names when using multiple analog interfaces
    user_edited_metadata = {
        "TimeSeries": {
            trigger_channels_metadata_key: {
                "name": "TimeSeriesTrigger",
                "description": "Trigger signals from EDF file"
            },
            percent_channels_metadata_key: {
                "name": "TimeSeriesOxygen",
                "description": "Oxygen saturation monitoring data"
            }
        }
    }

    # The metadata_key parameter ensures each interface creates entries with the correct names
    metadata = dict_deep_update(metadata, user_edited_metadata)

    # Convert all channel types to a single NWB file
    nwbfile_path = f"{path_to_save_nwbfile}"
    converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
