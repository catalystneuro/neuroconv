.. _annotate_ecephys_metadata:

How to Annotate Extracellular Electrophysiology Metadata
========================================================

Ecephys metadata describes the recording device, the electrode groups (the electrodes that are meant
to be analyzed together, typically a shank, a tetrode or a probe), and the ElectricalSeries that
carries the traces.

Almost none of it comes from the source. NeuroConv reads only what the acquisition file records, and
most formats record no probe identity and no brain region at all, so a conversion you run without
adding metadata writes a placeholder device and a placeholder electrode group. Everything that says
what was implanted, and where, is provenance you supply.

The examples here use :py:class:`~neuroconv.tools.testing.mock_interfaces.MockRecordingInterface`,
which synthesizes traces instead of reading a file, so every snippet runs as written with no data to
download. Everything after the constructor is the same for any recording interface: swap in
``IntanRecordingInterface``, ``SpikeGLXRecordingInterface`` or any other, with the arguments its
format needs, and annotate the metadata exactly as shown.

A recording interface emits one ``ElectricalSeries`` entry, keyed by its ``metadata_key``, and
nothing else unless the format records more. Some do: ``IntanRecordingInterface`` names the Intan
system it read, ``NeuralynxRecordingInterface`` reads the acquisition system out of the header, and
``SpikeGLXRecordingInterface`` names the probe. For the rest, the device and the electrode groups
are yours to create, which is what the first section below walks through in full. Every section
after it changes one link in that chain.

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
   :emphasize-lines: 12-13

    from datetime import datetime

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    metadata_key = "probe0"
    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key=metadata_key)

    metadata = interface.get_metadata_template()
    metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1, 12, 30, 0).astimezone()
    ecephys = metadata["Ecephys"]

    ecephys["ElectricalSeries"][metadata_key]["name"] = "ElectricalSeriesProbe0"
    ecephys["ElectricalSeries"][metadata_key]["description"] = "Raw broadband traces, 30 kHz."

**Describe the electrodes.** ``ecephys["ElectrodesTable"]["rows"]`` holds one entry per electrode, each
already pointing at its group with ``electrode_group_metadata_key``. The following properties are very
useful for downstream users, so fill them in if they are not available in the source format:

``location``
    The brain region, as a name. Use a standard atlas region where there is one, following the
    `best practices for the electrode table
    <https://nwbinspector.readthedocs.io/en/dev/best_practices/ecephys.html#location>`_. An electrode
    you say nothing about is written as ``"unknown"``.

``x``, ``y``, ``z``
    Where the electrode sat **in the brain**, on the axes the NWB schema fixes: **+x is posterior, +y
    is inferior, +z is right**, in **microns**. The origin is not fixed by the schema, so say what it
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
impedance in ohms and a description of the hardware filtering. Any other field you put on a row
becomes a column of its own.

.. code-block:: python
   :emphasize-lines: 14-21

    from datetime import datetime

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    metadata_key = "probe0"
    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key=metadata_key)

    metadata = interface.get_metadata_template()
    metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1, 12, 30, 0).astimezone()
    ecephys = metadata["Ecephys"]

    ecephys["ElectricalSeries"][metadata_key]["name"] = "ElectricalSeriesProbe0"
    ecephys["ElectricalSeries"][metadata_key]["description"] = "Raw broadband traces, 30 kHz."
    # Microns from bregma, on the schema's axes: +x posterior, +y inferior, +z right.
    regions = ["CA1", "CA1", "CA3", "CA3"]
    depths_in_um = [2100.0, 2100.0, 2600.0, 2600.0]
    rows = ecephys["ElectrodesTable"]["rows"]
    for entry, region, depth in zip(rows.values(), regions, depths_in_um):
        entry["location"] = region
        entry["x"], entry["y"], entry["z"] = 2000.0, depth, 1500.0
        entry["imp"] = 1.0e6

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
   :emphasize-lines: 22-35

    from datetime import datetime

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    metadata_key = "probe0"
    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key=metadata_key)

    metadata = interface.get_metadata_template()
    metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1, 12, 30, 0).astimezone()
    ecephys = metadata["Ecephys"]

    ecephys["ElectricalSeries"][metadata_key]["name"] = "ElectricalSeriesProbe0"
    ecephys["ElectricalSeries"][metadata_key]["description"] = "Raw broadband traces, 30 kHz."
    # Microns from bregma, on the schema's axes: +x posterior, +y inferior, +z right.
    regions = ["CA1", "CA1", "CA3", "CA3"]
    depths_in_um = [2100.0, 2100.0, 2600.0, 2600.0]
    rows = ecephys["ElectrodesTable"]["rows"]
    for entry, region, depth in zip(rows.values(), regions, depths_in_um):
        entry["location"] = region
        entry["x"], entry["y"], entry["z"] = 2000.0, depth, 1500.0
        entry["imp"] = 1.0e6
    for entry, side in zip(rows.values(), [0, 1, 0, 1]):
        entry["side"] = side

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

An entry is keyed by the field the rows use and can do four things:

``column_name``
    The header the column is written under. The rows say ``imp_measured`` and the file says
    ``impedance_at_1khz``, so you can rename a field without touching every row.

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
   :emphasize-lines: 36-46

    from datetime import datetime

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    metadata_key = "probe0"
    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key=metadata_key)

    metadata = interface.get_metadata_template()
    metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1, 12, 30, 0).astimezone()
    ecephys = metadata["Ecephys"]

    ecephys["ElectricalSeries"][metadata_key]["name"] = "ElectricalSeriesProbe0"
    ecephys["ElectricalSeries"][metadata_key]["description"] = "Raw broadband traces, 30 kHz."
    # Microns from bregma, on the schema's axes: +x posterior, +y inferior, +z right.
    regions = ["CA1", "CA1", "CA3", "CA3"]
    depths_in_um = [2100.0, 2100.0, 2600.0, 2600.0]
    rows = ecephys["ElectrodesTable"]["rows"]
    for entry, region, depth in zip(rows.values(), regions, depths_in_um):
        entry["location"] = region
        entry["x"], entry["y"], entry["z"] = 2000.0, depth, 1500.0
        entry["imp"] = 1.0e6
    for entry, side in zip(rows.values(), [0, 1, 0, 1]):
        entry["side"] = side

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
    ecephys["ElectrodeGroups"] = {
        group_key: {
            "name": "ElectrodeGroupProbe0",
            "description": "Silicon probe electrodes, dorsal hippocampus penetration",
            "location": "Dorsal hippocampus",
            "device_metadata_key": "probe0_device",
        },
    }
    for entry in rows.values():
        entry["electrode_group_metadata_key"] = group_key

The group's ``location`` is where the group as a whole sat. The per-row ``location`` above is the
electrodes table's own column; setting one does not populate the other.

**Name the device and its model, and write.** The device is the probe you implanted; the model is the
catalogue part it was ordered as. Together they tell someone reading the file exactly what recorded the
data, and the part number is what lets them look up the geometry rather than guess at it. Point the
group at a ``Devices`` entry, and that entry at a ``DeviceModels`` entry with
``device_model_metadata_key``; the manufacturer goes on the model, since ``Device.manufacturer`` is
deprecated in pynwb:

.. code-block:: python
   :emphasize-lines: 47-63

    from datetime import datetime

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    metadata_key = "probe0"
    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key=metadata_key)

    metadata = interface.get_metadata_template()
    metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1, 12, 30, 0).astimezone()
    ecephys = metadata["Ecephys"]

    ecephys["ElectricalSeries"][metadata_key]["name"] = "ElectricalSeriesProbe0"
    ecephys["ElectricalSeries"][metadata_key]["description"] = "Raw broadband traces, 30 kHz."
    # Microns from bregma, on the schema's axes: +x posterior, +y inferior, +z right.
    regions = ["CA1", "CA1", "CA3", "CA3"]
    depths_in_um = [2100.0, 2100.0, 2600.0, 2600.0]
    rows = ecephys["ElectrodesTable"]["rows"]
    for entry, region, depth in zip(rows.values(), regions, depths_in_um):
        entry["location"] = region
        entry["x"], entry["y"], entry["z"] = 2000.0, depth, 1500.0
        entry["imp"] = 1.0e6
    for entry, side in zip(rows.values(), [0, 1, 0, 1]):
        entry["side"] = side

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
    ecephys["ElectrodeGroups"] = {
        group_key: {
            "name": "ElectrodeGroupProbe0",
            "description": "Silicon probe electrodes, dorsal hippocampus penetration",
            "location": "Dorsal hippocampus",
            "device_metadata_key": "probe0_device",
        },
    }
    for entry in rows.values():
        entry["electrode_group_metadata_key"] = group_key
    metadata["Devices"] = {
        "probe0_device": {
            "name": "ProbeDorsalCA1",
            "description": "Implanted 2020-01-01, serial 1234",
            "device_model_metadata_key": "assy_156_p_1",
        },
    }

    metadata["DeviceModels"] = {
        "assy_156_p_1": {
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

       ElectrodeGroupProbe0  ──▶  ProbeDorsalCA1  ──▶  ASSY-156-P-1 (Cambridge NeuroTech)

Every arrow above is a ``*_metadata_key`` you wrote, and every name is a ``name`` field. The keys
(``"probe0_device"``, ``"probe0"``, ``"assy_156_p_1"``) are handles that stay in your script.

Two things follow from stating the table rather than deriving it. The rows are the table, so the
recording is no longer consulted for column values and a ``set_property`` call made after
``get_metadata_template`` has no effect; put the value in the row instead. And a row you declare is a
row you get, so select your channels before you call ``get_metadata_template``, or ``remove_channels``
afterwards leaves rows describing electrodes this session did not record from.

How to Set the Probe Geometry
-----------------------------

The probe's geometry is what lets a reader place the electrodes relative to each other, which is what
any analysis of distance, drift or spatial spread needs. The scenario above wrote it by hand; if you
know which probe recorded the data, attach it instead and the geometry comes from the probe. The
`probeinterface library <https://github.com/SpikeInterface/probeinterface_library>`_ carries the contact
geometry of published probes from most manufacturers, so a catalogue part is one ``get_probe`` call
away:

.. code-block:: python

    import probeinterface

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    interface = MockRecordingInterface(num_channels=32, durations=[0.1], metadata_key="probe0")

    probe = probeinterface.get_probe(manufacturer="neuronexus", probe_name="A1x32-Poly3-10mm-50-177")
    wiring = dict(zip(probe.contact_ids, interface.channel_ids))
    interface.set_probe(probe=probe, group_mode="by_probe", contact_id_to_channel_id=wiring)

    metadata = interface.get_metadata_template()
    list(metadata["Ecephys"]["ElectrodesTable"]["rows"])[:3]  # -> ['0_1', '0_2', '0_3']
    metadata["Ecephys"]["ElectrodesTable"]["rows"]["0_1"]
    # -> {'electrode_group_metadata_key': '0', 'electrode_name': '1',
    #     'rel_x': 0.0, 'rel_y': 450.0, 'location': 'unknown'}

The row keys changed too. Without a probe they are ``{group}_{channel}``, one per channel; with one
they are ``{group}_{contact}``, so a key names the physical contact rather than the path that recorded
it. That is the whole mechanism behind two channels sharing a row.

A catalogue probe describes a part rather than a wiring, so it arrives with no channel assignment and
cannot be attached until you say which channel recorded each contact. That is
``contact_id_to_channel_id``, keyed by contact id and valued by channel id, which is what a wiring table
gives you; a contact left out of it is one nothing recorded. ``group_mode`` decides whether the probe
becomes one electrode group or one per shank, which :ref:`set_probe_on_recording_interfaces` covers
along with building a probe from scratch.

Three things are filled in that you would otherwise write yourself:

- ``rel_x`` and ``rel_y`` on every row, from the probe's contact positions.
- ``electrode_name`` on every row, from the probe's contact identifiers. This is what makes two
  channels that recorded one contact share a row rather than duplicating it.
- The device, named after the probe rather than left as ``PlaceholderElectrodeDevice``.

What the probe cannot supply is where it was implanted. ``location``, and the ``x``, ``y`` and ``z``
stereotaxic coordinates, stay yours to state exactly as in the previous scenario.

How to Write Your Own Electrode Rows
------------------------------------

Every scenario above edited rows that came ready-made. If you would rather write them yourself,
under keys of your own choosing, one thing has to be said that those rows were saying for you: which
channel recorded which electrode. That is ``channel_to_electrode`` on the series entry, and it maps each
**channel id** to a row key. Channel ids are not channel names, and the two differ in most formats: a
SpikeGLX channel has id ``imec0.ap#AP0`` and name ``AP0``, an Intan channel has id ``A-000`` and name
``F1-01``.

.. code-block:: python

    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key="probe0")
    channel_ids = list(interface.channel_ids)

    metadata = interface.get_metadata()
    metadata["Ecephys"]["ElectrodeGroups"] = {
        "shank": {"name": "Shank1", "description": "One shank", "location": "CA1"},
    }
    metadata["Ecephys"]["ElectrodesTable"] = {
        "rows": {
            f"CA1_e{index}": {"electrode_group_metadata_key": "shank", "location": "CA1"}
            for index in range(4)
        },
    }
    metadata["Ecephys"]["ElectricalSeries"]["probe0"]["channel_to_electrode"] = {
        str(channel_id): f"CA1_e{index}" for index, channel_id in enumerate(channel_ids)
    }

    nwbfile = interface.create_nwbfile(metadata=metadata)
    list(nwbfile.electrodes["group_name"][:])  # -> ['Shank1', 'Shank1', 'Shank1', 'Shank1']

Leave out the mapping there and the conversion stops, naming the keys it derived and could not find, so
this is a mistake you are told about rather than one you discover in the file.

**You do not need it when you edit the rows above**, which is every scenario so far: the mapping
comes back alongside them, and the two already agree.

One thing it cannot do is make two recordings share electrodes when nothing in the file says they are
the same. Two bands of one probe share rows because both name the same contacts, not because of this
mapping. Where neither recording names a contact and their channel names differ, pointing both series
at one set of keys still writes two sets of rows, because the file has no contact identity to match
them on.

How to Annotate a Recording from a Multi-Shank Probe
----------------------------------------------------

One acquisition file often carries channels from more than one physical structure: an Intan controller
with two headstages, or a multi-shank probe. Each structure gets its own ``ElectrodeGroups`` entry, so
that a reader can tell which electrodes were sorted as a unit and which shared a shank.

Say which electrodes belong to which group the same way the first section did, by pointing each row at
its group. The recording's own ``group_name`` channel property is the other route, and a group's
``name`` then has to match it; that is what :ref:`setting a probe <set_probe_on_recording_interfaces>`
fills in.

.. code-block:: python

    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key="two_shanks")
    metadata = interface.get_metadata_template()
    metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1, 12, 30, 0).astimezone()
    ecephys = metadata["Ecephys"]

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

    rows = ecephys["ElectrodesTable"]["rows"]
    for index, entry in enumerate(rows.values()):
        entry["electrode_group_metadata_key"] = "shank_1" if index < 2 else "shank_2"

    nwbfile = interface.create_nwbfile(metadata=metadata)
    sorted(nwbfile.electrode_groups)  # -> ['Shank1', 'Shank2']
    list(nwbfile.electrodes["group_name"][:])  # -> ['Shank1', 'Shank1', 'Shank2', 'Shank2']
    list(nwbfile.devices)  # -> ['A4x8-5mm-50-200-177']

Both groups name the same ``device_metadata_key``, so one device is written and both groups link to
it. That is how a multi-shank probe is represented: one physical substrate, several electrode
groups. Two headstages on separate probes would instead be two ``Devices`` entries, one per group.

How to Annotate a Recording from Several Probes
-----------------------------------------------

Two probes in one recording are two ``Devices`` entries, one per electrode group, rather than one
device with two groups. The difference matters to a reader: it is what says whether two groups sat on
one piece of silicon or on two separately implanted probes.

.. code-block:: python

    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key="two_probes")
    metadata = interface.get_metadata_template()
    metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1, 12, 30, 0).astimezone()
    ecephys = metadata["Ecephys"]

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
            "location": "CA1",
            "device_metadata_key": "right_probe",
        },
    }

    rows = ecephys["ElectrodesTable"]["rows"]
    for index, entry in enumerate(rows.values()):
        entry["electrode_group_metadata_key"] = "left" if index < 2 else "right"

    nwbfile = interface.create_nwbfile(metadata=metadata)
    sorted(nwbfile.devices)  # -> ['ProbeLeft', 'ProbeRight']
    list(nwbfile.electrodes["group_name"][:])
    # -> ['ElectrodeGroupLeft', 'ElectrodeGroupLeft', 'ElectrodeGroupRight', 'ElectrodeGroupRight']

Whether two groups share a device or get one each is the whole difference between a multi-shank probe
and two probes, and it is stated in one place: the ``device_metadata_key`` each group names.
