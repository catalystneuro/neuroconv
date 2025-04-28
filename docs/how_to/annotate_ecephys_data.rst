.. _annotate_ecephys_data:

How to Annotate Extracellular Electrophysiology Data
====================================================

This guide provides instructions on how to annotate extracellular electrophysiology data in NeuroConv.

How to Set ElectrodeGroup Metadata
----------------------------------

When working with extracellular electrophysiology data, you may need to define multiple electrode groups with different metadata (such as location) based on channel names. By default, NeuroConv creates a single ElectrodeGroup that is associated with all channels. This guide demonstrates how to define multiple distinct electrode groups before running the conversion.

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


In this example:

1. We first create a mock recording interface with 5 channels.
2. We retrieve the default metadata using ``get_metadata()``.
3. We define three electrode groups with different names, descriptions, and locations.
4. We replace the default ElectrodeGroup in the metadata with our list of electrode groups.
5. We map each channel ID to its corresponding electrode group name using the ``set_property()`` method.
6. Finally, we create the NWBFile with our updated metadata.

This approach allows you to associate different channels with different electrode groups, each with its own metadata such as location.
