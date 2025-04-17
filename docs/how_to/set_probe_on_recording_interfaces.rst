.. _set_probe_on_recording_interfaces:

Setting Probes on Recording Interfaces
======================================

This guide explains how to set probe information on NeuroConv recording interfaces, which allows
spatial information about electrode locations to be included in your NWB files.

Why Set Probe Information?
--------------------------

Probe information provides critical metadata about the spatial arrangement of electrodes,
which is essential for:

- Proper spike sorting
- Visualization of recording sites
- Analysis that depends on spatial relationships between electrodes
- Complete and reusable NWB files

Using ProbeInterface with NeuroConv
-----------------------------------

NeuroConv integrates with the ProbeInterface library to handle probe information.
All classes that inherit from ``BaseRecordingExtractorInterface`` have a ``set_probe()``
method that allows you to attach probe information to your recording.

.. warning::
   **Important:** Probes must be properly wired before setting them on a recording interface.
   Wiring connects the probe channels to the recording channels. Without proper wiring,
   the spatial information won't be correctly associated with your recording data.

   For details on how to wire probes, see the ProbeInterface documentation:
   https://probeinterface.readthedocs.io/en/main/examples/ex_11_automatic_wiring.html

Example Usage
-------------

Here's a basic example of how to set a probe on a recording interface:

.. code-block:: python

    import probeinterface
    from neuroconv.datainterfaces import IntanRecordingInterface

    # Create a recording interface
    recording_interface = IntanRecordingInterface(file_path="path/to/data.bin")

    # Create a probe from a manufacturer or create a custom probe, see probeinterface documentation
    probe = probeinterface.get_probe(manufacturer="neuronexus", probe_name="A1x32-Poly3")

    # Wire the probe (critical step!)
    # See ProbeInterface documentation for wiring details
    # The following part requires the probe to be wired

    # Set the probe on the recording interface
    recording_interface.set_probe(probe=probe)

    # Now the probe information will be included when you write to NWB
    recording_interface.add_to_nwbfile(nwbfile)

Group Mode Parameter
--------------------

When setting a probe, you can specify a ``group_mode`` parameter, which determines how channels
are grouped in the NWB file:

- ``"by_shank"``: Channels are grouped according to the shank they belong to
- ``"by_probe"``: All channels from the same probe are grouped together

Choose the mode that best represents your experimental setup:

.. code-block:: python

    # Group by shank (common for multi-shank probes)
    recording_interface.set_probe(probe=probe, group_mode="by_shank")

    # Or group by probe (when using multiple independent probes)
    recording_interface.set_probe(probe=probe, group_mode="by_probe")
