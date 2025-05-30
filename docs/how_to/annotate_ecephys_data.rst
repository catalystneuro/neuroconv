.. _annotate_ecephys_data:

How to Annotate Extracellular Electrophysiology Data
====================================================

This guide provides instructions for annotating extracellular electrophysiology data using NeuroConv.

Most of the key metadata related to extracellular electrophysiology is stored in the electrodes table of the NWB file.
The electrode table contains a row per electrode where electrode specific metadata can be stored.
Two of the most important properties are the ``ElectrodeGroup`` assignments and the anatomical localization of the electrodes, both of which are required by the NWB format.

When annotating the electrodes table, be sure to follow the `best practices for the electrode table in NWB files <https://nwbinspector.readthedocs.io/en/dev/best_practices/ecephys.html#location>`_.


How to Set ElectrodeGroup Metadata
----------------------------------

When working with extracellular electrophysiology data, it can be helpful to segment electrodes into different groups for analysis (e.g., spike sorting).
Electrodes are typically grouped by physical proximity (e.g., tetrodes, probe shanks) or by probe.

By default, NeuroConv creates a single ElectrodeGroup that includes all channels.
This guide demonstrates how to define multiple distinct electrode groups and annotate them so that
NeuroConv correctly assigns them during data conversion.


.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface
    from neuroconv.tools import configure_and_write_nwbfile

    interface = MockRecordingInterface(num_channels=5, durations=[0.100])
    metadata = interface.get_metadata()

    # Define multiple electrode groups with different metadata
    electrode_group_A = {"name": "ElectrodeGroupA", "description": "A description", "location": "Location A"}
    electrode_group_B = {"name": "ElectrodeGroupB", "description": "B description", "location": "Location B"}
    electrode_group_C = {"name": "ElectrodeGroupC", "description": "C description", "location": "Location C"}

    # Replace the default ElectrodeGroup with a list of electrode groups
    electrode_groups = [electrode_group_A, electrode_group_B, electrode_group_C]
    metadata["Ecephys"]["ElectrodeGroup"] = electrode_groups

    # Map channel ids to group names, note that you can get the channel ids of the interface with:
    # interface.channel_ids
    recording = interface.recording_extractor
    channel_id_to_group_names = {
        "0": "ElectrodeGroupA",
        "1": "ElectrodeGroupA",
        "2": "ElectrodeGroupC",
        "3": "ElectrodeGroupB",
        "4": "ElectrodeGroupA",
    }
    recording.set_property(
        key="group",
        values=list(channel_id_to_group_names.values()),
        ids=list(channel_id_to_group_names.keys()),
    )

    # Create the NWBFile with the updated metadata
    nwbfile = interface.create_nwbfile(metadata=metadata)

    # You can check that your electrodes are correctly representing here
    nwbfile.electrode_groups

    # And that they are mapped correctly to the channels/electrodes
    nwbfile.electrodes.to_dataframe()

    nwbfile_path = "your_annotated_file.nwb"
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path)



This approach allows you to associate different channels with different electrode groups, each with its own metadata such as location.

How to Add Location to the Electrodes Table
-------------------------------------------

In addition to setting electrode group metadata, you may want to add specific location information for each individual electrode in the electrodes table.
This is particularly useful when electrodes are located in different brain areas or when you want to provide more detailed anatomical information.
Use standard atlas names for anatomical regions when possible.


.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface
    from neuroconv.tools import configure_and_write_nwbfile

    interface = MockRecordingInterface(num_channels=5, durations=[0.100])
    metadata = interface.get_metadata()

    # Get the recording extractor from the interface
    recording_extractor = interface.recording_extractor

    # Define brain areas for each channel using a dictionary
    # Each ID of the recording should be mapped to a specific brain area
    # Note that you can get the channel ids of the interface with: interface.channel_ids
    channel_id_to_brain_area = {
        "0": "CA1",
        "1": "CA1",
        "2": "CA3",
        "3": "DG",
        "4": "EC",
    }

    # Set the brain_area property on the recording extractor using the dictionary
    # It is very important the property is named brain area as that is what we use to map this to the electrodes table
    recording_extractor.set_property(
        key="brain_area",
        values=list(channel_id_to_brain_area.values()),
        ids=list(channel_id_to_brain_area.keys())
    )

    # Create the NWBFile with the updated metadata
    nwbfile = interface.create_nwbfile(metadata=metadata)

    # You can verify that the brain_area property was added to the electrodes table
    nwbfile.electrodes.to_dataframe()

    # Write the NWB file to disk
    nwbfile_path = "your_annotated_file.nwb"
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path)

This approach allows you to add specific location information for each electrode, which will be included in the NWB file's electrodes table.
Note that any other property of the electrodes can be added in a similar way such as impedance, filtering, stereotaxic coordinates, etc.

Current limitations
-------------------

Currently, the NWB format does not provide a standard way to distinguish between
channel properties (e.g., how data is recorded by the acquisition system) and
electrode properties (e.g., the characteristics of the physical electrodes).
There is ongoing work to address this here:

https://github.com/catalystneuro/ndx-extracellular-channels

We are also working on improving the specification of anatomical coordinates in:

https://github.com/catalystneuro/ndx-anatomical-localization

We welcome suggestions and use cases to help improve the format.
