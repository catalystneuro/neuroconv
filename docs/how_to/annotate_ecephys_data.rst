.. _annotate_ecephys_data:

How to Annotate Extracellular Electrophysiology Data
====================================================

This guide provides instructions on how to annotate extracellular electrophysiology data in NeuroConv.

How to Set ElectrodeGroup Metadata
----------------------------------

When working with extracellular electrophysiology data, you may need to define multiple electrode groups with different metadata (such as location) based on channel names.
By default, NeuroConv creates a single ElectrodeGroup that is associated with all channels.
This guide demonstrates how to define multiple distinct electrode groups and link them to the channels/electrodes.

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

    # Map channel ids to group names
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
    nwbfile = interface.add_to_nwbfile(metadata=metadata)

    # You can check that your electrodes are correctly representing here
    nwbfile.electrode_groups

    # And that they are mapped correctly to the channels/electrodes
    nwbfile.electrodes

    nwbfile_path = "your_annotated_file.nwb"
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path)



This approach allows you to associate different channels with different electrode groups, each with its own metadata such as location.

How to Add Location to the Electrodes Table
------------------------------------------

In addition to setting electrode group metadata, you may want to add specific location information for each individual electrode in the electrodes table. This is particularly useful when electrodes within the same group are in slightly different brain areas or when you want to provide more detailed anatomical information.

.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface
    from neuroconv.tools import configure_and_write_nwbfile

    interface = MockRecordingInterface(num_channels=5, durations=[0.100])
    metadata = interface.get_metadata()

    # Get the recording extractor from the interface
    recording_extractor = interface.recording_extractor

    # Define brain areas for each channel using a dictionary
    # Each ID of the recording should be mapped to a specific brain area
    channel_id_to_brain_area = {
        "0": "CA1",
        "1": "CA1",
        "2": "CA3",
        "3": "DG",
        "4": "EC",
    }

    # Set the brain_area property on the recording extractor using the dictionary
    recording_extractor.set_property(
        key="brain_area",
        values=list(channel_id_to_brain_area.values()),
        ids=list(channel_id_to_brain_area.keys())
    )

    # Create the NWBFile with the updated metadata
    nwbfile = interface.add_to_nwbfile(metadata=metadata)

    # You can verify that the brain_area property was added to the electrodes table
    nwbfile.electrodes

    # Write the NWB file to disk
    nwbfile_path = "your_annotated_file.nwb"
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path)

This approach allows you to add specific location information for each electrode, which will be included in the NWB file's electrodes table. The property name "brain_area" is used in this example, but you can use any property name that makes sense for your data.
