Temporal Alignment
==================

Neurophysiology experiments often involve multiple acquisition systems that need to be synchronized post-hoc, so
synchronizing time streams across multiple interfaces is of critical importance when performing an NWB conversion. As
explained in the Best Practices (#TODO: add link), all timing information within an NWB file must be with respect to
the ``timestamps_reference_time`` of the file, which by default is the ``session_start_time``.

Temporal Alignment Methods
--------------------------

There are several ways to synchronize acquisition systems post-hoc. This tutorial will walk you through the 3 methods
implemented in NeuroConv. The API also allows you to define an entirely custom method for synchronization.

Note that NeuroConv does not resample the data, as this requires a resampling method that can change the values of
the underlying data. Rather, we aim to provide the timing of the samples in a common clock.

The the code below, we demonstrate extracting times from TTL pulses sent to a SpikeGLX NIDQ channel.

1. Synchronize Start Time
~~~~~~~~~~~~~~~~~~~~~~~~~
The simplest method of synchronization is to shift the start time of one acquisition system with respect to another. In
this approach, a secondary system sends a signal as it is starting, such as a TTL pulse, to a primary system,
indicating the temporal offset between the two systems. To do this, use the DataInterface method
:py:meth:`~neuroconv.basetemporalalignmentinterface.BaseTemporalAlignmentInterface.set_aligned_starting_time`.
The advantage of this approach is its simplicity, but it cannot account for any drift due to misalignment between the
clocks of the two systems.

2. Synchronize Timestamps
~~~~~~~~~~~~~~~~~~~~~~~~~

Another method is to send a synchronization signals from a secondary system to a primary system on every sample.
This approach corrects for not only a difference in starting time, but also any drift that may have occurred due to
slight differences in the clock speeds of the two systems. Examples of this include sending TTL pulses from a camera
used to acquire optical imaging to a NIDQ board every time a frame is captured or every time a volume scan begins. You
can then align the timestamps of the secondary system by setting them to the pulse times as received by the primary
system, aligning the times to that system. Once the timestamps are known they can be set in any DataInterface via the
DataInterface method
:py:meth:`~neuroconv.basetemporalalignmentinterface.BaseTemporalAlignmentInterface.set_aligned_timestamps`.


3. Synchronize Based on a Synchronization Signal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Another common way of temporally aligning data between two systems is to send regular signals from secondary systems to
the primary system. Timestamps recorded by each secondary system must then be aligned using these synchronization
signals. Since not all timings are sent, an interpolation method must be used to synchronize each timestamp. The
NeuroConv default behavior for this approach is to linearly interpolate the timestamps given synchronization signal
via the DataInterface method
:py:meth:`~neuroconv.basetemporalalignmentinterface.BaseTemporalAlignmentInterface.align_by_interpolation`.
Note the data values for the series itself is *not* changed during the process, only the timestamp values are
inferred for common reference time.

To use this type of synchronization, all the user must provide is the mapping determined by the

.. code-block:: python

    regular_timestamps_as_seen_by_primary_system = ...
    regular_timestamps_as_seen_by_secondary_system = ...  # this is generally programmed explicitly, e.g. 1 per second.

    secondary_interface.align_by_interpolation(
        unaligned_timestamps=regular_timestamps_as_seen_by_secondary_system,
        aligned_timestamps=regular_timestamps_as_seen_by_primary_system,
    )
    # All time reference in the secondary_interface have now been mapped from the secondary to the primary system

Extracting synchronization signal
---------------------------------

Synchronization is often received achieved through sending synchronization singals from one acquisition system to
another. NeuroConv has some convenience methods for extracting times from TTL pulse signals. See the functions
:py:func:`~.tools.signal_processing.get_rising_frames_from_ttl` and
:py:func:`~.tools.signal_processing.get_falling_frames_from_ttl`. See also the convenience method
:py:meth:`~.datainterfaces.ecephys.spikeglx.spikeglxnidqinterface.SpikeGLXNIDQInterface.get_event_times_from_ttl`
of the
:py:class:`~.datainterfaces.ecephys.spikeglx.spikeglxnidqinterface.SpikeGLXNIDQInterface` class. Custom approach
will be required to use other types of synchronization signals.


Temporal Alignment within NWBConverter
--------------------------------------

To align data types within an :py:class:`.NWBConverter`, override the method
:py:meth:`.NWBConverter.temporally_align_data_interfaces`. For example, let's consider a system that has an audio
stream which sends a TTL pulse to a SpikeGLX system as it starts recording. This requires extracting the
synchronization TTL pulse times from the NIDQ interface, confirming that only one pulse was detected, and appluing
that as the start time of the audio stream.

.. code-block:: python

    from neuroconv import NWBConverter,
    from neuroconv.datainterfaces import (
        SpikeGLXRecordingInterface,
        AudioDataInterface,
        SpikeGLXNIDQRecordingInterface,
    )

    class ExampleNWBConverter(NWBConverter):
        data_interface_classes = dict(
            SpikeGLXRecording=SpikeGLXRecordingInterface,
            SpikeGLXNIDQ=SpikeGLXNIDQRecordingInterface,
            Audio=AudioDataInterface,
        )

        def temporally_align_data_interfaces():
            spikeglx_nidq_recording_interface = self.data_interface_objects["SpikeGLXNIDQ"]
            audio_interface = self.data_interface_objects["Audio"]
            ttl_times = spikeglx_nidq_recording_interface.get_event_times_from_ttl("channel-name")
            assert len(ttl_times) == 1, "more than one ttl pulse detected"
            audio_interface.set_aligned_starting_time(ttl_times[0])
