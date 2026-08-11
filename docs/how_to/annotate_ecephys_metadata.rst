.. _annotate_ecephys_metadata:

How to Annotate Extracellular Electrophysiology Metadata
========================================================

Ecephys metadata describes the recording device, the electrode groups (the physical groupings of
channels such as shanks, tetrodes or arrays), and the ElectricalSeries that carries the traces.

Almost none of it comes from the source. NeuroConv reads only what the acquisition file records, and
most formats record no probe identity and no brain region at all, so a conversion you run without
adding metadata writes a placeholder device and a placeholder electrode group. Everything that says
what was implanted, and where, is provenance you supply.

The examples here use :py:class:`~neuroconv.tools.testing.mock_interfaces.MockRecordingInterface`,
which synthesizes traces instead of reading a file, so every snippet runs as written with no data to
download. Everything after the constructor is the same for any recording interface: swap in
``IntanRecordingInterface``, ``SpikeGLXRecordingInterface`` or any other, with the arguments its
format needs, and annotate the metadata exactly as shown.

What the interface gives you, and what you add
----------------------------------------------

A recording interface emits one ``ElectricalSeries`` entry, keyed by its ``metadata_key``, and
nothing else unless the format records something more:

.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface

    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key="m1_array")
    metadata = interface.get_metadata(use_new_metadata_format=True)
    metadata["Ecephys"]  # -> {'ElectricalSeries': {'m1_array': {'name': 'ElectricalSeries'}}}

There is no ``Devices`` block and no ``ElectrodeGroups`` block, because this recording claims no
device and no groups. Some formats do: ``IntanRecordingInterface`` names the Intan system it read,
``NeuralynxRecordingInterface`` reads the acquisition system out of the header, and
``SpikeGLXRecordingInterface`` names the probe. For the rest, you create both.

Annotate a single probe
-----------------------

The whole recording comes from one probe and forms one electrode group. Create the device under a
key of your choosing, create the group, and point the group at the device with
``device_metadata_key``:

.. code-block:: python

    from datetime import datetime

    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key="m1_array")
    metadata = interface.get_metadata(use_new_metadata_format=True)
    metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1, 12, 30, 0).astimezone()

    metadata["Devices"] = {
        "utah_array": {
            "name": "UtahArrayM1",
            "description": "96-channel Utah array implanted in primary motor cortex",
        },
    }

    metadata["Ecephys"]["ElectrodeGroups"] = {
        "m1": {
            "name": "ElectrodeGroup",
            "description": "Utah array electrodes",
            "location": "Primary motor cortex",
            "device_metadata_key": "utah_array",
        },
    }

    metadata["Ecephys"]["ElectricalSeries"]["m1_array"]["description"] = "Raw broadband traces."

    nwbfile = interface.create_nwbfile(metadata=metadata)
    nwbfile.electrode_groups["ElectrodeGroup"].device.name  # -> 'UtahArrayM1'

The keys (``"utah_array"``, ``"m1"``, ``"m1_array"``) are handles you choose and they are never
written to the file. The ``name`` fields are.

Annotate channels from several probes
-------------------------------------

One acquisition file often carries channels from more than one physical structure: an Intan
controller with two headstages, or a multi-shank probe. Each structure gets its own
``ElectrodeGroups`` entry, and channels are assigned to a group by the recording's ``group_name``
channel property.

**This is the one link that does not come from metadata.** A group's ``name`` has to match the
``group_name`` value on the channels that belong to it, or the writer creates a default group for
them instead. The property normally comes from the file, or from
:ref:`setting a probe <set_probe_on_recording_interfaces>`; here it is set by hand so the mapping is
visible:

.. code-block:: python

    interface = MockRecordingInterface(num_channels=4, durations=[0.1], metadata_key="two_shanks")
    interface.recording_extractor.set_property(key="group_name", values=["s1", "s1", "s2", "s2"])

    metadata = interface.get_metadata(use_new_metadata_format=True)
    metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1, 12, 30, 0).astimezone()

    metadata["Devices"] = {
        "a4x8_probe": {
            "name": "A4x8-5mm-50-200-177",
            "description": "NeuroNexus 4-shank silicon probe",
        },
    }

    metadata["Ecephys"]["ElectrodeGroups"] = {
        "shank_1": {
            "name": "s1",
            "description": "Shank 1, dorsal CA1",
            "location": "CA1",
            "device_metadata_key": "a4x8_probe",
        },
        "shank_2": {
            "name": "s2",
            "description": "Shank 2, dorsal CA1",
            "location": "CA1",
            "device_metadata_key": "a4x8_probe",
        },
    }

    nwbfile = interface.create_nwbfile(metadata=metadata)
    sorted(nwbfile.electrode_groups)  # -> ['s1', 's2']
    list(nwbfile.devices)  # -> ['A4x8-5mm-50-200-177']

Both groups name the same ``device_metadata_key``, so one device is written and both groups link to
it. That is how a multi-shank probe is represented: one physical substrate, several electrode
groups. Two headstages on separate probes would instead be two ``Devices`` entries, one per group.

A device nothing links to is not written
----------------------------------------

``metadata["Devices"]`` is a registry rather than a list of things to write. An entry is written only
when something references it, which is what lets a project-wide metadata file describe every device
in a lab while each conversion writes only the ones it used. A ``Devices`` entry that no electrode
group names is silently absent from the file, and a typo in ``device_metadata_key`` looks exactly
like that.

Two different things are called location
----------------------------------------

An electrode group's ``location`` is a field you set in the metadata, as above. The ``location``
column of the electrodes table is per channel and comes from the recording's ``brain_area``
property, not from the group. Setting the group's location does not populate the column:

.. code-block:: python

    sorted({str(location) for location in nwbfile.electrodes.to_dataframe()["location"]})  # -> ['unknown']

Set ``brain_area`` on the recording extractor the same way as ``group_name`` if you want per-channel
regions.

The manufacturer belongs on a device model
------------------------------------------

``Device.manufacturer`` is deprecated in pynwb: a manufacturer describes a product rather than the
individual unit, so it belongs on a ``DeviceModel`` that the device links to. Models live in their own
top-level registry, and a device points at one with ``device_model_metadata_key``, the same way an
electrode group points at its device:

.. code-block:: python

    metadata["DeviceModels"] = {
        "utah_array_model": {
            "name": "UtahArray96",
            "manufacturer": "Blackrock Neurotech",
            "description": "96-channel Utah array",
        },
    }

    metadata["Devices"] = {
        "utah_array": {
            "name": "UtahArrayM1",
            "description": "Implanted in primary motor cortex",
            "device_model_metadata_key": "utah_array_model",
        },
    }

    nwbfile = interface.create_nwbfile(metadata=metadata)
    nwbfile.devices["UtahArrayM1"].model.manufacturer  # -> 'Blackrock Neurotech'

The split is one model, many devices. Two probes of the same part number are two ``Devices`` entries
naming one ``DeviceModels`` entry, so what is true of the product is stated once and what is true of
the individual unit, the serial number or where it was implanted, stays on the device.

Where to go next
----------------

:ref:`ecephys_metadata_structure` is the full reference: every block, how the cross-references
resolve, and why ``ElectricalSeries`` carries no link to an electrode group.
:ref:`set_probe_on_recording_interfaces` covers attaching a probe, which sets the channel properties
these examples set by hand.
