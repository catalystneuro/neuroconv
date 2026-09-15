Adding Multiple Sorting Interfaces
===================================

If you have a session with multiple probes or the same recording is sorted with
different algorithms, you may need to handle multiple spike sorting outputs. This
how-to will guide you through the process of adding more than one sorting interface
to your NWB files using NeuroConv.

Why Unit ID Management Matters
-------------------------------

When you have multiple sorting outputs (e.g., from different algorithms like
Kilosort and MountainSort), they might have overlapping unit IDs (0, 1, 2, etc.).
If they do, adding them naively in NeuroConv will lead to the rows corresponding
to the second sorter being skipped, as NeuroConv will identify them as the same
unit and skip them to avoid duplicates. To handle this problem you have two main
approaches:

1. **Rename units** to create unique identifiers before merging into the
    canonical Units table
2. **Keep separate tables for each sorter** in the processing module to maintain original
    sorter IDs

Setting Up the Example
-----------------------

First, let's create two mock sorting interfaces to demonstrate the concepts:

.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockSortingInterface
    from neuroconv import ConverterPipe

    # Create two sorting interfaces with overlapping unit IDs
    sorting_interface1 = MockSortingInterface(num_units=4)
    sorting_interface2 = MockSortingInterface(num_units=4)

    print("Sorting 1 unit IDs:", sorting_interface1.units_ids)
    print("Sorting 2 unit IDs:", sorting_interface2.units_ids)

Expected output:

.. code-block:: text

    Sorting 1 unit IDs: ['0', '1', '2', '3']
    Sorting 2 unit IDs: ['0', '1', '2', '3']

The units from both sorting interfaces have the same IDs, which will cause conflicts.

Approach 1: Canonical Units Table with Unit Renaming
-----------------------------------------------------

This approach merges all sorting results into the main NWB Units table after
renaming units to avoid ID conflicts.

Step 1: Add First Sorting to NWB File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # Create NWB file with first sorting (no renaming needed)
    nwbfile = sorting_interface1.create_nwbfile()
    print("Units after adding first sorting:")
    print(nwbfile.units.to_dataframe()[['unit_name']])

Expected output:

.. code-block:: text

    Units after adding first sorting:
    id  unit_name
    0           0
    1           1
    2           2
    3           3

Step 2: Rename Units in Second Sorting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Before adding the second sorting, we need to rename its units to avoid
conflicts:

.. code-block:: python

    # Method 1: Using the new rename_unit_ids method with dictionary mapping
    unit_rename_map = {
        '0': 'sorter2_unit_0',
        '1': 'sorter2_unit_1',
        '2': 'sorter2_unit_2',
        '3': 'sorter2_unit_3'
    }
    mock_sorting2.rename_unit_ids(unit_rename_map)

    print("Sorting 2 unit IDs after renaming:", mock_sorting2.units_ids)

Expected output:

.. code-block:: text

    Sorting 2 unit IDs after renaming: ['sorter2_unit_0', 'sorter2_unit_1', 'sorter2_unit_2', 'sorter2_unit_3']

Step 3: Add Second Sorting to Existing NWB File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # Add the renamed sorting to the existing NWB file
    mock_sorting2.add_to_nwbfile(nwbfile=nwbfile)

    print("Units after adding both sortings:")
    units_df = nwbfile.units.to_dataframe()
    print(units_df[['unit_name']])

Expected output:

.. code-block:: text

    Units after adding both sortings:
    id      unit_name
    0           0
    1           1
    2           2
    3           3
    4   sorter2_unit_0
    5   sorter2_unit_1
    6   sorter2_unit_2
    7   sorter2_unit_3


Advantages of This Approach
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- All units are in the canonical Units table, making analysis easier
- Creates session-unique unit identifiers
- Standard location that analysis tools expect

Disadvantages
~~~~~~~~~~~~~

- Requires careful unit ID management
- Original sorter IDs are lost unless preserved in unit properties

Approach 2: Separate Tables in Processing Module
-------------------------------------------------

This approach keeps each sorting in its own table within the processing module,
preserving original unit IDs.

.. code-block:: python

    # Create fresh sorting interfaces
    mock_sorting1 = MockSortingInterface(num_units=4)
    mock_sorting2 = MockSortingInterface(num_units=4)

    # Set up data interfaces with descriptive names
    data_interfaces = {
        "kilosort_sorting": mock_sorting1,
        "mountainsort_sorting": mock_sorting2,
    }

    # Create converter with both sortings
    converter = ConverterPipe(data_interfaces=data_interfaces)

    # Configure to write each sorting to separate processing tables
    conversion_options = {
        "kilosort_sorting": {
            "write_as": "processing",
            "units_name": "UnitsKilosort",
            "units_description": "Units detected by Kilosort spike sorting algorithm"
        },
        "mountainsort_sorting": {
            "write_as": "processing",
            "units_name": "UnitsMountainSort",
            "units_description": "Units detected by MountainSort spike sorting algorithm"
        },
    }

    # Create NWB file with separate tables
    nwbfile = converter.create_nwbfile(conversion_options=conversion_options)

    print("Processing module contents:")
    print(list(nwbfile.processing['ecephys'].data_interfaces.keys()))
    # ['UnitsKilosort', 'UnitsMountainSort']

Advantages of This Approach
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Preserves original unit IDs from each sorter
- Clear provenance of which algorithm produced which units
- No risk of ID conflicts

Disadvantages
^^^^^^^^^^^^^

- Analysis tools need to know which table to use
- More complex to work with multiple tables
- Units are not in the standard NWB Units location



Alternative Renaming Approaches
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also use more descriptive naming schemes:

.. code-block:: python

    # Descriptive naming based on sorting algorithm
    descriptive_map = {
        '0': 'kilosort_cluster_01',
        '1': 'kilosort_cluster_02',
        '2': 'kilosort_cluster_03',
        '3': 'kilosort_cluster_04'
    }

    # Or cell-type based naming
    celltype_map = {
        '0': 'pyramidal_neuron_1',
        '1': 'interneuron_1',
        '2': 'pyramidal_neuron_2',
        '3': 'unclassified_1'
    }


Adding Custom Properties to the Units Table
-------------------------------------------

When using the canonical Units table approach, you may want to add additional
columns that provide important context about your units. This is particularly
useful when combining units from multiple probes or sorting algorithms. You can
add custom properties using the sorting extractor's ``set_property`` method. Note that
if the sorting extractor already pre-loads properties those will be automatically
added to the units table.

Adding Probe Information
~~~~~~~~~~~~~~~~~~~~~~~~

Here's how to add a "probe" column to distinguish units from different probes:

.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockSortingInterface

    # Create two sorting interfaces representing different probes
    probe1_sorting = MockSortingInterface(num_units=4)
    probe2_sorting = MockSortingInterface(num_units=3)

    # Rename units to avoid conflicts (do this first)
    probe1_sorting.rename_unit_ids({
        '0': 'a',
        '1': 'b',
        '2': 'c',
        '3': 'd',
    })

    probe2_sorting.rename_unit_ids({
        '0': 'e',
        '1': 'f',
        '2': 'g',
    })

    # Add probe information as a property for each sorting
    probe1_sorting.sorting_extractor.set_property(
        key="probe",
        values=["probe_A"] * 4,  # All 4 units are from probe A
        ids=["a", "b", "c", "d"]
    )

    probe2_sorting.sorting_extractor.set_property(
        key="probe",
        values=["probe_B"] * 3,  # All 3 units are from probe B
        ids=["e", "f", "g"]  # Use renamed IDs
    )

    # Create NWB file and add both sortings
    nwbfile = probe1_sorting.create_nwbfile()
    probe2_sorting.add_to_nwbfile(nwbfile=nwbfile)

    # Verify the probe column was added
    units_df = nwbfile.units.to_dataframe()
    print("Units table with probe information:")
    print(units_df[['unit_name', 'probe']])

Expected output:

.. code-block:: text

    Units table with probe information:
    id  unit_name    probe
    0          a  probe_A
    1          b  probe_A
    2          c  probe_A
    3          d  probe_A
    4          e  probe_B
    5          f  probe_B
    6          g  probe_B

Adding Algorithm Provenance Information
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also add information about which sorting algorithm was used:

.. code-block:: python

    # Create sorting interfaces for different algorithms
    kilosort_sorting = MockSortingInterface(num_units=3)
    mountainsort_sorting = MockSortingInterface(num_units=2)

    # Rename units to avoid conflicts (do this first)
    kilosort_sorting.rename_unit_ids({
        '0': 'a',
        '1': 'b',
        '2': 'c',
    })

    mountainsort_sorting.rename_unit_ids({
        '0': 'd',
        '1': 'e',
    })

    # Add algorithm information
    kilosort_sorting.sorting_extractor.set_property(
        key="algorithm",
        values=["kilosort"] * 3,
        ids=["a", "b", "c"]
    )

    mountainsort_sorting.sorting_extractor.set_property(
        key="algorithm",
        values=["mountainsort"] * 2,
        ids=["d", "e"]  # Use renamed IDs
    )

    # You can add multiple properties at once
    kilosort_sorting.sorting_extractor.set_property(
        key="quality_score",
        values=[0.95, 0.87, 0.92],
        ids=["a", "b", "c"]
    )

    mountainsort_sorting.sorting_extractor.set_property(
        key="quality_score",
        values=[0.89, 0.76],
        ids=["d", "e"]  # Use renamed IDs
    )

    # Create NWB file with both sortings
    nwbfile = kilosort_sorting.create_nwbfile()
    mountainsort_sorting.add_to_nwbfile(nwbfile=nwbfile)

    # View the enriched units table
    units_df = nwbfile.units.to_dataframe()
    print("Units table with algorithm and quality information:")
    print(units_df[['unit_name', 'algorithm', 'quality_score']])

Expected output:

.. code-block:: text

    Units table with algorithm and quality information:
    id  unit_name      algorithm  quality_score
    0       a       kilosort           0.95
    1       b       kilosort           0.87
    2       c       kilosort           0.92
    3       d   mountainsort           0.89
    4       e   mountainsort           0.76
