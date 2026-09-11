.. _annotate_ecephys_metadata:

How to Annotate Extracellular Electrophysiology Metadata
========================================================

Ecephys metadata describes the recording device, the electrode groups (the electrodes that are meant
to be analyzed together, typically a shank, a tetrode or a probe), and the ElectricalSeries that
carries the traces.

The metadata available from the source depends on the recording format. NeuroConv reads what the
acquisition file provides, but details such as probe identity and anatomical location may need to be
supplied separately. Where device or electrode group information is missing, NeuroConv uses placeholder
entries that you can annotate.

.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    interface = MockRecordingInterface(num_channels=4, durations=[0.1])
    nwbfile = interface.create_nwbfile()

.. admonition:: Resulting structure
   :class: tip

   .. code-block:: text

       acquisition
       └── ElectricalSeries  ──▶  electrodes rows 0-3

       electrodes
       id   location   group_name       channel_name
        0   unknown    ElectrodeGroup   0
        1   unknown    ElectrodeGroup   1
        2   unknown    ElectrodeGroup   2
        3   unknown    ElectrodeGroup   3

       ElectrodeGroup  ──▶  PlaceholderElectrodeDevice

To illustrate how to annotate your ecephys data, we use
:py:class:`~neuroconv.tools.testing.mock_interfaces.MockRecordingInterface`. You can follow along
with this mock interface or load your own data from any of our
:ref:`supported recording formats <conversion_gallery_ecephys_recording>` in the Conversion Gallery.

How to Annotate a Recording Session
-----------------------------------

We build one session in five steps, following the chain of references outward from the traces: the
series, the electrodes it points at, the columns you add of your own, the group those electrodes belong
to, and the device that group is part of. Each block shows the **whole script so far** with the new
lines highlighted, so the last one is the complete, runnable script.

**Name the series.** The ``ElectricalSeries`` is the object that holds the traces. Its name is how
someone opening the file tells one series from another, and its description is where you say what the
signal is, which nothing in the acquisition file records. Set both on the entry keyed by the
interface's ``metadata_key``:

.. code-block:: python
   :emphasize-lines: 1-10

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    metadata_key = "probe0"
    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key=metadata_key)

    metadata = interface.get_metadata()
    ecephys = metadata["Ecephys"]

    ecephys["ElectricalSeries"][metadata_key]["name"] = "ElectricalSeriesProbe0"
    ecephys["ElectricalSeries"][metadata_key]["description"] = "Raw broadband traces, 30 kHz."

.. admonition:: The file so far
   :class: note

   The series has its name, and the electrodes it points at are still the ones the recording derives.

   .. code-block:: text

       acquisition
       └── ElectricalSeriesProbe0  ──▶  electrodes rows 0-3

       electrodes
       id   group_name       channel_name
        0   ElectrodeGroup   0
        1   ElectrodeGroup   1
        2   ElectrodeGroup   2
        3   ElectrodeGroup   3

**Describe the electrodes.** Add an ``ElectrodesTable`` block to hold the annotations. Its ``rows``
dictionary has one entry per electrode, each pointing at its group with
``electrode_group_metadata_key``. We choose ``electrode_0`` through ``electrode_3`` as row keys;
they are handles for these annotations, not electrode group names. Since this example has one electrode
per recorded channel, we generate the rows in channel order and save the channel-to-row association
alongside them. Keep that mapping with the annotations: adding probe information later enriches the
same rows rather than changing which electrodes the annotations describe.

Create the rows, then add the values you know. Fields you omit keep the values the recording supplies.
The following properties are useful for downstream users, so fill them in if they are not available
in the source format:

``location``
    The brain region, as a name. Use a standard atlas region where there is one, following the
    `best practices for the electrode table
    <https://nwbinspector.readthedocs.io/en/dev/best_practices/ecephys.html#location>`_. If you omit it,
    the writer uses the recording's brain region, or ``"unknown"`` when the source provides none.

``x``, ``y``, ``z``
    Where the electrode sat **in the brain**, on the axes the NWB schema fixes: **+x is posterior, +y
    is inferior, +z is right**, in **microns**. This is **PIR** in the three-letter anatomical orientation
    notation: Posterior, Inferior, Right are the positive directions of x, y, and z, respectively.
    The origin is not fixed by the schema, so say what it
    is (bregma, typically) in the electrode group's description. Nothing in the recording knows these,
    since they depend on how the probe was implanted, so they are yours to supply. Where you need to
    state the reference frame explicitly, or give a position in a named atlas, `ndx-anatomical-localization
    <https://github.com/catalystneuro/ndx-anatomical-localization>`_ is the extension for it; these
    three columns carry a position and nothing about the space it is in.

``rel_x``, ``rel_y``, ``rel_z``
    Where the electrode sits **on the probe**, as a coordinate in the electrode group, also in
    microns. This is the probe's own geometry and does not change between sessions, which is why the
    next scenario gets it from the probe rather than by hand.

``imp`` and ``filtering`` are the other two columns the NWB schema defines, for the electrode's
impedance in ohms and a description of the hardware filtering. Add these fields where you have values
to supply. Optional columns absent from both the recording and your annotations are left out of the
file. Any other field you put on a row becomes a column of its own.

.. code-block:: python
   :emphasize-lines: 11-26

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    metadata_key = "probe0"
    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key=metadata_key)

    metadata = interface.get_metadata()
    ecephys = metadata["Ecephys"]

    ecephys["ElectricalSeries"][metadata_key]["name"] = "ElectricalSeriesProbe0"
    ecephys["ElectricalSeries"][metadata_key]["description"] = "Raw broadband traces, 30 kHz."
    # Microns from bregma, on the schema's axes: +x posterior, +y inferior, +z right.
    ecephys["ElectrodesTable"] = {
        "rows": {
            f"electrode_{channel_id}": {"electrode_group_metadata_key": "ElectrodeGroup"}
            for channel_id in interface.channel_ids
        },
        "columns": {},
    }
    rows = ecephys["ElectrodesTable"]["rows"]
    ecephys["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"] = dict(
        zip(interface.channel_ids, rows)
    )
    rows["electrode_0"].update(location="CA1", x=2000.0, y=2100.0, z=1500.0, imp=1.0e6)
    rows["electrode_1"].update(location="CA1", x=2000.0, y=2100.0, z=1500.0, imp=1.0e6)
    rows["electrode_2"].update(location="CA3", x=2000.0, y=2600.0, z=1500.0, imp=1.0e6)
    rows["electrode_3"].update(location="CA3", x=2000.0, y=2600.0, z=1500.0, imp=1.0e6)

.. admonition:: The file so far
   :class: note

   .. code-block:: text

       acquisition
       └── ElectricalSeriesProbe0  ──▶  electrodes rows 0-3

       electrodes
       id   location   x      y      z      imp
        0   CA1        2000   2100   1500   1e6
        1   CA1        2000   2100   1500   1e6
        2   CA3        2000   2600   1500   1e6
        3   CA3        2000   2600   1500   1e6

**Add your own columns.** The properties above are the ones the NWB schema names. Anything else you
know about the electrodes is worth recording too, and a reader can only use it if it says what it
means. Put the value on the rows and describe it under ``ElectrodesTable["columns"]``:

.. code-block:: python
   :emphasize-lines: 27-42

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    metadata_key = "probe0"
    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key=metadata_key)

    metadata = interface.get_metadata()
    ecephys = metadata["Ecephys"]

    ecephys["ElectricalSeries"][metadata_key]["name"] = "ElectricalSeriesProbe0"
    ecephys["ElectricalSeries"][metadata_key]["description"] = "Raw broadband traces, 30 kHz."
    # Microns from bregma, on the schema's axes: +x posterior, +y inferior, +z right.
    ecephys["ElectrodesTable"] = {
        "rows": {
            f"electrode_{channel_id}": {"electrode_group_metadata_key": "ElectrodeGroup"}
            for channel_id in interface.channel_ids
        },
        "columns": {},
    }
    rows = ecephys["ElectrodesTable"]["rows"]
    ecephys["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"] = dict(
        zip(interface.channel_ids, rows)
    )
    rows["electrode_0"].update(location="CA1", x=2000.0, y=2100.0, z=1500.0, imp=1.0e6)
    rows["electrode_1"].update(location="CA1", x=2000.0, y=2100.0, z=1500.0, imp=1.0e6)
    rows["electrode_2"].update(location="CA3", x=2000.0, y=2600.0, z=1500.0, imp=1.0e6)
    rows["electrode_3"].update(location="CA3", x=2000.0, y=2600.0, z=1500.0, imp=1.0e6)
    rows["electrode_0"]["side"] = 0
    rows["electrode_1"]["side"] = 1
    rows["electrode_2"]["side"] = 0
    rows["electrode_3"]["side"] = 1

    ecephys["ElectrodesTable"]["columns"]["side"] = {
        "column_name": "shank_side",
        "description": "Which face of the shank the contact sits on.",
        "column_categories": {
            "labels": {0: "front", 1: "back"},
            "meanings": {
                0: "contact on the front face",
                1: "contact on the back face",
            },
        },
    }

.. admonition:: The file so far
   :class: note

   The ``side`` field became the ``shank_side`` column, written as labels with a table of their meanings.

   .. code-block:: text

       acquisition
       └── ElectricalSeriesProbe0  ──▶  electrodes rows 0-3

       electrodes
       id   location   x      y      z      imp   shank_side
        0   CA1        2000   2100   1500   1e6   front
        1   CA1        2000   2100   1500   1e6   back
        2   CA3        2000   2600   1500   1e6   front
        3   CA3        2000   2600   1500   1e6   back

       shank_side_meanings
       front   contact on the front face
       back    contact on the back face

An entry is keyed by the field the rows use and can do four things:

``column_name``
    The header the column is written under. The rows say ``imp_measured`` and the file says
    ``impedance_at_1khz``, so you can rename a field without touching every row. Each field must have
    a distinct output name. The names ``id``, ``group``, ``group_name``, ``channel_name``,
    ``electrode_name``, and ``location`` are reserved and cannot be renamed or overwritten.

``description``
    What the column means. Without one it is written as ``"no description"``, which is the state most
    electrode columns are in across published files.

``dtype``
    What the values are written as. Worth stating for numbers, because a metadata file that has been
    through YAML or JSON comes back with plain Python ``int`` and ``float`` and loses what the source
    measured.

``column_categories``
    A vocabulary for a column whose values are codes. ``labels`` maps each raw value to what the cell
    says, and ``meanings`` maps it to a sentence; the pair is written as a ``MeaningsTable`` beside the
    column. Use it where the number is an arbitrary hardware encoding, and not where the number means
    something on its own, since the raw value is not recoverable afterwards.

**Name the electrode group.** Electrodes in the electrodes table are grouped together with the notion
of an ``ElectrodeGroup``: electrodes that are meant to be analyzed together, the canonical example
being the ones a sorting algorithm is run over. It is what tells someone reading the file which
electrodes were sorted as a unit and which sat on the same shank. Declare the group and point every row
at it with ``electrode_group_metadata_key``:

.. code-block:: python
   :emphasize-lines: 43-56

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    metadata_key = "probe0"
    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key=metadata_key)

    metadata = interface.get_metadata()
    ecephys = metadata["Ecephys"]

    ecephys["ElectricalSeries"][metadata_key]["name"] = "ElectricalSeriesProbe0"
    ecephys["ElectricalSeries"][metadata_key]["description"] = "Raw broadband traces, 30 kHz."
    # Microns from bregma, on the schema's axes: +x posterior, +y inferior, +z right.
    ecephys["ElectrodesTable"] = {
        "rows": {
            f"electrode_{channel_id}": {"electrode_group_metadata_key": "ElectrodeGroup"}
            for channel_id in interface.channel_ids
        },
        "columns": {},
    }
    rows = ecephys["ElectrodesTable"]["rows"]
    ecephys["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"] = dict(
        zip(interface.channel_ids, rows)
    )
    rows["electrode_0"].update(location="CA1", x=2000.0, y=2100.0, z=1500.0, imp=1.0e6)
    rows["electrode_1"].update(location="CA1", x=2000.0, y=2100.0, z=1500.0, imp=1.0e6)
    rows["electrode_2"].update(location="CA3", x=2000.0, y=2600.0, z=1500.0, imp=1.0e6)
    rows["electrode_3"].update(location="CA3", x=2000.0, y=2600.0, z=1500.0, imp=1.0e6)
    rows["electrode_0"]["side"] = 0
    rows["electrode_1"]["side"] = 1
    rows["electrode_2"]["side"] = 0
    rows["electrode_3"]["side"] = 1

    ecephys["ElectrodesTable"]["columns"]["side"] = {
        "column_name": "shank_side",
        "description": "Which face of the shank the contact sits on.",
        "column_categories": {
            "labels": {0: "front", 1: "back"},
            "meanings": {
                0: "contact on the front face",
                1: "contact on the back face",
            },
        },
    }
    group_key = "probe0_shank"
    device_key = "probe0_device"
    ecephys["ElectrodeGroups"] = {
        group_key: {
            "name": "ElectrodeGroupProbe0",
            "description": "Silicon probe electrodes, dorsal hippocampus penetration",
            "location": "Dorsal hippocampus",
            "device_metadata_key": device_key,
        },
    }
    rows["electrode_0"]["electrode_group_metadata_key"] = group_key
    rows["electrode_1"]["electrode_group_metadata_key"] = group_key
    rows["electrode_2"]["electrode_group_metadata_key"] = group_key
    rows["electrode_3"]["electrode_group_metadata_key"] = group_key

.. admonition:: The file so far
   :class: note

   Every row links to the group, which carries where the group as a whole sat.

   .. code-block:: text

       acquisition
       └── ElectricalSeriesProbe0  ──▶  electrodes rows 0-3

       electrodes
       id   location   x      y      z      imp   shank_side   group
        0   CA1        2000   2100   1500   1e6   front        ──▶  ElectrodeGroupProbe0
        1   CA1        2000   2100   1500   1e6   back         ──▶  ElectrodeGroupProbe0
        2   CA3        2000   2600   1500   1e6   front        ──▶  ElectrodeGroupProbe0
        3   CA3        2000   2600   1500   1e6   back         ──▶  ElectrodeGroupProbe0

       shank_side_meanings
       front   contact on the front face
       back    contact on the back face

       ElectrodeGroupProbe0 · Dorsal hippocampus

The group's ``location`` is where the group as a whole sat. The per-row ``location`` above is the
electrodes table's own column; setting one does not populate the other.

**Name the device and its model.** The device is the probe you implanted; the model is the
catalogue part it was ordered as. Together they tell someone reading the file exactly what recorded the
data, and the part number is what lets them look up the geometry rather than guess at it. Point the
group at a ``Devices`` entry, and that entry at a ``DeviceModels`` entry with
``device_model_metadata_key``; the manufacturer goes on the model, since ``Device.manufacturer`` is
deprecated in pynwb:

.. code-block:: python
   :emphasize-lines: 57-74

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    metadata_key = "probe0"
    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key=metadata_key)

    metadata = interface.get_metadata()
    ecephys = metadata["Ecephys"]

    ecephys["ElectricalSeries"][metadata_key]["name"] = "ElectricalSeriesProbe0"
    ecephys["ElectricalSeries"][metadata_key]["description"] = "Raw broadband traces, 30 kHz."
    # Microns from bregma, on the schema's axes: +x posterior, +y inferior, +z right.
    ecephys["ElectrodesTable"] = {
        "rows": {
            f"electrode_{channel_id}": {"electrode_group_metadata_key": "ElectrodeGroup"}
            for channel_id in interface.channel_ids
        },
        "columns": {},
    }
    rows = ecephys["ElectrodesTable"]["rows"]
    ecephys["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"] = dict(
        zip(interface.channel_ids, rows)
    )
    rows["electrode_0"].update(location="CA1", x=2000.0, y=2100.0, z=1500.0, imp=1.0e6)
    rows["electrode_1"].update(location="CA1", x=2000.0, y=2100.0, z=1500.0, imp=1.0e6)
    rows["electrode_2"].update(location="CA3", x=2000.0, y=2600.0, z=1500.0, imp=1.0e6)
    rows["electrode_3"].update(location="CA3", x=2000.0, y=2600.0, z=1500.0, imp=1.0e6)
    rows["electrode_0"]["side"] = 0
    rows["electrode_1"]["side"] = 1
    rows["electrode_2"]["side"] = 0
    rows["electrode_3"]["side"] = 1

    ecephys["ElectrodesTable"]["columns"]["side"] = {
        "column_name": "shank_side",
        "description": "Which face of the shank the contact sits on.",
        "column_categories": {
            "labels": {0: "front", 1: "back"},
            "meanings": {
                0: "contact on the front face",
                1: "contact on the back face",
            },
        },
    }
    group_key = "probe0_shank"
    device_key = "probe0_device"
    ecephys["ElectrodeGroups"] = {
        group_key: {
            "name": "ElectrodeGroupProbe0",
            "description": "Silicon probe electrodes, dorsal hippocampus penetration",
            "location": "Dorsal hippocampus",
            "device_metadata_key": device_key,
        },
    }
    rows["electrode_0"]["electrode_group_metadata_key"] = group_key
    rows["electrode_1"]["electrode_group_metadata_key"] = group_key
    rows["electrode_2"]["electrode_group_metadata_key"] = group_key
    rows["electrode_3"]["electrode_group_metadata_key"] = group_key
    device_model_key = "assy_156_p_1"
    metadata["Devices"] = {
        device_key: {
            "name": "ProbeDorsal",
            "description": "Implanted 2020-01-01, serial 1234",
            "device_model_metadata_key": device_model_key,
        },
    }

    metadata["DeviceModels"] = {
        device_model_key: {
            "name": "ASSY-156-P-1",
            "manufacturer": "Cambridge NeuroTech",
            "description": "64-channel silicon probe, P series",
        },
    }

    nwbfile = interface.create_nwbfile(metadata=metadata)

.. admonition:: The finished file
   :class: note

   .. code-block:: text

       acquisition
       └── ElectricalSeriesProbe0  ──▶  electrodes rows 0-3

       electrodes
       id   location   x      y      z      imp   shank_side   group
        0   CA1        2000   2100   1500   1e6   front        ──▶  ElectrodeGroupProbe0
        1   CA1        2000   2100   1500   1e6   back         ──▶  ElectrodeGroupProbe0
        2   CA3        2000   2600   1500   1e6   front        ──▶  ElectrodeGroupProbe0
        3   CA3        2000   2600   1500   1e6   back         ──▶  ElectrodeGroupProbe0

       shank_side_meanings
       front   contact on the front face
       back    contact on the back face

       ElectrodeGroupProbe0  ──▶  ProbeDorsal  ──▶  ASSY-156-P-1 (Cambridge NeuroTech)

The group-to-device and device-to-model links use the ``*_metadata_key`` fields you wrote.
Their displayed names come from the ``name`` fields. The keys
(``"probe0_device"``, ``"probe0"``, ``"assy_156_p_1"``) are handles that stay in your script.

.. _ecephys_probe_geometry:

.. _set_probe_on_recording_interfaces:

How to Add Probe Geometry
-------------------------

When the layout is missing and you know the probe model, you can
attach a catalogue probe instead of entering each contact's position yourself. The
`probeinterface library <https://spikeinterface.github.io/probeinterface_library/>`_ provides layouts
for supported models.

This example loads a catalogue layout and uses ``zip`` to pair the mock recording's channels with
the probe's contacts in list order. For your data, replace this example wiring with the actual
channel-to-contact connections. The contact positions describe the probe's geometry, not its
placement in the brain:

.. code-block:: python

    import probeinterface

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    interface = MockRecordingInterface(num_channels=32, durations=[0.1], metadata_key="probe0")

    probe = probeinterface.get_probe(manufacturer="neuronexus", probe_name="A1x32-Poly3-10mm-50-177")
    wiring = dict(zip(interface.channel_ids, probe.contact_ids))
    interface.set_probe(probe=probe, channel_id_to_contact_id=wiring)

    metadata = interface.get_metadata()
    nwbfile = interface.create_nwbfile(metadata=metadata)
    nwbfile.electrodes.to_dataframe()[["electrode_name", "rel_x", "rel_y"]].head()
    list(nwbfile.devices)

``channel_id_to_contact_id`` takes **channel ids as keys** and **probe contact ids as values**.
Contacts absent from the values are not recorded by this interface. This differs from
``channel_to_electrode``, whose values are electrode-row metadata keys (see
:ref:`ecephys_channel_to_electrode`). If you already wired the probe with
``probe.set_device_channel_indices``, omit ``channel_id_to_contact_id``.

Electrode groups follow the probe's organization automatically: one per probe, subdivided by shank
and then contact side when that information is present. No subdivisions are inferred from contact
positions. For grouping options, see :ref:`ecephys_electrode_grouping`.

Attaching the probe supplies three things when the file is written:

- ``rel_x`` and ``rel_y`` on every row, from the probe's contact positions.
- ``electrode_name`` on every row, from the probe's contact identifiers. This is what makes two
  channels that recorded one contact share a row rather than duplicating it.
- The device and its model, when the probe provides model information, linked to the electrode group.

What the probe cannot supply is where it was implanted. ``location``, and the ``x``, ``y`` and ``z``
stereotaxic coordinates, stay yours to state exactly as in the previous scenario.

.. _ecephys_electrode_grouping:

How to Assign Electrodes to Shanks or Tetrodes
----------------------------------------------

Use electrode groups to describe which electrodes belong to the same shank or tetrode.
First check whether the recording already carries the grouping you need. If it does, annotate those
groups rather than rebuilding their membership. Acquisition ports or headstage labels alone do not
establish which electrodes form a tetrode or belong to a shank; use your experimental arrangement.

Automatic grouping and overrides
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, ``set_probe`` uses SpikeInterface's ``group_mode="auto"``. Each probe gets its own group,
subdivided by ``shank_ids`` and then ``contact_sides`` when provided. For example, two probes with two
shanks each produce four groups; if each shank has recorded contacts on its front and back sides,
they produce eight. A probe without either subdivision produces one group. Positions alone do not
establish shanks or sides.

You can override this when your experiment calls for a different grouping:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - ``group_mode``
     - Electrode groups
   * - ``"auto"`` (default)
     - Each probe, subdivided by shank and contact side when present.
   * - ``"by_probe"``
     - One per probe, ignoring shanks and sides.
   * - ``"by_shank"``
     - One per shank within each probe, ignoring sides. Requires shank ids.
   * - ``"by_side"``
     - One per side within each probe and shank, if present. Requires contact sides.

For example, pass ``group_mode="by_probe"`` to keep all contacts of each probe together.
Attaching a probe replaces the recording's channel groups with this grouping. Explicit electrode-group
assignments in your electrode-row metadata still take precedence when writing NWB.

If a probe you are attaching already carries a per-contact grouping annotation, you can use it with
``group_property``, for example ``interface.set_probe(probe, group_property="tetrode")`` for an
already-wired probe with a ``tetrode`` annotation. This further subdivides the groups selected by
``group_mode``; identical labels on separate probes do not combine their contacts. To describe group
membership yourself, use electrode-row metadata as shown below.

Assigning groups in electrode-row metadata
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The mock recording below starts with one default group. We assign its four recorded electrodes to
two shanks on the same probe by changing each row's ``electrode_group_metadata_key``. For a tetrode,
the same field would assign its four electrodes to one group.

This approach does not require a ProbeInterface probe. Group membership and its annotations are
visible together in the electrode-row metadata.

.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key="two_shanks")
    metadata = interface.get_metadata()
    ecephys = metadata["Ecephys"]
    ecephys["ElectricalSeries"]["two_shanks"]["description"] = "Raw broadband traces, 30 kHz."

    metadata["Devices"] = {
        "a4x8_probe": {
            "name": "A4x8-5mm-50-200-177",
            "description": "NeuroNexus 4-shank silicon probe",
        },
    }

    ecephys["ElectrodeGroups"] = {
        "shank_1": {
            "name": "Shank1",
            "description": "Shank 1, dorsal CA1",
            "location": "CA1",
            "device_metadata_key": "a4x8_probe",
        },
        "shank_2": {
            "name": "Shank2",
            "description": "Shank 2, dorsal CA1",
            "location": "CA1",
            "device_metadata_key": "a4x8_probe",
        },
    }

    ecephys["ElectrodesTable"] = {
        "rows": {
            f"electrode_{channel_id}": {"electrode_group_metadata_key": "ElectrodeGroup"}
            for channel_id in interface.channel_ids
        },
        "columns": {},
    }
    rows = ecephys["ElectrodesTable"]["rows"]
    ecephys["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"] = dict(
        zip(interface.channel_ids, rows)
    )
    rows["electrode_0"].update(electrode_group_metadata_key="shank_1", location="CA1")
    rows["electrode_1"].update(electrode_group_metadata_key="shank_1", location="CA1")
    rows["electrode_2"].update(electrode_group_metadata_key="shank_2", location="CA1")
    rows["electrode_3"].update(electrode_group_metadata_key="shank_2", location="CA1")

    nwbfile = interface.create_nwbfile(metadata=metadata)
    sorted(nwbfile.electrode_groups)  # -> ['Shank1', 'Shank2']
    list(nwbfile.electrodes["group_name"][:])  # -> ['Shank1', 'Shank1', 'Shank2', 'Shank2']
    list(nwbfile.devices)  # -> ['A4x8-5mm-50-200-177']

Both groups name the same ``device_metadata_key``, so one device is written and both groups link to
it. This example describes recorded electrodes on two shanks of one probe. If the groups instead belong
to separate implanted probes, give each probe its own device, as in the next section.

How to Annotate Multiple Probes
-------------------------------

Use this section when a session includes distinct implanted probes that need their own identities
and descriptions. Keep any correct device identities and group links already supplied by the source;
add or update them where that information is missing. Each physical probe has its own ``Devices`` entry,
and every electrode group belonging to that probe points to it. A probe can have several groups.

The example below starts with a single mock recording containing channels from two probes, without
metadata identifying them. We describe one group per probe and assign the first two electrodes to the
left probe in CA1 and the other two to the right probe in CA3. This is different from assigning shanks
within one probe: the groups now point to distinct devices.

.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key="two_probes")
    metadata = interface.get_metadata()
    ecephys = metadata["Ecephys"]
    ecephys["ElectricalSeries"]["two_probes"]["description"] = "Raw broadband traces, 30 kHz."

    metadata["Devices"] = {
        "left_probe": {"name": "ProbeLeft", "description": "Serial 18194814172, left hemisphere"},
        "right_probe": {"name": "ProbeRight", "description": "Serial 18194814173, right hemisphere"},
    }

    ecephys["ElectrodeGroups"] = {
        "left": {
            "name": "ElectrodeGroupLeft",
            "description": "Left hemisphere penetration",
            "location": "CA1",
            "device_metadata_key": "left_probe",
        },
        "right": {
            "name": "ElectrodeGroupRight",
            "description": "Right hemisphere penetration",
            "location": "CA3",
            "device_metadata_key": "right_probe",
        },
    }

    ecephys["ElectrodesTable"] = {
        "rows": {
            f"electrode_{channel_id}": {"electrode_group_metadata_key": "ElectrodeGroup"}
            for channel_id in interface.channel_ids
        },
        "columns": {},
    }
    rows = ecephys["ElectrodesTable"]["rows"]
    ecephys["ElectricalSeries"][interface.metadata_key]["channel_to_electrode"] = dict(
        zip(interface.channel_ids, rows)
    )
    rows["electrode_0"].update(electrode_group_metadata_key="left", location="CA1")
    rows["electrode_1"].update(electrode_group_metadata_key="left", location="CA1")
    rows["electrode_2"].update(electrode_group_metadata_key="right", location="CA3")
    rows["electrode_3"].update(electrode_group_metadata_key="right", location="CA3")

    nwbfile = interface.create_nwbfile(metadata=metadata)
    sorted(nwbfile.devices)  # -> ['ProbeLeft', 'ProbeRight']
    list(nwbfile.electrodes["group_name"][:])
    # -> ['ElectrodeGroupLeft', 'ElectrodeGroupLeft', 'ElectrodeGroupRight', 'ElectrodeGroupRight']

The ``device_metadata_key`` on each group records which physical probe it belongs to. For multiple
multi-shank probes, define a device per probe and connect each shank's group to the appropriate device.
The number of groups does not determine the number of probes.

When different recording interfaces supply the probes' signals, their metadata must preserve those
distinct device identities and group links as well. Conversely, separate streams from one probe should
not create additional probe identities; :ref:`ecephys_channel_to_electrode` explains the related issue
of sharing electrode rows.


.. _ecephys_channel_to_electrode:

How to Map Recorded Channels to Electrodes
------------------------------------------

When the recorded channels already resolve to the intended electrode rows, no explicit mapping is
needed. The following cases explain when the electrode inventory and the recorded signals need to be
described separately.

Electrodes without recorded channels
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A probe can have electrodes that are not connected to any
of the channels in this recording. You can still describe those electrodes in
``ElectrodesTable["rows"]``. The series' ``channel_to_electrode`` mapping then identifies which
electrode supplied each recorded channel: its keys are **channel ids**, and its values are
**electrode row keys**.

For example, suppose a probe has four electrodes, listed in your metadata as ``electrode_0`` through
``electrode_3``, but only two recording channels. If channel 0 is connected to electrode 0 and channel 1
to electrode 2, the mapping is:

.. code-block:: python

    channel_to_electrode = {
        "0": "electrode_0",
        "1": "electrode_2",
    }

Supply this dictionary under
``metadata["Ecephys"]["ElectricalSeries"][metadata_key]["channel_to_electrode"]``. The resulting file has:

- Two columns of traces in the ``ElectricalSeries``, one per recorded channel.
- Four rows in the electrodes table: the two recorded electrodes first, followed by the unrecorded ones.
- An ``ElectricalSeries.electrodes`` reference connecting the first trace to electrode 0 and the second
  trace to electrode 2. The other two electrodes have metadata, but no traces in this series.

The electrode table describes the electrodes; the mapping describes their connections to the recorded
channels. Each recorded channel must map to an electrode, but not every electrode needs a recorded
channel. Each series saves its own ``channel_to_electrode`` mapping, connecting channel ids to keys
in the shared ``ElectrodesTable["rows"]`` dictionary. The writer translates these handles into numeric
row indices for ``ElectricalSeries.electrodes``. Channel ids are not channel names: a SpikeGLX channel
has id ``imec0.ap#AP0`` and name ``AP0``, while an Intan channel can have id ``A-000`` and name ``F1-01``.

The first walkthrough generated the mapping alongside its one-row-per-channel annotations. Here we
supply the connections explicitly because only two of the four electrodes were recorded:

.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    interface = MockRecordingInterface(num_channels=2, durations=[0.1], metadata_key="probe0")
    channel_ids = list(interface.channel_ids)

    metadata = interface.get_metadata()
    metadata["Ecephys"]["ElectrodeGroups"] = {
        "shank": {"name": "Shank1", "description": "One shank", "location": "CA1"},
    }
    metadata["Ecephys"]["ElectrodesTable"] = {
        "rows": {
            "CA1_e0": {"electrode_group_metadata_key": "shank", "location": "CA1"},
            "CA1_e1": {"electrode_group_metadata_key": "shank", "location": "CA1"},
            "CA1_e2": {"electrode_group_metadata_key": "shank", "location": "CA1"},
            "CA1_e3": {"electrode_group_metadata_key": "shank", "location": "CA1"},
        },
    }
    metadata["Ecephys"]["ElectricalSeries"]["probe0"]["channel_to_electrode"] = {
        channel_ids[0]: "CA1_e0",
        channel_ids[1]: "CA1_e2",
    }

    nwbfile = interface.create_nwbfile(metadata=metadata)
    assert len(nwbfile.electrodes) == 4
    assert list(nwbfile.acquisition["ElectricalSeries"].electrodes.data[:]) == [0, 1]
    assert list(nwbfile.electrodes["channel_name"][:]) == ["0", "1", "", ""]

A declared ``ElectrodesTable`` requires the saved mapping; omitting it raises rather than guessing from
row names. Every currently recorded channel must map to a declared row. Entries for channels removed
from the recording are allowed and are not used by that series. Rows unreferenced by the current
recording remain in the table. Without an ``ElectrodesTable`` block, conversion still derives the table
automatically and requires no user-supplied mapping.

Multiple channels from the same electrodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One electrode can supply a channel in more than one recording stream. For example, `Plexon OmniPlex
<https://plexon.com/plexon-systems/omniplex-neural-recording-system/>`_ can save wideband, continuous
spike-band and field-potential signals from the same neural input. `Neuralynx digital systems
<https://neuralynx.com/cheetah-ref-guide/HardwareSystems/HardwareSystemsOverview.html>`_ can send one
digitized input to multiple acquisition entities with different filtering and amplification settings.
These are multiple representations of the signal from one physical electrode, not additional electrodes.
Their corresponding channels should reference the same electrode row. These system capabilities do not
by themselves guarantee that a reader supplies the contact identity needed for automatic matching.

The following example supplies known contact identities to two mock interfaces and maps both streams
to one electrode registry. The second stream records the contacts in the opposite channel order. Its
traces are synthetic, not a filtered version of the first stream; this demonstrates the metadata
relationships, not Plexon or Neuralynx reader behavior.

.. code-block:: python

    from probeinterface import Probe

    from neuroconv import ConverterPipe
    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    raw_key = "raw"
    field_key = "field"
    group_key = "probe_group"
    device_key = "probe"
    raw = MockRecordingInterface(num_channels=2, durations=[0.1], metadata_key=raw_key)
    field = MockRecordingInterface(
        num_channels=2, sampling_frequency=1250.0, durations=[0.1], metadata_key=field_key
    )

    probe = Probe(ndim=2, si_units="um")
    probe.set_contacts(positions=[[0, 0], [0, 20]], shapes="circle", shape_params={"radius": 5})
    probe.set_contact_ids(["e0", "e1"])
    raw.set_probe(probe, channel_id_to_contact_id={"0": "e0", "1": "e1"})
    field.set_probe(probe, channel_id_to_contact_id={"0": "e1", "1": "e0"})

    converter = ConverterPipe(data_interfaces={"Raw": raw, "Field": field})
    metadata = converter.get_metadata()
    metadata["Devices"] = {device_key: {"name": "ProbeDorsal"}}
    ecephys = metadata["Ecephys"]
    ecephys["ElectrodeGroups"] = {
        group_key: {"name": "ProbeGroup", "location": "CA1", "device_metadata_key": device_key}
    }
    ecephys["ElectrodesTable"] = {
        "rows": {
            "electrode_a": {"electrode_group_metadata_key": group_key, "location": "CA1"},
            "electrode_b": {"electrode_group_metadata_key": group_key, "location": "CA3"},
        }
    }
    ecephys["ElectricalSeries"][raw_key].update(
        name="ElectricalSeriesRaw",
        description="Synthetic example of a wideband recording stream.",
        channel_to_electrode={"0": "electrode_a", "1": "electrode_b"},
    )
    ecephys["ElectricalSeries"][field_key].update(
        name="ElectricalSeriesField",
        description="Synthetic example of a field-potential recording stream.",
        channel_to_electrode={"0": "electrode_b", "1": "electrode_a"},
    )

    nwbfile = converter.create_nwbfile(metadata=metadata)
    assert len(nwbfile.electrodes) == 2
    assert list(nwbfile.electrodes["location"][:]) == ["CA1", "CA3"]
    assert list(nwbfile.electrodes["electrode_name"][:]) == ["e0", "e1"]
    assert list(nwbfile.acquisition["ElectricalSeriesRaw"].electrodes.data[:]) == [0, 1]
    assert list(nwbfile.acquisition["ElectricalSeriesField"].electrodes.data[:]) == [1, 0]

.. admonition:: Resulting structure
   :class: note

   .. code-block:: text

       acquisition
       ├── ElectricalSeriesRaw    ──▶  electrodes rows 0, 1
       └── ElectricalSeriesField  ──▶  electrodes rows 1, 0

       electrodes
       id   electrode_name   location
        0   e0               CA1
        1   e1               CA3

The saved mappings associate annotations with channels; the probe wiring supplies each channel's
contact identity and geometry. The writer brings that source information into the mapped rows, then
uses the common group and contact identities to find electrodes already written by the other stream.
No fabricated channel names or duplicate electrode rows are needed. Do not assign matching contact
identities merely to force sharing: the wiring must describe the actual physical connections.

.. _how_to_annotate_ecephys_from_a_template:

How to Annotate from a Template
-------------------------------

The examples above start from ``get_metadata()`` and build the annotations one block at a time,
so that each entry and reference is visible. Once you know the structure,
``get_metadata_template()`` assembles it for you: the electrode rows and groups are sized to your
recording, their references are connected, and values available from the source are prefilled.
Fields you can supply are marked with ``None`` where their values are missing.

Fill what applies and delete what does not. This example annotates the electrodes and their group,
names the probe, and removes the model entry because no model information is being supplied:

.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key="probe0")
    metadata = interface.get_metadata_template()
    ecephys = metadata["Ecephys"]

    ecephys["ElectricalSeries"]["probe0"]["description"] = "Raw broadband traces, 30 kHz."
    for row in ecephys["ElectrodesTable"]["rows"].values():
        row["location"] = "CA1"
    for group in ecephys["ElectrodeGroups"].values():
        group["description"] = "Silicon probe electrodes, dorsal hippocampus penetration"
        group["location"] = "CA1"

    device = metadata["Devices"]["probe"]
    device["name"] = "ProbeDorsal"
    device["description"] = "Implanted 2020-01-01"
    device["serial_number"] = "1234"
    del device["device_model_metadata_key"]
    del metadata["DeviceModels"]

    nwbfile = interface.create_nwbfile(metadata=metadata)

A required field left ``None`` fails validation or conversion. Optional electrode values such as
``imp`` and ``filtering`` can remain ``None`` and are omitted when no row supplies a value.
Deleting a row field lets the writer use the recording's value; for ``location``, it uses
``"unknown"`` if the source provides none. A custom column's blank description must be filled in or
deleted to use the description supplied by the recording.

Attaching the probe first lets the template prefill its geometry and contact identities. If you attach
it later, keep the saved mapping and remove blank row fields that should inherit the newly available
values. You can add rows for electrodes that are not
connected to this recording's channels; those rows do not need an entry in ``channel_to_electrode``.
The same structure is available as YAML and JSON at
:ref:`ecephys_metadata_template`.
