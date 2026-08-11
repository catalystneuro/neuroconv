.. _handle_heterogeneous_offsets:

Handling Channels with Heterogeneous Offsets
============================================

Writing a recording whose channels carry different offsets raises an error like this one:

.. code-block:: text

    The channels of this recording have heterogeneous offsets, which a single NWB
    ElectricalSeries cannot represent.
    Multiple offsets were found per channel IDs:
      Offset 0.0: Channel IDs ['Fp1', 'Fp2', 'C3', 'C4']
      Offset -1.5: Channel IDs ['OSAT', 'Pleth']

An ``ElectricalSeries`` stores a single scalar ``offset`` for the whole series, so there is nowhere
to put a per-channel offset. Per-channel *gains* are not a problem, they go into the optional
``channel_conversion`` array, which is why only offsets force a decision here.

There are two ways out and they are not interchangeable. Which one is right depends on why the
offsets differ, and the map printed in the error tells you: look at which channels carry the odd
offsets.

The offsets come from per-channel scaling
-----------------------------------------

Some formats let each channel declare its own physical range, and exporters that autoscale every
channel independently then produce a different gain and offset per channel. EDF is the common case,
since its per-channel physical and digital minimum and maximum are exactly this, and Micromed,
MNE's channelwise export and EEGLAB all write files this way.

You are in this case when the offsets are spread across channels that are all the same kind of
signal, for instance when a 64 channel electroencephalography montage comes back with a handful of
distinct offsets scattered over the electrodes. The offset groups carry no physical meaning: they
are an artifact of how the file was written, so splitting the electrodes along them would partition
the array on nothing, and dropping channels would throw away real electrodes.

Write the recording in physical units instead. This applies each channel's gain and offset to the
data and stores float physical values, so the series needs only a single scalar offset of zero:

.. code-block:: python

    from neuroconv.datainterfaces import EDFRecordingInterface

    interface = EDFRecordingInterface(file_path=file_path)

    metadata = interface.get_metadata()
    interface.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        data_representation="physical_units",
    )

``data_representation`` is a conversion option, so with a converter it is passed per interface:

.. code-block:: python

    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        conversion_options=dict(EDFRecordingInterface=dict(data_representation="physical_units")),
    )

Be aware of what this costs. The data is stored as floats rather than the original integers, which
roughly doubles the size on disk, and because the per-channel gains and offsets are folded into the
values and are no longer written to the file, the original digital counts cannot be recovered from
the NWB file afterwards.

The odd channels are not electrode channels
-------------------------------------------

Clinical recordings routinely carry auxiliary signals next to the electrodes: oxygen saturation,
pulse rate, plethysmography, respiration, trigger lines. These have their own physical ranges, so
they come with their own scaling, and the offset error is how you find out that they are in the
recording at all.

You are in this case when the odd offsets isolate a small set of channels whose names are not
electrode names. Here the offsets are a symptom rather than the problem. Those channels do not
belong in an ``ElectricalSeries``, which is meant for electrical recordings from electrodes, and
writing them in physical units would silence the error while producing a file that says oxygen
saturation was measured in volts at an electrode.

Drop them from the recording interface and write them as ``TimeSeries`` through the matching analog
interface:

.. code-block:: python

    from neuroconv import ConverterPipe
    from neuroconv.datainterfaces import EDFRecordingInterface, EDFAnalogInterface

    recording_interface = EDFRecordingInterface(file_path=file_path)
    recording_interface.remove_channels(channel_ids=["OSAT", "Pleth"])

    oxygen_interface = EDFAnalogInterface(
        file_path=file_path,
        channels_to_include=["OSAT"],
        metadata_key="time_series_oxygen",
    )

    converter = ConverterPipe(data_interfaces=[recording_interface, oxygen_interface])

A ``TimeSeries`` also holds a single unit for all of its channels, so auxiliary channels of
different units go one unit type per interface. Writing several unit types into one series makes
the physical values unrecoverable, and NeuroConv warns when that happens.

For interfaces that accept a channel selection at construction, such as
:py:class:`~neuroconv.datainterfaces.ecephys.edf.edfdatainterface.EDFRecordingInterface` with its
``channels_to_skip`` argument, you can exclude the auxiliary channels there instead of calling
``remove_channels`` afterwards. A complete example is in the
:doc:`../conversion_examples_gallery/recording/edf` gallery page, under "Combining Electrode and
Auxiliary Channels".
