.. _annotate_ecephys_metadata:

How to Annotate Extracellular Electrophysiology Metadata
========================================================

This guide provides instructions for annotating extracellular electrophysiology (ecephys) data
using NeuroConv's dict-based metadata format.

.. note::

   This guide describes the **target** dict-based ecephys metadata API. The pipeline support and
   per-interface ``metadata_key`` arguments shown below land in subsequent PRs. Until then,
   ecephys conversions continue to use the existing list-based metadata format documented in
   :ref:`annotate_ecephys_data`. See :ref:`ecephys_metadata_structure` for the full reference.

Ecephys metadata in NWB files describes the recording device (probe), the electrode groups
(physical groupings of channels such as shanks or tetrodes), and the ElectricalSeries (the
acquired voltage traces). Per-channel properties (location, impedance, etc.) live on the
recording's channel properties and are written into the electrodes table at conversion time.

A single recording interface typically wraps one acquisition file or folder, and that file may
contain channels from one or several physical electrode structures. The dict-based metadata
format expresses each of those structures as one ``Devices`` entry plus one ``ElectrodeGroups``
entry, with the per-channel ``ElectricalSeries -> ElectrodeGroup`` link resolved at write time
from the recording's ``group`` channel property. The patterns below show how to set that up for
the most common acquisition setups.


How to Annotate a Single Probe (Blackrock)
------------------------------------------

In the simplest case the entire recording comes from a single probe and forms a single electrode
group. A typical Blackrock Cerebus session records one Utah array into one ``.nsX`` file, which
fits this shape exactly. Each recording interface accepts a ``metadata_key`` parameter that
organizes the related metadata components: the same key indexes the ElectricalSeries entry, and
the device and electrode group are reached through ``device_metadata_key`` references and the
recording's channel ``group`` property.

.. code-block:: python

    from neuroconv.datainterfaces import BlackrockRecordingInterface

    metadata_key = "m1_array"

    interface = BlackrockRecordingInterface(
        file_path="path/to/session.ns5",
        metadata_key=metadata_key,
    )

    metadata = interface.get_metadata()

    # The same metadata_key indexes the related components:
    # - metadata["Devices"][metadata_key] -> the recording device (probe)
    # - metadata["Ecephys"]["ElectrodeGroups"][metadata_key] -> the electrode group
    # - metadata["Ecephys"]["ElectricalSeries"][metadata_key] -> the electrical series

    device = metadata["Devices"][metadata_key]
    device["name"] = "UtahArrayM1"
    device["description"] = "96-channel Utah array implanted in primary motor cortex"
    device["manufacturer"] = "Blackrock Neurotech"

    electrode_group = metadata["Ecephys"]["ElectrodeGroups"][metadata_key]
    electrode_group["name"] = "ElectrodeGroup"
    electrode_group["description"] = "Utah array electrodes"
    electrode_group["location"] = "Primary motor cortex (M1)"

    electrical_series = metadata["Ecephys"]["ElectricalSeries"][metadata_key]
    electrical_series["name"] = "ElectricalSeries"
    electrical_series["description"] = "Raw broadband traces from Blackrock Cerebus"

    nwbfile = interface.create_nwbfile(metadata=metadata)


How to Annotate Channels from Multiple Probes (Intan)
-----------------------------------------------------

A single Intan recording controller often connects to several headstages, each attached to a
different probe. The amplifier channels in the resulting ``.rhd`` / ``.rhs`` file therefore come
from physically distinct probes, and each probe should appear as its own ``Devices`` entry and
its own ``ElectrodeGroups`` entry. Channels are mapped to the right group by setting the
recording's ``group`` channel property.

.. code-block:: python

    from neuroconv.datainterfaces import IntanRecordingInterface
    from neuroconv.tools import configure_and_write_nwbfile

    interface = IntanRecordingInterface(file_path="path/to/session.rhd")
    metadata = interface.get_metadata()

    # One Devices entry per physical probe
    metadata["Devices"]["v1_probe"] = {
        "name": "NeuropixelsV1",
        "description": "Neuropixels probe in V1, port A headstage",
        "manufacturer": "IMEC",
    }
    metadata["Devices"]["hpc_probe"] = {
        "name": "NeuropixelsHPC",
        "description": "Neuropixels probe in hippocampus, port B headstage",
        "manufacturer": "IMEC",
    }

    # One ElectrodeGroups entry per probe, each linked to its own device
    metadata["Ecephys"]["ElectrodeGroups"]["v1_probe"] = {
        "name": "ElectrodeGroupV1",
        "description": "Port A headstage probe",
        "location": "V1 binocular zone",
        "device_metadata_key": "v1_probe",
    }
    metadata["Ecephys"]["ElectrodeGroups"]["hpc_probe"] = {
        "name": "ElectrodeGroupHPC",
        "description": "Port B headstage probe",
        "location": "CA1 pyramidal layer",
        "device_metadata_key": "hpc_probe",
    }

    # Map channels to the probe they belong to. Intan groups channels by port
    # (port A is the first 64 amplifier channels, port B the next 64).
    # The string written here must match the "name" field of the corresponding
    # ElectrodeGroups entry above. See :ref:`no_electrode_group_metadata_key`
    # for why ElectricalSeries entries do not carry an electrode_group_metadata_key.
    recording = interface.recording_extractor
    channel_ids = list(recording.get_channel_ids())
    channel_id_to_group_name = {
        channel_id: ("ElectrodeGroupV1" if index < 64 else "ElectrodeGroupHPC")
        for index, channel_id in enumerate(channel_ids)
    }
    recording.set_property(
        key="group",
        values=list(channel_id_to_group_name.values()),
        ids=list(channel_id_to_group_name.keys()),
    )

    nwbfile = interface.create_nwbfile(metadata=metadata)
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path="annotated_session.nwb")


How to Annotate a Multi-Shank Probe (NeuroNexus A4x8)
-----------------------------------------------------

A multi-shank silicon probe is a single physical device with several spatially separated columns
of recording sites. The NeuroNexus ``A4x8-5mm-50-200-177`` (catalog name: 4 shanks of 8 sites,
5 mm shank length, 50 μm vertical site spacing, 200 μm shank spacing, 177 μm² site area) has
four shanks of eight sites each on a single substrate; one Intan headstage drives all 32
channels. The natural NWB shape is one ``Devices`` entry for the probe and one
``ElectrodeGroups`` entry per shank, with every shank referencing the same
``device_metadata_key``.

.. code-block:: python

    from neuroconv.datainterfaces import IntanRecordingInterface

    interface = IntanRecordingInterface(file_path="path/to/session.rhd")
    metadata = interface.get_metadata()

    # One Devices entry for the whole probe
    probe_key = "a4x8_probe"
    metadata["Devices"][probe_key] = {
        "name": "A4x8-5mm-50-200-177",
        "description": (
            "NeuroNexus A4x8-5mm-50-200-177 silicon probe: 4 shanks x 8 sites, 5 mm shank "
            "length, 50 um vertical site spacing, 200 um shank spacing, 177 um^2 site area"
        ),
        "manufacturer": "NeuroNexus",
    }

    # One ElectrodeGroups entry per shank, all pointing at the shared probe
    num_shanks = 4
    channels_per_shank = 8
    recording = interface.recording_extractor
    channel_ids = list(recording.get_channel_ids())

    channel_id_to_group_name = {}
    for shank_index in range(num_shanks):
        group_name = f"Shank{shank_index}"
        metadata["Ecephys"]["ElectrodeGroups"][f"shank_{shank_index}"] = {
            "name": group_name,
            "description": f"Shank {shank_index} of the A4x8 probe",
            "location": "CA1 pyramidal layer",
            "device_metadata_key": probe_key,
        }
        start = shank_index * channels_per_shank
        end = start + channels_per_shank
        for channel_id in channel_ids[start:end]:
            channel_id_to_group_name[channel_id] = group_name

    recording.set_property(
        key="group",
        values=list(channel_id_to_group_name.values()),
        ids=list(channel_id_to_group_name.keys()),
    )

    nwbfile = interface.create_nwbfile(metadata=metadata)

If different shanks target different brain areas (for example a probe straddling CA1 and DG),
give each ``ElectrodeGroups`` entry a distinct ``location`` value. Anatomy belongs on the group,
not on the device.

The exact probe geometry (site positions, shank spacing) belongs on the recording's probe object
rather than in the metadata dict. See :ref:`set_probe_on_recording_interfaces` for how to attach
a ``probeinterface`` probe (such as ``A4x8-5mm-50-200-177`` from the ``probeinterface_library``)
to the recording before conversion.

For per-channel fields such as brain area, impedance, or arbitrary user-defined columns, see
:ref:`annotate_ecephys_data`. Those properties are set on the recording extractor's channel
properties (not in the metadata dict) and are written into the NWB electrodes table at
conversion time.


.. note::

    If you have a use case not covered here, please open an issue at
    `NeuroConv GitHub Issues <https://github.com/catalystneuro/neuroconv/issues>`_.
