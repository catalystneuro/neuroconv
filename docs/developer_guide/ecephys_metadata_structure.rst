.. _ecephys_metadata_structure:

Ecephys Metadata Structure
==========================

This document describes the extracellular electrophysiology metadata shape and the decisions that
produced it. It is intended for developers who are contributing new recording interfaces or modifying
existing ones, and the decisions below are the ones a new ecephys interface has to follow.

For user-facing documentation on how to annotate ecephys data, see :ref:`annotate_ecephys_metadata`.
For the rules that hold across every modality, see :ref:`metadata_principles`.


The Structure
-------------

The ecephys-specific metadata lives under ``metadata["Ecephys"]``. The devices it links out to live in
the registries that own them, shared with the other modalities:

.. code-block:: python

    metadata["DeviceModels"] = {
        "neuropixels_1_0": {  # keyed by metadata_key; "name" is the NWB object's name
            "name": "Neuropixels 1.0",
            "manufacturer": "IMEC",
            "model_number": "PRB_1_4_0480_1",
        },
    }

    metadata["Devices"] = {
        "probe_0": {
            "name": "NeuropixelsImec0",
            "description": "Implanted 2020-01-01.",
            "serial_number": "18194809281",
            "device_model_metadata_key": "neuropixels_1_0",  # -> DeviceModels
        },
    }

    metadata["Ecephys"] = {
        "ElectrodeGroups": {
            "shank_0": {
                "name": "Shank0",
                "description": "Shank 0 of the probe.",
                "location": "CA1",
                "device_metadata_key": "probe_0",            # -> Devices
            },
        },
        "ElectrodesTable": {
            "rows": {                                         # one entry per contact, keyed by a handle
                "shank_0_e0": {
                    "electrode_group_metadata_key": "shank_0",  # -> Ecephys.ElectrodeGroups, required
                    "electrode_name": "e0",                   # the contact's own identifier, where the format has one
                    "location": "CA1",
                    "rel_x": 0.0,
                    "rel_y": 0.0,
                    "imp": 1.0e6,
                    "shank_side": 0,                          # any other field becomes a column
                },
            },
            "columns": {                                      # keyed by the field the rows use
                "imp": {
                    "column_name": "impedance",               # the header it is written under
                    "description": "Electrode impedance in ohms, measured at 1 kHz.",
                    "dtype": "float64",
                },
                "shank_side": {
                    "description": "Which face of the shank the contact sits on.",
                    "column_categories": {                    # written as a MeaningsTable beside the column
                        "labels": {0: "front", 1: "back"},
                        "meanings": {0: "contact on the front face", 1: "contact on the back face"},
                    },
                },
            },
        },
        "ElectricalSeries": {
            "imec0.ap": {                                     # keyed by the interface's metadata_key
                "name": "ElectricalSeriesAP",
                "description": "Raw action-potential band, 30 kHz.",
                "channel_to_electrode": {"imec0.ap#AP0": "shank_0_e0"},  # channel id -> a key in rows
            },
        },
    }

    # The older column-description list. Still read, and superseded by ElectrodesTable.columns above.
    metadata["Ecephys"]["Electrodes"] = [{"name": "imp", "description": "Electrode impedance in ohms."}]

A series entry is passed to the ``ElectricalSeries`` constructor, so every field in it is a pynwb
argument except ``channel_to_electrode``, which the writer pops by name. A ``metadata_key`` naming no
entry raises: that is a caller mistake and not absent metadata.

A group entry that omits ``description`` or ``location`` has them filled from the modality's placeholder
factory. A group naming no ``device_metadata_key`` falls to the attached probe's identity when the
recording carries one probe, and to ``PlaceholderElectrodeDevice`` otherwise. Two group keys that share a
``name`` raise when rows point at both. The recording's own ``group`` and ``group_name`` properties have
to agree, and regrouping the channels after an interface set ``group_name`` at construction raises.

``ElectrodesTable`` is optional. Absent, the table is derived from the recording's channels and
properties. Present, each writing series must supply ``channel_to_electrode``, covering every current
channel and pointing to declared row keys. Source properties follow that saved association before
annotations are overlaid: a row wins for the fields it states, including explicit ``None`` values,
and inherits the rest. Row keys are handles, not a formula the writer recomputes to locate annotations.
The template generates rows and their mapping together; manual registries must save both as well.

Referenced rows are ordered by the recording's channels, followed by declared rows not reached by that
recording. Removed-channel mapping entries are allowed. A missing mapping or a target row that is not
declared raises; unreferenced rows are still valid electrodes. A row's ``electrode_group_metadata_key``
may be inherited from the source, but its resolved link must name a group. Explicit group links remain
authoritative. ``group``, ``group_name`` and ``channel_name`` remain writer-owned fields.

A source contact identity conflicting with a nonblank identity stated on the mapped row raises, as do
channels with different source contact/group identities mapped onto one row. Other column validation
rules are unchanged: descriptions must address existing fields, values must support declared dtypes,
and two declared rows cannot describe the same ``(group, electrode_name)``.

The rows are in NWB column space and not in spikeinterface property space: the ``location`` property
becomes ``rel_x``, ``rel_y`` and ``rel_z``, ``brain_area`` becomes ``location``, and ``gain_to_uV``,
``offset_to_uV`` and ``physical_unit`` are written into the ``ElectricalSeries`` and never reach the
table. ``exclude=`` on ``add_recording_to_nwbfile`` is how a property is kept out of the table on every
path, since a row that omits it inherits the recording's value.

The cross-references resolve as follows. ``device_metadata_key`` goes into the shared top-level
``metadata["Devices"]`` and ``device_model_metadata_key`` into ``metadata["DeviceModels"]``.
``electrode_group_metadata_key`` goes into ``metadata["Ecephys"]["ElectrodeGroups"]``, and each value of
``channel_to_electrode`` is a key of ``metadata["Ecephys"]["ElectrodesTable"]["rows"]``. A key naming no
entry raises in all four cases. The ``ElectricalSeries`` to ``ElectrodeGroup`` relationship has no key,
for the reason given below.

A recording interface's ``metadata_key`` addresses its ``ElectricalSeries`` entry and nothing else. The
migrated interfaces resolve a fixed snake_case constant in ``__init__``: ``"intan_recording"``,
``"blackrock_recording"``, ``"open_ephys_recording"``. SpikeGLX derives one per stream, ``"imec0.ap"``,
since a session produces several at once. An interface with no constant falls back to its ``es_key``,
which is how one that names its own series keys its entry without stating the same string twice.
``add_recording_to_nwbfile`` takes the same argument and requires it when the block is keyed. See
:ref:`metadata_key_naming` for the cross-modality rule. The older list-based block is translated where it
enters the library, so nothing downstream is written against it.

``get_metadata_template()`` returns this whole structure with what the recording carries filled in and
every field only the experimenter can supply set to ``None``: the series description, a group's
description and location, the device where no attached probe names one, each row's ``location`` where
the format records no brain area, and the columns NWB defines that the recording did not carry. A
required blank still ``None`` at write time is refused by name rather than guessed at, which is the
rule in :ref:`metadata_principles`, and a deleted field falls back to what the recording says.


Design Decisions
----------------

No ``electrode_group_metadata_key`` on an ``ElectricalSeries`` entry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An ``ElectricalSeries`` entry does not name its electrode group, unlike an ophys ``MicroscopySeries``,
which carries ``imaging_plane_metadata_key``.

The reason is structural. An NWB ``ElectricalSeries`` does not reference an ``ElectrodeGroup``. It
references rows of the electrodes table through a ``DynamicTableRegion``, and each row carries its own
``group``. The relationship is therefore many-to-many and is resolved through the table: on the derived
path from the recording's channel groups, and on the stated path from each row's
``electrode_group_metadata_key``. A key on the series would be wrong-shaped, and several series in one
file already work without it, since ``SpikeGLXConverterPipe`` instantiates one interface per stream and
each writes its own entry.


One ``ElectricalSeries`` per interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A recording interface writes exactly one ``ElectricalSeries``, the entry its ``metadata_key`` names. To
produce several in one file, create several interfaces, as ``SpikeGLXConverterPipe`` does, or call
``add_recording_to_nwbfile`` several times with different keys.

A single interface producing several series from one recording, with a channel selection per series,
is not supported and would need its own design.


The outer key is ``ElectricalSeries``, not a name from ``ndx-extracellular-channels``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The block is keyed by the NWB core class name. The ophys pipeline borrows ``MicroscopySeries`` from
``ndx-microscopy`` because that extension is an accepted proposal with a path to core.
``ndx-extracellular-channels`` does not have that status yet, so borrowing its vocabulary would cost
familiarity without the forward-compatibility payoff. ``ElectricalSeries`` is the object users already
write and covers every ecephys use case NeuroConv produces.


The electrodes table has its own key beside ``Electrodes``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The stated table lives at ``Ecephys.ElectrodesTable`` and ``Ecephys.Electrodes`` keeps its old meaning,
the list of column descriptions annotating a derived table. The alternative, built first, was to claim
``Electrodes`` for both and route on shape, a list being descriptions and a mapping being rows.

That was reversed because a wrong shape became a different feature instead of an error: a list written
where rows were meant was silently read as descriptions, ``dict_deep_update`` warned on the documented
converter path, and the schema could not express the union. Under separate keys the schema refuses the
wrong shape. The name is pynwb's own class name and matches ``nwbfile.electrodes``, and the inner keys
are lowercase ``rows`` and ``columns`` because in this format CamelCase keys are blocks and lowercase keys
are fields of one.


The stated table is an overlay on the recording, not a replacement for it
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The table is derived from the recording on every path. When a registry is supplied, the saved
``channel_to_electrode`` mapping addresses each source row to its annotation row before applying
user-stated fields. Source geometry and contact identity therefore reach custom row keys too, rather
than being discarded because the generated key differs. Explicit nulls still mean null; deleting a
field requests inheritance from the source.

This separates three things: a metadata row handle, the channel's association to it, and the physical
contact identity. Attaching a probe can enrich an existing row without renaming its handle or losing
its anatomical annotations. The mapping lives in serializable metadata, not hidden interface state,
so saving the annotations and using a new interface instance preserves the association.

The rejected alternative was to recompute an implicit mapping from ``{group}_{contact}`` or
``{group}_{channel}`` at write time even when the user had supplied annotation rows. Probe attachment
could change both parts, leaving the annotated rows unreferenced and generating additional electrodes.
A configuration-order warning would not prevent that silent error. Declared registries now require an
explicit association; wholly derived conversions retain their automatic behavior.

The mapping is not permission to overwrite a conflicting known physical identity. Such conflicts
raise and require the user to reconcile wiring or annotations. This also does not retroactively update
an already written NWB file: enrichment applies while constructing the file from the supplied metadata.


A row is a contact where the format names one, a channel otherwise
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A row's identity in the file is ``(group_name, electrode_name)`` where the recording carries contact
identifiers, and ``(group_name, channel_name)`` where it does not, and the row keys the template derives
follow the same rule: ``{group}_{contact}`` or ``{group}_{channel}``. Two channels that recorded one
contact reach one row. The alternative was the previous triple ``{group}_{electrode}_{channel}``, which
put every channel on its own row.

The triple was replaced because it forced a fabrication. The AP and LF bands of a Neuropixels probe are
the same contacts read through two channels, and the only way to share rows under the triple was for
``SpikeGLXRecordingInterface`` to write a joined ``AP0,LF0`` into both recordings' ``channel_name`` so the
identities collided. That put a name in the file that was no channel's own and fired for an AP-only
conversion. `#2001 <https://github.com/catalystneuro/neuroconv/pull/2001>`_ removed it. The group
qualifies the key because contact ids are unique per probe and not per recording: two probes in one
SpikeGLX session were measured sharing 70 contact ids.

What this obliges of a new interface. ``channel_name`` is the recording's own label and a row cannot
state it. If the format supplies contact ids, two streams over the same contacts share rows with nothing
else to do. If it does not, the channel name is the identity, so it must not change between streams of
one recording, and a row shared by two bands keeps whichever band's channel name reached it first.


Column declarations are central on the table, not inline per interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``columns`` sits on ``ElectrodesTable`` and describes the table as a whole, in the entry format the
events tables use, with ``column_name``, ``description``, ``dtype`` and ``column_categories``. The
alternative was the events layout, where each interface declares the columns it contributes.

Events needs per-contributor declarations because several interfaces pool rows into one table and each
brings its own label vocabulary. The electrodes table is one table described by whoever annotates it, so
a central block is what a user edits and what a converter merges. The cost is accepted and named: two
interfaces describing one column collide in ``dict_deep_update`` and the second wins silently. An
interface seeds descriptions through the ``Ecephys.Electrodes`` list and the template carries them into
``columns``, so stating the table does not lose a description the interface was supplying. ``dtype`` is
declared only for numeric and boolean kinds, since a numpy string dtype carries a width that would
truncate a value a user lengthened.


A group naming no device falls to the attached probe before the placeholder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Device resolution has three tiers: the group's ``device_metadata_key``, then the probe attached to the
recording, then ``PlaceholderElectrodeDevice``. The alternative was two tiers, key or placeholder.

The probe tier exists because a probe from ``probeinterface`` already carries the provenance the file
wants, a ``Device`` and a ``DeviceModel`` keyed by serial number, and writing a placeholder over it would
discard what the recording knows. It fires only for a single-probe recording, since a group cannot be
traced back to its probe otherwise. The obligation on a new interface is that if the format names its
hardware, emit it in ``get_metadata`` as a ``Devices`` entry and point the groups at it, which is what
``IntanRecordingInterface`` and ``SpikeGLXRecordingInterface`` do.
