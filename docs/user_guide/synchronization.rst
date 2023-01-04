Synchronization
===============

Synchronizing time streams across multiple interfaces is of critical importance when performing an NWB conversion. As explained in the Best Practices (#TODO: add link), all timing information within an NWB file must be with respect to the `timestamps_reference_time` of the file, which by default is the `session_start_time`. It is also encouraged to set this reference time to be the earliest time that occurs in the file so that all synchronized values are strictly positive. This Best Practice is in place to counter drift (#TODO: demonstrate visual drift in unsyncrhonized file) which can occur over the course of an experiment due to the internal clocks of separate systems moving at slightly different rates.

NeuroConv offers several methods to synchronize timing information across data interfaces, and our API is also flexible enough to allow you to define an entirely custom method as well.

Below is a basic demonstration of the core API calls to synchronize timing information between interfaces assuming the timing information is already known. The later section deals with the more complicated approaches of how to actually track and compute the timing information itself for some example experimental setups.



Synchronize Start Time
----------------------

If the only information available within the source data for some interface is the time difference between when that stream began acquiring data relative to the chosen common time, then you can shift the time references of any interface in the following manner

.. code:
    start_time_of_common_system = 0
    start_time_of_other_interface = 3.4  # in units seconds
    
    other_interface.synchronize_start_time(start_time=start_time_of_other_interface)



Synchronize Timestamps
----------------------

The more preferred approach is to track the exact timing of events from secondary interfaces with respect to the common time. Examples of this include sending TTL pulses from a camera used to acquire optical imaging to a NIDQ board every time a frame is captured or a volume scan begins. We can then set these timestamps for the secondary interface as being the known pulse times as recieved by the common system so that we can be confident that refering to neural activity from the optical series at a particular point in time perfectly aligns to other data streams, such as behavioral times.

Once the `timestamps` are known they can be set in any data interface via

.. code:
    secondary_interface.synchronize_timestamps(timestamps=timestamps)




Synchronize Between Systems
---------------------------

Another common way of temporally aligning data between two systems is to send regular pulses from secondary systems to the primary system, and then record timing information for each data stream within the basis of its own system. The regular pulses then allow you to effectively reference a timestamp from a secondary and map it as closely as possible to the relative time within the primary system. The NeuroConv default behavior for this approach is to linearly interpolate the timestamps given this functional mapping; note the data values for the series itself is *not* changed during the process, only the timestamp values are inferred to be within the common reference time.

To use this type of synchronization, all the user must provide is the mapping determined by the 

.. code:
    regular_timestamps_as_seen_by_primary_system = ...
    regular_timestamps_as_seen_by_secondary_system = ...

    secondary_interface.syncrhonize_between_systems(
        primary_timestamps=regular_timestamps_as_seen_by_primary_system,
        secondary_timestamps=regular_timestamps_as_seen_by_secondary_system,
    )
    # All time reference in the secondary_interface have now been mapped from the secondary to the primary system



Tracking Timing Information: NIDQ
---------------------------------

The above sections do not go into great detail about how exactly to go about tracking and storing all the relative timing information. Different labs may have different approaches and some state-of-the-art acquisition systems will automatically synchronize between various data streams. One common approach is to utilize electrophysiology boards due to their naturally high sampling frequency. With this approach, the activity of a particular channel can be setup to recieve a signal sent from a secondary system every time a certain event occurs. Those events could be mechanical triggers, analog signals from environmental electrodes, digital codes, or simple TTLs (# TODO: link to examples of these).

A common type of board used for this purpose is the NIDQ (#TODO: add link), which NeuroConv provides a special data interface for. This interface comes equipped with the ability to compute the frame indices correpsonding to pulses on particular channels.

As an example demonstration of how to use this interface, let us assume the following experimental setup.

Primary system: NeuroPixels ecephys probe (SpikeGLX)
Secondary systems: SLEAP pose estimation (in `.slp` file format) of a mouse subject and event trigger times from when the mouse performed a certain interation with a mechanical device (stored in a `.mat` file)




