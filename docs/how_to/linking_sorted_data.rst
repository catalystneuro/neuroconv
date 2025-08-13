.. _linking_sorted_data:

How to Link Sorted Data to Electrodes
=====================================

When converting spike sorting results to NWB format, it is essential to preserve the
relationship between sorted units and the recording electrodes that detected them.
This linkage ensures that each unit inherits all electrode-level metadata stored in the
`electrodes` table of the NWB file.

For this linkage to be useful, the `electrodes` table itself must be **well annotated**,
including accurate information on brain area, anatomical coordinates, electrode geometry,
and any probe-specific metadata. Without this detail, the benefits of unit–electrode
linking are severely limited.

Why Link Units to Electrodes?
-----------------------------

Proper electrode linking allows each unit to be formally connected to all the metadata
describing its recording site. This enables both spatial and anatomical localization
of units—information that is critical for accurate interpretation and reproducibility.

**Spatial Analysis**
    With well-annotated electrode positions (e.g., rel_x, rel_y, rel_z),
    future users of the NWBFile can determine where units lie within the probe, perform laminar
    analyses, assess depth-dependent firing properties, and investigate spatial
    organization such as receptive field gradients or clustering patterns across channels.

**Anatomical Analysis**
    Registering the probe's position in the brain allows anatomical features such as
    brain area, subregion, or cortical layer to be associated with electrodes and,
    by extension, with linked units.
    As an example, Liu et al. (2022) demonstrated how depth-resolved recordings across
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

In summary, linking units to well-annotated electrodes in NWB is not merely a bookkeeping
step—it is a prerequisite for spatially and anatomically grounded neuroscience. Without
both the linkage and high-quality electrode annotations, many types of interpretation and
analysis become impossible making the data less useful for future users.

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


General and Flexible Case: Single Recording and Sorting Interface
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

    nwbfile = converter.run_conversion(nwbfile_path="path/to/output.nwb")

Understanding IDs, Indices, and Mapping
---------------------------------------

When creating the unit-to-channel mapping, it's important to understand the relationship
between IDs and indices across different components:

**Recording Interface**
    - ``recording_interface.channel_ids``: Array of channel ID strings (e.g., ``['A-000', 'A-001', ...]``)
    - Channel indices: 0-based positions in the channel_ids array

**Sorting Interface**
    - ``sorting_interface.unit_ids``: Array of unit ID strings (e.g., ``['unit_a', 'unit_b', 'unit_c', ...]``)
    - Unit indices: 0-based positions in the unit_ids array

**NWB Units Table**
    - Unit's Table indices: Indices of the unit when assigned in the NWB file


Creating the Mapping from Sorting Results
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some sorting algorithms return channel **indices** rather than channel **IDs**.
For example, Kilosort's ``get_best_channels`` function returns indices:

.. code-block:: python

    def get_best_channels(results_dir):
        """Get channel numbers with largest template norm for each cluster."""
        templates = np.load(results_dir / 'templates.npy')
        best_chans = (templates**2).sum(axis=1).argmax(axis=-1)
        return best_chans  # Returns indices, not IDs

To convert indices to IDs for the mapping, you need to understand how the different
components relate:

1. **Kilosort unit indices**: Position in the `best_channel_indices` array
2. **Kilosort channel indices**: Returned by `get_best_channels()`
3. **Recording channel IDs**: Actual channel identifiers
4. **Sorting unit IDs**: From the sorting interface

Here's the correct approach:

.. code-block:: python

    from pathlib import Path

    # Get channel indices from Kilosort results
    kilosort_dir = Path("path/to/kilosort_output")
    best_channel_indices = get_best_channels(kilosort_dir)  # Returns channel indices

    # Get the recording and sorting interfaces
    recording = recording_interface.recording_extractor
    sorting = sorting_interface.sorting_extractor

    # Create the mapping
    unit_ids_to_channel_ids = {}

    for kilosort_unit_idx, kilosort_channel_idx in enumerate(best_channel_indices):
        # Get the actual unit ID from the sorting interface
        sorting_unit_id = str(sorting.unit_ids[kilosort_unit_idx])

        # Convert channel index to channel ID using the recording
        # This assumes that kilosort maps positionally, unsure about this
        channel_id = recording.channel_ids[kilosort_channel_idx]

        unit_ids_to_channel_ids[sorting_unit_id] = [channel_id]



Special Case: SpikeGLX Multi-Probe Data
---------------------------------------

SpikeGLX recordings often contain data from multiple probes that have been sorted
independently. The :py:class:`~neuroconv.converters.SortedSpikeGLXConverter`
enhances the standard :py:class:`~neuroconv.converters.SpikeGLXConverterPipe`
with the ability to preserve sorting metadata and maintain proper unit-to-electrode
linkage across all probes.

Multiple Probes with Independent Sorting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example with multiple Neuropixels probes, each sorted independently:

.. code-block:: python

    from neuroconv.converters import SpikeGLXConverterPipe, SortedSpikeGLXConverter
    from neuroconv.datainterfaces import KiloSortSortingInterface

    # Initialize the SpikeGLX converter for all streams
    spikeglx_converter = SpikeGLXConverterPipe(
        folder_path="path/to/spikeglx_data"
    )

    # View available streams
    print(spikeglx_converter.data_interface_objects.keys())
    # Example output: dict_keys(['imec0.ap', 'imec0.lf', 'imec1.ap', 'imec1.lf', 'nidq'])

When working with multiple sorting interfaces, a common challenge arises when different sorters
produce units with identical IDs (e.g., both probes generating units "0", "1", "2"). The
:doc:`adding_multiple_sorting_interfaces` guide provides comprehensive strategies for handling
such scenarios. However, the :py:class:`~neuroconv.converters.SortedSpikeGLXConverter` automatically
resolves these conflicts by generating unique unit names using the pattern ``{stream_id}_unit_{original_id}``
(e.g., ``imec0_ap_unit_0``, ``imec1_ap_unit_0``) when conflicts are detected. If unit IDs are already
unique across all sorters, the original unit names are preserved.

Create sorting configuration for each sorted probe. Note the channel ID format specific to SpikeGLX:

.. code-block:: python

    sorting_configuration = [
        {
            "stream_id": "imec0.ap",
            "sorting_interface": KiloSortSortingInterface(
                folder_path="path/to/imec0_kilosort_output"
            ),
            "unit_ids_to_channel_ids": {
                "0": ["imec0.ap#AP0", "imec0.ap#AP1", "imec0.ap#AP2"],
                "1": ["imec0.ap#AP3", "imec0.ap#AP4"],
                "2": ["imec0.ap#AP5", "imec0.ap#AP6"]
            }
        },
        {
            "stream_id": "imec1.ap",
            "sorting_interface": KiloSortSortingInterface(
                folder_path="path/to/imec1_kilosort_output"
            ),
            "unit_ids_to_channel_ids": {
                "0": ["imec1.ap#AP0", "imec1.ap#AP1"],
                "1": ["imec1.ap#AP2", "imec1.ap#AP3", "imec1.ap#AP4"],
                "2": ["imec1.ap#AP10", "imec1.ap#AP11"]
            }
        }
    ]

Create the converter and run the conversion:

.. code-block:: python

    # Create the sorted converter
    converter = SortedSpikeGLXConverter(
        spikeglx_converter=spikeglx_converter,
        sorting_configuration=sorting_configuration
    )

    # Run the conversion
    nwbfile = converter.run_conversion(nwbfile_path="path/to/output.nwb")

.. note::

    * Only AP (action potential) streams can have sorting data
    * Currently supports one sorting interface per probe
    * All unit IDs from different probes will be added to the canonical Units table
