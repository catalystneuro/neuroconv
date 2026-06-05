.. _ecephys_metadata_structure:

Ecephys Metadata Structure
==========================

This document describes the dict-based metadata structure used by the extracellular electrophysiology
(ecephys) pipeline in NeuroConv. It is intended for developers who are contributing new recording
interfaces or modifying existing ones.

The shape described here is the target the pipeline tool functions in
``tools/spikeinterface/spikeinterface.py`` will read once the dict-based ecephys pipeline lands.
Recording interfaces will be migrated in subsequent PRs. Until then, ecephys conversions continue
to use the existing list-based metadata format.


Design Principles
-----------------

The ecephys metadata system follows the same core principles as the ophys system
(see :ref:`ophys_metadata_structure`):

1. **Dictionary-Based Organization**
   Metadata is organized using dictionaries with meaningful keys. Dictionaries allow direct access
   to specific components by name, which is clearer and less error-prone than positional access.

   .. code-block:: python

       metadata["Ecephys"]["ElectrodeGroups"]["visual_cortex"]["location"] = "V1 binocular zone"

2. **Consistent metadata_key Across Interfaces**
   Every ecephys interface uses a single ``metadata_key`` parameter that propagates to its
   components (Device, ElectrodeGroup, ElectricalSeries). This matches the ophys convention.

3. **Explicit References**
   Components reference each other using explicit ``_metadata_key`` fields where the relationship
   is 1:1 (for example an ElectrodeGroup references its Device via ``device_metadata_key``).
   Where the relationship is many-to-many (ElectricalSeries to ElectrodeGroup), the link is
   resolved through the electrodes table, not an explicit metadata field. See
   :ref:`no_electrode_group_metadata_key` below.

4. **Top-Level Devices**
   Devices are stored at the top level (``metadata["Devices"]``) enabling device sharing across
   ecephys, ophys, and other modalities. A single probe can be referenced by multiple electrode
   groups, or the same ``Devices`` entry can be reused by an ophys interface in a mixed recording.

5. **Provenance-First get_metadata()**
   The ``get_metadata()`` method returns only values extracted from the source data, not defaults.
   Defaults are applied at NWB object creation time.


Metadata Structure Overview
---------------------------

The complete ecephys metadata structure:

.. code-block:: python

    metadata = {
        "NWBFile": {...},  # Session-level metadata
        "Subject": {...},  # Subject information

        "Devices": {
            "visual_cortex_probe": {
                "name": "Neuropixels 1.0",
                "description": "IMEC Neuropixels 1.0 probe, serial 19011119132",
                "manufacturer": "IMEC",
            },
            "hippocampus_probe": {
                "name": "A4x8-5mm-50-200-177",
                "description": "NeuroNexus 4-shank silicon probe, 8 sites per shank",
                "manufacturer": "NeuroNexus",
            },
        },

        "Ecephys": {
            "ElectrodeGroups": {
                "visual_cortex_probe": {
                    "name": "ElectrodeGroupV1",
                    "description": "IMEC probe shank in V1",
                    "location": "V1 binocular zone",
                    "device_metadata_key": "visual_cortex_probe",  # Reference to device
                },
                "hippocampus_shank_0": {
                    "name": "Shank0",
                    "description": "Shank 0 of the A4x8 probe, dorsal CA1",
                    "location": "CA1 pyramidal layer",
                    "device_metadata_key": "hippocampus_probe",  # Multiple groups share one device
                },
                "hippocampus_shank_1": {
                    "name": "Shank1",
                    "description": "Shank 1 of the A4x8 probe, dorsal CA1",
                    "location": "CA1 pyramidal layer",
                    "device_metadata_key": "hippocampus_probe",
                },
                "hippocampus_shank_2": {
                    "name": "Shank2",
                    "description": "Shank 2 of the A4x8 probe, dorsal CA1",
                    "location": "CA1 pyramidal layer",
                    "device_metadata_key": "hippocampus_probe",
                },
                "hippocampus_shank_3": {
                    "name": "Shank3",
                    "description": "Shank 3 of the A4x8 probe, dorsal CA1",
                    "location": "CA1 pyramidal layer",
                    "device_metadata_key": "hippocampus_probe",
                },
            },

            "ElectricalSeries": {
                "visual_cortex_probe": {
                    "name": "ElectricalSeriesV1",
                    "description": "Raw AP-band acquisition traces from V1",
                },
                "hippocampus_probe": {
                    "name": "ElectricalSeriesHPC",
                    "description": "Raw broadband traces from the A4x8 probe",
                },
            },
        },
    }

This layout shows the two patterns the dict format expresses:

- **One device per group (1:1).** ``visual_cortex_probe`` appears once in ``Devices`` and once in
  ``ElectrodeGroups``, with the same key. This is the common single-probe case.
- **One device shared across many groups (1:N).** ``hippocampus_probe`` appears once in
  ``Devices``, and each shank gets its own ``ElectrodeGroups`` entry pointing at it via
  ``device_metadata_key``. This is how multi-shank silicon probes are represented: one physical
  substrate, several electrode groups.

Each interface contributes one ``ElectricalSeries`` entry indexed by its ``metadata_key`` (see
:ref:`single_electrical_series_per_interface`). The per-channel link from a sample in the
``ElectricalSeries`` to its ``ElectrodeGroup`` is resolved through the electrodes table at write
time, not through a metadata key (see :ref:`no_electrode_group_metadata_key`).


The metadata_key Parameter
--------------------------

Ecephys recording interfaces accept a ``metadata_key`` parameter that selects the ElectricalSeries
entry to write. The same key is the primary lookup for the device and electrode group chain.
When ``None`` (the default), the interface generates a unique key from parameters that make the
interface unique (e.g. stream name). Explicit values let the caller deliberately share keys across
interfaces.

``add_recording_to_nwbfile`` takes the same ``metadata_key`` argument and is the pipeline-level
entry point. Passing ``metadata_key`` to this function opts the call into the dict-based path
regardless of other signals.

Key Propagation
~~~~~~~~~~~~~~~

For a recording interface with ``metadata_key="visual_cortex_probe"``:

- ``metadata["Ecephys"]["ElectricalSeries"]["visual_cortex_probe"]`` - The primary object (direct
  lookup via ``metadata_key``).
- ``metadata["Ecephys"]["ElectrodeGroups"][group_name]`` - Resolved from the recording's
  ``group_name`` channel property. Each channel carries its own ``group_name``, so the pipeline
  looks up the entry whose ``"name"`` matches.
- ``metadata["Devices"][device_metadata_key]`` - Resolved via ``device_metadata_key`` inside each
  matched ``ElectrodeGroups`` entry.

In the simplest case, the interface's ``metadata_key`` and the group name are the same value,
which is what ``get_metadata()`` produces by default. The indirection through ``device_metadata_key``
lets multiple electrode groups share a single Device entry.


.. _no_electrode_group_metadata_key:

No electrode_group_metadata_key on ElectricalSeries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unlike ophys ``MicroscopySeries`` (which carries ``imaging_plane_metadata_key``), an
``ElectricalSeries`` entry does **not** carry an ``electrode_group_metadata_key`` field. The reason
is structural: an NWB ``ElectricalSeries`` does not directly reference an ``ElectrodeGroup``. It
references the ``electrodes`` table via a ``DynamicTableRegion``, and each row of that table has
its own ``group`` column. The ``ElectricalSeries`` to ``ElectrodeGroup`` relationship is therefore
many-to-many, not 1:1.

The pipeline resolves the linkage implicitly from the recording's SpikeInterface channel properties:
each channel has a ``group`` property, which becomes the ``group_name`` column of the electrodes
table, which links each row to its ``ElectrodeGroup``. Adding an explicit
``electrode_group_metadata_key`` on ``ElectricalSeries`` would be wrong-shaped.

Multiple ElectricalSeries per NWBFile are already supported without any such field: the
``SpikeGLXConverter`` pattern instantiates one recording interface per stream (AP, LF, NIDQ), each
with its own ``metadata_key``, each writing its own entry under
``metadata["Ecephys"]["ElectricalSeries"]``. Each interface's recording carries its own channels
and their own group properties, so the per-row ``group`` linkage is sufficient.


.. _single_electrical_series_per_interface:

Single ElectricalSeries per Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A recording interface writes exactly one ``ElectricalSeries`` per ``metadata_key``. To produce
multiple series in one NWB file, create multiple interfaces (as in ``SpikeGLXConverter``) or call
``add_recording_to_nwbfile`` multiple times with different ``metadata_key`` values.

A future capability in which a single interface produces multiple ``ElectricalSeries`` from the
same recording (with explicit channel selection per series) is not supported today. That would
need a separate design and is out of scope for the dict-based pipeline work.


Naming: ElectricalSeries versus other candidates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The outer key under ``metadata["Ecephys"]`` is ``ElectricalSeries``, matching the NWB core class
name. The ophys pipeline follows a different convention (``MicroscopySeries``, borrowed from
``ndx-microscopy``) because ndx-microscopy is an accepted NWB enhancement proposal with a clear
path to core. ``ndx-extracellular-channels`` does not yet have the same status, so borrowing its
terminology would adopt unfamiliar vocabulary without the forward-compat payoff. Keeping
``ElectricalSeries`` mirrors the object users already write today and covers every ecephys use
case NeuroConv produces (extracellular microelectrodes, LFP, ECoG, EEG).


Linking and Object Creation
---------------------------

Each interface's goal is to create an ``ElectricalSeries`` in NWB, along with its linked
``ElectrodeGroup`` (one per distinct channel group in the recording) and ``Device`` objects.

Contained vs Linked Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In NWB, ``Device`` and ``ElectrodeGroup`` are separate, shareable objects. An ``ElectrodeGroup``
links to its ``Device``. An ``ElectricalSeries`` links to the ``electrodes`` table rows (which in
turn link to their ``ElectrodeGroup``). All three are **linked components** and get separate
metadata entries.

How Linking Works
~~~~~~~~~~~~~~~~~

In the metadata dict we do not have actual NWB objects yet, only dictionaries. Relationships use
``_metadata_key`` fields:

``device_metadata_key`` is used in ElectrodeGroup to reference its Device:

.. code-block:: python

    electrode_group = {
        "name": "0",
        "description": "Shank 0",
        "location": "V1",
        "device_metadata_key": "visual_cortex_probe",  # Points to metadata["Devices"]["visual_cortex_probe"]
    }

The ``ElectricalSeries`` to ``ElectrodeGroup`` linkage is resolved through the electrodes table
and does not have an explicit metadata field (see :ref:`no_electrode_group_metadata_key`).

When Objects Are Created
~~~~~~~~~~~~~~~~~~~~~~~~

Linked objects (Devices, ElectrodeGroups) are created when ``add_recording_to_nwbfile`` is called.
The metadata dict defines what *could* be created; the ``_metadata_key`` references and the
recording's channel group properties determine what actually gets written.

The rules are:

1. Devices and ElectrodeGroups are created lazily: only entries reached through a ``_metadata_key``
   chain or matched to a channel group get written. Entries present in the metadata dict but not
   reachable are ignored. This means a shared YAML can describe all devices in a project and only
   the ones actually linked end up in the NWB file.

2. If a required link is missing (an ElectrodeGroup entry has no ``device_metadata_key``), a
   default Device is created and linked automatically.

3. If the recording contains a channel ``group_name`` with no matching entry in
   ``metadata["Ecephys"]["ElectrodeGroups"]``, a default ElectrodeGroup is generated for that
   group and linked to the default Device.

4. For shared resources (two electrode groups from the same probe), both group entries reference
   the same ``device_metadata_key``. The Device is created by whichever group is written first
   and reused thereafter.

.. code-block:: python

    # Two electrode groups sharing one probe.
    metadata["Devices"]["shared_probe"] = {
        "name": "Neuropixels 1.0",
        "description": "IMEC Neuropixels 1.0 probe",
        "manufacturer": "IMEC",
    }

    metadata["Ecephys"]["ElectrodeGroups"]["shank_0"] = {
        "name": "0",
        "description": "Shank 0",
        "location": "V1",
        "device_metadata_key": "shared_probe",
    }

    metadata["Ecephys"]["ElectrodeGroups"]["shank_1"] = {
        "name": "1",
        "description": "Shank 1",
        "location": "V1",
        "device_metadata_key": "shared_probe",
    }

Device keys are independent of any interface's ``metadata_key`` and can be any arbitrary string.
No interface "owns" the device; it is created at write time by whichever interface first follows
the reference chain to it.
