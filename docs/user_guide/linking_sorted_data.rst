.. _linking_sorted_data:

How to Link Sorted Data to Electrodes
===================================

The ``SortedRecordingConverter`` maintains proper linkage between sorted units and their corresponding recording channels in NWB files.
It handles the critical relationship between ``Units`` and ``Electrodes`` tables by:

* Creating electrode table regions for each unit
* Maintaining electrode group and device relationships
* Mapping channel IDs to electrode indices correctly

This automated handling ensures proper provenance tracking in the NWB file, which is essential for interpreting and analyzing sorted electrophysiology data.

Basic Usage
----------

Single Probe and Single Recording
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This example demonstrates linking data from a single Neuropixel probe recorded with SpikeGLX and sorted with Kilosort.

The converter requires three components:

1. A recording interface (:py:class:`~neuroconv.datainterfaces.ecephys.spikeglx.spikeglxrecordinginterface.SpikeGLXRecordingInterface`)
2. A sorting interface (:py:class:`~neuroconv.datainterfaces.ecephys.kilosort.kilosortinterface.KiloSortSortingInterface`)
3. A mapping between unit IDs and their associated channel IDs

First, instantiate the interfaces::

    from neuroconv import SortedRecordingConverter
    from neuroconv.datainterfaces import SpikeGLXRecordingInterface, KiloSortSortingInterface

    # Initialize interfaces
    recording_interface = SpikeGLXRecordingInterface(
        folder_path="path/to/spikeglx_data",
        stream_id="imec0.ap"
    )
    sorting_interface = KiloSortSortingInterface(
        folder_path="path/to/kilosort_data"
    )

Access channel and unit IDs through interface properties::

    # Access channel IDs
    print(recording_interface.channel_ids)
    # Example output: ['imec0.ap#AP0', 'imec0.ap#AP1', 'imec0.ap#AP2', ...]

    # Access unit IDs
    print(sorting_interface.unit_ids)
    # Example output: ['0', '1', '2', ...]

Define the mapping between units and channels::

    unit_ids_to_channel_ids = {
        "0": ["imec0.ap#AP0", "imec0.ap#AP1"],  # Unit 0 detected on two channels
        "1": ["imec0.ap#AP2"],                   # Unit 1 detected on one channel
        "2": ["imec0.ap#AP3", "imec0.ap#AP4"],   # Unit 2 detected on two channels
        ...  # Map all remaining units to their respective channels
    }

.. note::

    Every unit from the sorting interface must have a corresponding channel mapping.

Create the converter and run the conversion::

    converter = SortedRecordingConverter(
        recording_interface=recording_interface,
        sorting_interface=sorting_interface,
        unit_ids_to_channel_ids=unit_ids_to_channel_ids
    )

    nwbfile = converter.run_conversion(nwbfile_path="path/to/output.nwb")
