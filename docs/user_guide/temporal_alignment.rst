Temporal Alignment
==================

Neurophysiology experiments often involve multiple acquisition systems that need to be synchronized post-hoc, so
synchronizing time streams across multiple interfaces is of critical importance when performing an NWB conversion. As
explained in the Best Practices (#TODO: add link), all timing information within an NWB file must be with respect to
the ``timestamps_reference_time`` of the file, which by default is the ``session_start_time``.

There are several ways to synchronize acquisition systems post-hoc. This tutorial will walk you through the 3 methods
implemented in NeuroConv. The API also allows you to define an entirely custom method for synchronization.

Note that NeuroConv does not resample the data, as this requires a resampling method that can change the values of
the underlying data. Rather, we aim to provide the timing of the samples in a common clock.


1. Synchronize Start Time
-------------------------
The simplest method of synchronization is to shift the start time of one acquisition system with respect to another. In
this approach, a secondary system sends a signal as it is starting, such as a TTL pulse, to a primary system,
indicating the temporal offset between the two systems. The following code will shift the timing of the DataInterface
of a secondary system according to this new starting time.

.. code-block:: python

    start_time_of_other_interface = 3.4  # in units seconds
    
    other_interface.synchronize_start_time(start_time=start_time_of_other_interface)

The advantage of this approach is its simplicity, but it cannot account for any drift due to misalignment between the
clocks of the two systems.

2. Synchronize Timestamps
-------------------------

Another method is to send a synchronization signals from a secondary system to a primary system on every sample.
This approach corrects for not only a difference in starting time, but also any drift that may have occurred due to
slight differences in the clock speeds of the two systems. Examples of this include sending TTL pulses from a camera
used to acquire optical imaging to a NIDQ board every time a frame is captured or every time a volume scan begins. You
can then align the timestamps of the secondary system by setting them to the pulse times as received by the primary
system, aligning the times to that system.

Once the `timestamps` are known they can be set in any DataInterface via

.. code-block:: python

    secondary_interface.synchronize_timestamps(timestamps=timestamps)

3. Synchronize Based on a Synchronization Signal
------------------------------------------------

Another common way of temporally aligning data between two systems is to send regular signals from secondary systems to
the primary system. Timestamps recorded by each secondary system must then be aligned using these synchronization
signals. Since not all timings are sent, an interpolation method must be used to synchronize each timestamp. The
NeuroConv default behavior for this approach is to linearly interpolate the timestamps given synchronization signal;
note the data values for the series itself is *not* changed during the process, only the timestamp values are
inferred for common reference time.

To use this type of synchronization, all the user must provide is the mapping determined by the 

.. code-block:: python

    regular_timestamps_as_seen_by_primary_system = ...
    regular_timestamps_as_seen_by_secondary_system = ...

    secondary_interface.synchronize_between_systems(
        unaligned_timestamps=regular_timestamps_as_seen_by_secondary_system,
        aligned_timestamps=regular_timestamps_as_seen_by_primary_system,
    )
    # All time reference in the secondary_interface have now been mapped from the secondary to the primary system


Tracking Timing Information: NIDQ
---------------------------------

The above sections do not describe how to track and store the timing information. One common approach is to utilize
electrophysiology boards due to their naturally high sampling frequency. With this approach, a channel can be setup
to receive a signal sent from a secondary system every time a certain event occurs. Those events could be mechanical
triggers, analog signals from environmental electrodes, digital codes, or simple TTLs (# TODO: link to examples of
these).

A common type of board used for this purpose is the NIDQ (#TODO: add link), which NeuroConv provides a special data
interface for. This interface comes equipped with the ability to compute the frame indices corresponding to pulses on
particular channels.

As an example demonstration of how to use this interface, let us assume the following experimental setup.

Primary system: NeuroPixels ecephys probe (SpikeGLX)
Secondary systems: SLEAP pose estimation (in `.slp` file format) of a mouse subject and event trigger times from when
the mouse performed a certain interation with a mechanical device (stored in a `.mat` file)




