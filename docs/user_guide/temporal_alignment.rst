Temporal Alignment
==================

Neurophysiology experiments often involve multiple acquisition systems that need to be synchronized post-hoc, so
synchronizing time streams across multiple interfaces is of critical importance when performing an NWB conversion. As
explained in the `Best Practices <https://nwbinspector.readthedocs.io/en/dev/best_practices/time_series.html#time-series-time-references/>`_, all timing information within an NWB file must be with respect to
the ``timestamps_reference_time`` of the file, which by default is the ``session_start_time``.



Interface Alignment Methods
---------------------------

There are several ways to synchronize acquisition systems post-hoc. This section will explain the core methods implemented in the :py:class:`~neuroconv.basetemporalalignmentinterface.BaseTemporalAlignmentInterface` NeuroConv, which is propagated to all format-specific interfaces supported by NeuroConv.

Aligning Start Times
~~~~~~~~~~~~~~~~~~~~

The simplest method of synchronization is to shift the start time of one acquisition system with respect to another. In this approach, a secondary system sends a signal as it is starting, such as a TTL pulse, to a primary system, indicating the temporal offset between the two systems.

The interface method we will use for this is :py:method:`~neuroconv.basetemporalalignmentinterface.BaseTemporalAlignmentInterface.set_aligned_starting_time`, which takes a single scalar argument ``starting_time`` to serve as this offset. This method will shift all timing information in the DataInterface of a secondary system by this new starting time.

The following code demonstrates this usage in a conversion involving two interfaces; InterfaceA and InterfaceB (TODO: use real interfaces in kind-of-realistic situation)

.. code-block:: python

    from neuroconv import ConverterPipe
    from neuroconv.datainterfaces import InterfaceB, InterfaceB
    
    # interface_b starts acquiring data exactly 3.2 seconds after interface_a
    interface_b = InterfaceB()
    
    interface_b.set_aligned_starting_time(starting_time=3.2)
    
    converter = ConverterPipe(...)
    converter.run_conversion()



Aligning Exact Timestamps
~~~~~~~~~~~~~~~~~~~~~~~~~

Another method is to send a synchronization signals from a secondary system to a primary system on every sample. This approach corrects for not only a difference in starting time, but also any drift that may have occurred due to slight differences in the clock speeds of the two systems. Examples of this include sending TTL pulses from a camera used to acquire optical imaging to a NIDQ board every time a frame is captured or every time a volume scan begins. You can then align the timestamps of the secondary system by setting them to the pulse times as received by the primary system, aligning the times to that system.

The interface method we will use for this is :py:method:`~neuroconv.basetemporalalignmentinterface.BaseTemporalAlignmentInterface.set_aligned_timestamps`, which takes a :py:class:`~numpy.ndarray` of ``aligned_timestamps``, which much match the total number of frames in the underlying data. This method will adjust the exact timing information in the DataInterface of a secondary system by these new values.

The following code demonstrates this usage in a conversion involving two interfaces; InterfaceA and InterfaceB (TODO: use real interfaces in kind-of-realistic situation)

.. code-block:: python

    from neuroconv import ConverterPipe
    from neuroconv.datainterfaces import InterfaceB, InterfaceB
    
    # interface_b starts acquiring data exactly 3.2 seconds after interface_a
    interface_b = InterfaceB()
    
    interface_b.set_aligned_starting_time(starting_time=3.2)
    
    converter = ConverterPipe(...)
    converter.run_conversion()



Aligning Between Multiple Signals
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Though not as common as the other approaches, one way of temporally aligning data across more than two systems is for tertiary systems to send timing signals to a common secondary system, and then to send timing information from that secondary system to the primary one. Since the primary system does not have direct access to the timing information from the tertiary systems, an interpolation method must be used to synchronize the timestamps. The NeuroConv default behavior for this approach is to linearly interpolate the timestamps given synchronization signal; note the data values for the series itself is *not* changed during the process, only the timestamp values are inferred for common reference time.

The interface method we will use for this is :py:method:`~neuroconv.basetemporalalignmentinterface.BaseTemporalAlignmentInterface.align_by_interpolation`, which takes two :py:class:`~numpy.ndarray`, one ``unaligned_timestamps`` from the tertiary system (in the time basis of the secondary system), and then the ``aligned_timestamps`` from the secondary system (in the time basis of the primary system). This method will adjust the exact timing information in the DataInterface of the tertiary system by these new values.

The following code demonstrates this usage in a conversion involving three interfaces; InterfaceA, InterfaceB, and InterfaceC (TODO: use real interfaces in kind-of-realistic situation)



Tracking Timing Information: NIDQ
---------------------------------

The above sections do not describe how to track and store the timing information. One common approach is to utilize
electrophysiology boards due to their naturally high sampling frequency. With this approach, a channel can be setup
to receive a signal sent from a secondary system every time a certain event occurs. Those events could be mechanical
triggers, analog signals from environmental electrodes, digital codes, or simple TTLs. (TODO: link/describe these in more detail)

A common type of board used for this purpose is the NIDQ (#TODO: add link), which NeuroConv provides a special data
interface for. This interface comes equipped with the ability to compute the frame indices corresponding to pulses on
particular channels.

As an example demonstration of how to use this interface, let us assume the following experimental setup.

Primary system: NeuroPixels ecephys probe (SpikeGLX)
Secondary systems: SLEAP pose estimation (in `.slp` file format) of a mouse subject and event trigger times from when
the mouse performed a certain interation with a mechanical device (stored in a `.mat` file)

.. code-block:: python

    from neuroconv import ConverterPipe
    from neuroconv.datainterfaces import InterfaceB, InterfaceB
    
    # interface_b starts acquiring data exactly 3.2 seconds after interface_a
    interface_b = InterfaceB()
    
    interface_b.set_aligned_starting_time(starting_time=3.2)
    
    converter = ConverterPipe(...)
    converter.run_conversion()



Temporal Alignment within NWBConverter
--------------------------------------

To align data types within an :py:class:`.NWBConverter`, override the method
:py:class:`.NWBConverter.temporally_align_data_interfaces`.

Let's consider a system that has an audio stream which sends a TTL pulse to a SpikeGLX system as it starts recording.

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
            ttl_times = self.data_interface_objects["SpikeGLXNIDQ"].get_event_times_from_ttl("channel-name")
            self.data_interface_objects["Audio"].set_aligned_starting_time(ttl_times[0])



Example Usage
-------------

Below are some full examples of how this feature can be used on some experimental patterns inspired by real data conversions.

