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


Single Recording and Sorting Interface
----------------------------------------------------

For most spike sorting workflows, you have one recording interface and one sorting
interface that need to be linked together. The :py:class:`~neuroconv.converters.SortedRecordingConverter`
handles this by requiring an explicit mapping between unit IDs and their associated channel IDs.

Using Intan Recording Data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The mapping is something you supply, because most sorting formats record only which
spikes belong to which unit and say nothing about which channels those units were
detected on. This example demonstrates linking data from an Intan recording system with
MountainSort sorting results:

.. code-block:: python

    from neuroconv.converters import SortedRecordingConverter
    from neuroconv.datainterfaces import (
        IntanRecordingInterface,
        MdaSortingInterface
    )

    # Initialize interfaces
    recording_interface = IntanRecordingInterface(
        file_path="path/to/intan_data.rhd"
    )
    sorting_interface = MdaSortingInterface(
        file_path="path/to/firings.mda", sampling_frequency=30_000.0
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

.. note::

    A few sorting formats do record which channels each unit was detected on. Where they do, the interface offers a helper that reads it out, and the dictionary above should not be written by hand: see :ref:`Deriving the Mapping from Kilosort Output <deriving_mapping_from_kilosort>`. Everything else on this page, including the converter itself, is the same either way.

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


.. _deriving_mapping_from_kilosort:

Deriving the Mapping from Kilosort Output
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Kilosort is one of the formats that does record which channels each unit was detected on: it fits
every template on a fixed number of nearby channels and leaves it exactly zero everywhere else, so
the mapping is in ``templates.npy`` and does not have to be written by hand. This is a convenience
specific to Kilosort; the converter and everything else above are unchanged.
:py:meth:`~neuroconv.datainterfaces.ecephys.kilosort.kilosortdatainterface.KiloSortSortingInterface.get_unit_ids_to_channel_ids`
reads it out and names the channels with the recording's channel IDs:

.. code-block:: python

    from neuroconv.converters import SortedRecordingConverter
    from neuroconv.datainterfaces import (
        IntanRecordingInterface,
        KiloSortSortingInterface
    )

    recording_interface = IntanRecordingInterface(
        file_path="path/to/intan_data.rhd"
    )
    sorting_interface = KiloSortSortingInterface(
        folder_path="path/to/kilosort_output", gain_to_uV=0.195
    )

    unit_ids_to_channel_ids = sorting_interface.get_unit_ids_to_channel_ids(
        recording_interface=recording_interface
    )
    print(unit_ids_to_channel_ids[0])
    # Example output: ['A-000', 'A-001', 'A-002', 'A-016', 'A-017']

The converter is then built exactly as above, and the waveforms follow the linkage: each unit's
``waveform_mean`` is written over the electrodes it is linked to rather than over the whole probe.

.. code-block:: python

    converter = SortedRecordingConverter(
        recording_interface=recording_interface,
        sorting_interface=sorting_interface,
        unit_ids_to_channel_ids=unit_ids_to_channel_ids
    )

    nwbfile = converter.create_nwbfile()

**What the call asserts.** The recording you pass must be the one Kilosort was run on, with the same
channels in the same order. ``channel_map.npy`` records which channels of the sorted binary each
template lives on, as positions rather than names, so nothing in the sorter folder can confirm that
your recording is that binary. The helper rejects what the folder can disprove, comparing the channel
count and sampling rate against ``params.py``, but a different recording of the same shape will pass.

**The mistake this catches.** If bad channels were removed before the binary was written, pass the
recording that was sorted rather than the raw one, since the channel positions differ. Note also
that ``dat_path`` in ``params.py`` is not a reliable way to identify the original recording: Kilosort
2.5 points it at ``temp_wh.dat``, its own whitened and filtered copy, rather than at your data.

The same mapping is what :py:class:`~neuroconv.converters.SortedSpikeGLXConverter` takes for the
multi-probe case below, so derive it once per probe and pass it through in the same way.

**How this combines with** ``waveform_representation``. Once the converter supplies the electrodes,
they decide the layout, so the interface's ``"dense"`` default gives way to them and there is nothing
to set. ``"none"`` still means what it says, and pairs with linking perfectly well: the units come
out on their real electrodes with no waveforms. ``"sparse_with_electrodes_table"`` is refused here,
because it asks the interface to invent a probe while you are handing it a real one.

**If you do not link at all**, the Kilosort interface still writes the templates. The channel axis
then spans every channel Kilosort sorted, in ``channel_map.npy`` order and the same for every unit,
and is not connected to any electrode. That is a complete output rather than a degraded one, so there
is no reason to invent a pairing in order to satisfy this page.

SpikeGLX Multi-Probe Data
--------------------------------------------------------

SpikeGLX recordings often contain data from multiple probes that have been sorted
independently. The :py:class:`~neuroconv.converters.SortedSpikeGLXConverter`
enhances the standard :py:class:`~neuroconv.converters.SpikeGLXConverterPipe`
with the ability to preserve sorting metadata and maintain proper unit-to-electrode
linkage across all probes.

**Interface Names in SpikeGLX:**
For SpikeGLX data, interface names correspond to recording streams which combine
probe and band information (e.g., "imec0.ap" = probe 0 + ap band,
"imec1.lf" = probe 1 + lf band). Only AP interfaces can have sorting data associated
with them.

Multiple Probes with Independent Sorting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example with multiple Neuropixels probes, each sorted independently:

.. code-block:: python

    from neuroconv.converters import SpikeGLXConverterPipe, SortedSpikeGLXConverter
    from neuroconv.datainterfaces import KiloSortSortingInterface

    # Initialize the SpikeGLX converter for all streams
    spikeglx_converter = SpikeGLXConverterPipe(
        folder_path="path/to/spikeglx_data"
    )

    # View available interfaces
    print(spikeglx_converter.data_interface_objects.keys())
    # Example output: dict_keys(['imec0.ap', 'imec0.lf', 'imec1.ap', 'imec1.lf', 'nidq'])

When working with multiple sorting interfaces, a common challenge arises when different sorters
produce units with identical IDs (e.g., both probes generating units "0", "1", "2"). The
:doc:`adding_multiple_sorting_interfaces` guide provides comprehensive strategies for handling
such scenarios. However, the :py:class:`~neuroconv.converters.SortedSpikeGLXConverter` automatically
resolves these conflicts by generating unique unit names using the pattern ``{interface_name}_unit_{original_id}``
(e.g., ``imec0_ap_unit_0``, ``imec1_ap_unit_0``) when conflicts are detected. If unit IDs are already
unique across all sorters, the original unit names are preserved.

Create sorting configuration for each sorted probe. Note the channel ID format specific to SpikeGLX:

.. code-block:: python

    sorting_configuration = [
        {
            "interface_name": "imec0.ap",
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
            "interface_name": "imec1.ap",
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

    # Create NWB file and write to disk
    nwbfile = converter.create_nwbfile()
    from neuroconv.tools import configure_and_write_nwbfile
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path="path/to/output.nwb")


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
