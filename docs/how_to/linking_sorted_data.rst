.. _linking_sorted_data:

How to Link Sorted Data to Electrodes
=====================================

When converting spike sorting results to NWB format, it is essential to preserve the
relationship between sorted units and the recording electrodes that detected them.
This linkage ensures that each unit inherits all electrode-level metadata stored in the
`electrodes` table of the NWB file.

For this linkage to be useful, the `electrodes` table itself must be **well annotated**,
including accurate information on brain area, anatomical coordinates, electrode geometry,
and any probe-specific metadata. Without this detail, the benefits of unit-electrode
linking are severely limited. For guidance on electrode table annotation, see
:doc:`annotate_ecephys_data`.

Why Link Units to Electrodes?
-----------------------------

Proper electrode linking allows each unit to be formally connected to all the metadata
describing its recording site. This enables both spatial and anatomical localization
of units which is critical for accurate interpretation and reproducibility:

**Spatial Analysis**
    With well-annotated electrode positions (e.g., rel_x, rel_y, rel_z),
    future users of the NWBFile can determine where units lie within the probe, perform laminar
    analyses, assess depth-dependent firing properties, and investigate spatial
    organization such as receptive field gradients or clustering patterns across channels.

**Anatomical Analysis**
    Registering the probe's position in the brain allows anatomical features such as
    brain area, subregion, or cortical layer to be associated with electrodes and,
    by extension, with linked units.
    As an example, `Liu et al. (2022) <https://doi.org/10.1038/s41467-022-33536-x>`_ demonstrated how depth-resolved recordings across
    hippocampal layers reveal distinct current source density and local field potential
    signatures of sharp wave-ripples. This type of interpretation is only possible when
    recording channel locations are known and correctly linked to sorted units.

**Quality Control and Traceability**
    Linking units to electrode metadata ensures full traceability from spike sorting
    results back to the raw recording channels. This allows you to inspect waveforms,
    review spike detection events, and confirm that units are spatially plausible
    (e.g., waveforms localized to nearby electrodes). Such verification helps detect
    sorting errors, identify artifacts, and maintain reproducibility by making the
    sorting process transparent and auditable.


Accessing Electrode Metadata from Units
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once units are properly linked to electrodes and the electrodes table is well annotated,
you can programmatically retrieve electrode-level metadata for any unit in your NWB file.

.. code-block:: python

    from pynwb import read_nwb

    nwbfile = read_nwb("output.nwb")

    # View all units as a DataFrame
    units_df = nwbfile.units.to_dataframe()
    print(units_df)

    # Access electrode information for each unit
    for unit_index in range(len(nwbfile.units)):
        unit_id = nwbfile.units.id[unit_index]
        electrode_refs = nwbfile.units.electrodes[unit_index]
        electrode_indices = list(electrode_refs.index)

        # Get electrode properties for this unit
        unit_electrodes = nwbfile.electrodes[electrode_indices]
        print(f"Unit {unit_id}:")
        print(f"  - Electrode indices: {electrode_indices}")
        print(f"  - Locations: {unit_electrodes['location']}")
        print(f"  - Groups: {unit_electrodes['group_name']}")
        print(f"  - X positions: {unit_electrodes['rel_x']}")
        print(f"  - Y positions: {unit_electrodes['rel_y']}")


Single Recording and Sorting Interface
----------------------------------------------------

For most spike sorting workflows, you have one recording interface and one sorting
interface that need to be linked together. The :py:class:`~neuroconv.converters.SortedRecordingConverter`
handles this by requiring an explicit mapping between unit IDs and their associated channel IDs.

Using Intan Recording Data
~~~~~~~~~~~~~~~~~~~~~~~~~

This example demonstrates linking data from an Intan recording system with
Kilosort sorting results:

.. code-block:: python

    from neuroconv.converters import SortedRecordingConverter
    from neuroconv.datainterfaces import (
        IntanRecordingInterface,
        KiloSortSortingInterface
    )

    # Initialize interfaces
    recording_interface = IntanRecordingInterface(
        file_path="path/to/intan_data.rhd"
    )
    sorting_interface = KiloSortSortingInterface(
        folder_path="path/to/kilosort_output"
    )

Examine the available channel and unit IDs:

.. code-block:: python

    # Access channel IDs from the recording
    print(recording_interface.channel_ids)
    # Example output: ['A-000', 'A-001', 'A-002', 'A-003', ...]

    # Access unit IDs from the sorting
    print(sorting_interface.unit_ids)
    # Example output: ['0', '1', '2', '3', ...]

Create the mapping between units and channels. This mapping specifies which recording channels were used to detect each sorted unit:

.. code-block:: python

    unit_ids_to_channel_ids = {
        "0": ["A-000", "A-001", "A-002"],    # Unit 0 detected on 3 channels
        "1": ["A-003", "A-004"],             # Unit 1 detected on 2 channels
        "2": ["A-005", "A-006", "A-007"],    # Unit 2 detected on 3 channels
        "3": ["A-008"],                      # Unit 3 detected on 1 channel
        # ... continue for all units
    }

.. note::

    Every unit from the sorting interface must have a corresponding channel mapping. The channel IDs must exactly match those from the recording interface.

Create the converter and run the conversion:

.. code-block:: python

    converter = SortedRecordingConverter(
        recording_interface=recording_interface,
        sorting_interface=sorting_interface,
        unit_ids_to_channel_ids=unit_ids_to_channel_ids
    )

    nwbfile = converter.create_nwbfile()
    from neuroconv.tools import configure_and_write_nwbfile
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path="path/to/output.nwb")
