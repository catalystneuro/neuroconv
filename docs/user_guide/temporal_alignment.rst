Temporal Alignment
==================

Neurophysiology experiments combine several acquisition systems, and each system timestamps its data against its own
**clock**. A conversion has to bring all of them onto one shared clock, the NWB file's ``session_start_time``: every
time stored in the file is measured from it.

NeuroConv does not try to infer the correct timestamps on its own: how your systems were wired and synchronized is
rarely recorded in the files, so in general only you know it. When the source carries timing information the interface
pre-loads it, so you start from the times the acquisition system actually recorded. Those times are on that system's
clock, which need not coincide with the session clock. By default the interface writes them unchanged, which amounts to
assuming the two clocks coincide; when they do not, aligning is how you place the system's data on the session clock.
Aligning changes only when each sample occurred, never the samples themselves.

Time-bearing objects and the alignment API
------------------------------------------

Alignment acts on an interface's **time-bearing objects**: the neurodata types it writes that carry times relative to
``session_start_time``. Examples are the ``TwoPhotonSeries`` of an imaging interface, the ``ElectricalSeries`` of a
recording interface, each ``PoseEstimationSeries`` of a pose estimation interface, each ``EventsTable`` of an events
interface, with its times in the ``timestamp`` column, and a trials table, with its times in ``start_time``,
``stop_time`` and any other column whose name ends in ``_time``. By contrast, neurodata types such as a ``Device``, an
``ImagingPlane`` or the electrodes table are written by interfaces but carry no times, so they are not time-bearing
objects.

Every interface exposes its alignment methods under ``interface.alignment``, and each time-bearing object is reached
there by its name: ``imaging_interface.alignment["two_photon_series"]`` is the ``TwoPhotonSeries`` of an imaging
interface. ``get_times`` returns the times an object will write. Before you align anything, those are the times the
interface pre-loaded from the source:

.. code-block:: python

    imaging_interface.alignment["two_photon_series"].get_times()   # one time per sample, in seconds

Gross and fine alignment
------------------------

You might record a session as separate trials on the same rig, each file's clock starting near zero. Nothing about any
single trial is wrong; the trials just have to be laid out one after another on the session timeline, and sliding each
to the time it began does it, with nothing inside a trial touched. Or a behavior box that ran alongside the recording
may have started a few seconds later: a single trigger shared between the two tells you the gap, and because both ran
at the same rate, sliding the box's whole stream by that one number lines them up. Both are **gross alignment**: the
samples are already correctly spaced on a clock you trust, and only their placement as a whole is off, so a single
rigid shift fixes it.

.. image:: ../_static/images/time_alignment_concatenate.png
   :width: 600px
   :align: center
   :alt: Two panels. On the left, three trial files each start near zero, piled at the start of the axis. On the
         right, each trial is shifted to its own start so the three tile one after another along one session clock,
         the samples inside each trial untouched.

Now put a camera next to the electrophysiology. It keeps its own clock, and because the two clocks tick at slightly
different rates its frame times slide away from the recording, tens of milliseconds by the end of a long session, so
no single shift fixes both the first frame and the last. Two acquisition systems logging in parallel do the same, each
free-running on its own oscillator at a nominally identical rate: they drift apart as the session runs on. This is
**fine alignment**: the streams live on different clocks that drift, so the times themselves have to be rewritten,
usually by interpolating each stream onto the reference clock through synchronization pulses the systems share.

.. image:: ../_static/images/time_alignment_gross_vs_fine.png
   :width: 600px
   :align: center
   :alt: Two panels contrasting gross and fine alignment. On the left, a second stream sits at a constant offset from
         every recording instant, so one rigid shift lines it up. On the right, the gap to each recording instant
         grows across the session as the clocks drift, so no single shift works and the times must be rewritten.

An operational way to think about this is to ask whether one rigid shift could ever be right: it is gross alignment
if sliding the stream as a whole lines it up, and fine alignment if sliding makes the beginning line up but leaves
the end wrong, because the gap itself grows as the session runs on.

Aligning one object
-------------------

The examples in this section align one time-bearing object. We use the ``TwoPhotonSeries`` of an imaging interface
throughout, reached as ``imaging_interface.alignment["two_photon_series"]``. Interfaces that write several objects are
covered in `Interfaces with several objects`_.

Gross alignment
~~~~~~~~~~~~~~~

Gross alignment is the case where your data is already on the same clock and only its placement on that clock is wrong.
There are two operations for it, and which one you reach for depends on what you know:

* ``shift_times(delta)``, when you know how far the object is off. It moves the object by ``delta`` seconds from
  wherever it sits now.
* ``move_start_to(t)``, when you know where the object should begin. It moves the object so that its start sits at
  ``t`` seconds after ``session_start_time``.

Both are rigid moves: the spacing between samples, the gaps between events and all durations are preserved, and only
the object's position on the session clock changes. They differ when repeated: ``shift_times`` is relative, so repeated
calls add up, while ``move_start_to`` is absolute, so repeating it changes nothing.

.. image:: ../_static/images/time_alignment_coarse.png
   :width: 600px
   :align: center
   :alt: Three panels of one time-bearing object. As loaded; after shift_times(3.0), the object 3.0 seconds from
         where it was; after move_start_to(5.0), its start at 5.0 seconds from session start. In both moved panels
         the spacing between its samples is unchanged.

The canonical case for ``shift_times`` is a secondary system that sends a single pulse to the primary system as it
starts: that pulse tells you the offset, and one call moves the whole stream onto the shared clock:

.. code-block:: python

    imaging_interface.alignment["two_photon_series"].shift_times(3.0)   # every sample now sits 3.0 seconds later

When what you know is where the stream began rather than how far it is off, for instance that imaging started 4.2
seconds into the session, give that position to ``move_start_to``:

.. code-block:: python

    imaging_interface.alignment["two_photon_series"].move_start_to(4.2)   # the first sample now sits at 4.2 seconds

A series starts at its first sample, and an events table starts at its earliest event. A later ``shift_times`` moves
the object from that position.

.. _temporal_alignment_fine:

Fine alignment
~~~~~~~~~~~~~~

Fine alignment is the case where the clocks themselves disagree, so no single shift lines things up and the times have
to be rewritten. There are two ways to do it, and which you use depends on what you already have.

**Set the times directly.** When you already have the correct per-sample times, from a per-sample synchronization
signal or any computation you trust, hand them to ``set_times``:

.. code-block:: python

    imaging_interface.alignment["two_photon_series"].set_times(frame_times)

These are the times the file will carry: ``set_times`` writes them exactly as given. Call ``get_times`` afterwards
and you get back what you just set. The call replaces whatever the object had, including any earlier shift or
placement, while a shift or placement made afterwards moves the times you set.

**Re-time against a reference clock.** When you do not have the true times, you recover them by comparison with a clock
you trust, the reference clock.

A stream keeps its timestamps on its own clock. Beyond a constant offset, which a shift already handles, two clocks
can diverge in ways no shift can absorb: drifting at slightly different rates, or varying irregularly with no single
rate connecting them at all. When a constant shift cannot reconcile them, you map one clock onto the other point by
point.

That map comes from events the two clocks share, and two systems on different clocks have none, so you create some.
Feed one physical signal into both at once and each records the very same events on its own clock; in practice that
signal is a train of TTL (transistor-transistor logic) pulses, wired into both systems so every pulse is timestamped
twice. Each pulse is then a pair, its time on the reference clock and its time on the stream's clock, and the pairs pin
the two together. ``remap_times`` re-expresses the object's timestamps through those pairs, interpolating for the
samples that fall between pulses:

.. code-block:: python

    # The shared pulses, timestamped on each clock.
    pulses_local = ...       # on the timeline the object currently reports
    pulses_reference = ...   # the same pulses on the reference clock

    imaging_interface.alignment["two_photon_series"].remap_times(
        local_sync_times=pulses_local,
        reference_sync_times=pulses_reference,
    )

.. image:: ../_static/images/time_alignment_interpolation.png
   :width: 600px
   :align: center
   :alt: The same synchronization pulses, recorded on both a camera clock (local_sync_times) and the reference
         clock (reference_sync_times), pin one clock's times to the other's. Because the pulses are sparser than the
         camera's frames, a frame that falls between two pulses is placed on the reference clock by interpolating
         between the surrounding anchors.

``local_sync_times`` is on the timeline the object currently reports, so if you have already shifted it these have to
carry that shift too, while ``reference_sync_times`` is on the clock you are aligning to and cannot vary that way. The
two arrays pair up positionally, index by index, so a pulse that only one system recorded has to be dropped from the
other as well; equal lengths are not proof that the pairing is right.

The pulse times usually come from the TTL line each system recorded: :ref:`extract_events_from_signals` shows how to
read such a line into events, and ``get_event_times`` returns one event type's times.

Choosing how the map is built
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The map between the pulses is built with :func:`numpy.interp`, so a sample falling between two pulses is placed
proportionally between them, and samples outside the first and last pulse are clamped to the nearest reference time
rather than extrapolated. ``interpolation_function`` is how you change that, and there are two cases.

The first is when you want ``numpy.interp`` itself, with different arguments. Bind them with :func:`functools.partial`,
for instance to mark the samples outside the pulse range instead of clamping them:

.. code-block:: python

    from functools import partial

    imaging_interface.alignment["two_photon_series"].remap_times(
        local_sync_times=pulses_local,
        reference_sync_times=pulses_reference,
        interpolation_function=partial(np.interp, left=np.nan, right=np.nan),
    )

The second is when you want a different scheme altogether, a spline or a fit that extrapolates. Any callable will do,
as long as it takes the object's times and the two pulse arrays and returns the remapped times, which is
``numpy.interp``'s own signature:

.. code-block:: python

    from scipy.interpolate import interp1d

    def extrapolating(times, local_sync_times, reference_sync_times):
        return interp1d(local_sync_times, reference_sync_times, fill_value="extrapolate")(times)

    imaging_interface.alignment["two_photon_series"].remap_times(
        local_sync_times=pulses_local,
        reference_sync_times=pulses_reference,
        interpolation_function=extrapolating,
    )

None of this is a closed set. If the map you need is not expressible this way, compute the times you want by whatever
means you like and hand them to ``set_times``, which writes exactly what you give it.

Interfaces with several objects
-------------------------------

Many interfaces write more than one time-bearing object: a pose interface has one per keypoint, an events interface one
per event type, and a video or an audio interface one per file. Which objects an interface writes depends on the
interface. A few examples:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Interface
     - Time-bearing objects
   * - Recording
     - the ``ElectricalSeries``
   * - Events
     - each ``EventsTable``
   * - Pose estimation
     - each ``PoseEstimationSeries``
   * - External video
     - one object per video file, named after the file
   * - Audio
     - each ``AcousticWaveformSeries``, one per file
   * - Trials or epochs
     - the ``TimeIntervals`` table

``alignment`` exposes those objects as a mapping: its keys enumerate them, and indexing one reaches it, giving you that
object's times and the operations that rewrite them:

.. code-block:: python

    pose_interface.alignment.keys()                    # e.g. ("nose", "left_ear", "tail_base")

    pose_interface.alignment["nose"].get_times()
    pose_interface.alignment["nose"].set_times(times)
    pose_interface.alignment["nose"].remap_times(local_sync_times=pulses_local, reference_sync_times=pulses_reference)

``shift_times``, ``move_start_to`` and ``remap_times`` work at two scopes. Called on ``alignment[key]``, they act on
that one object. Called on ``alignment``, they act on every object of the interface: ``remap_times`` applies the same
map to all of them, and the other two move all of them by one common amount. For those two, what you want to move picks
the scope and the number you know picks the operation:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Scope
     - Shift by a correction
     - Move the start to a destination
   * - One object
     - ``alignment[key].shift_times(delta)``
     - ``alignment[key].move_start_to(t)``
   * - Whole interface
     - ``alignment.shift_times(delta)``
     - ``alignment.move_start_to(t)``

.. image:: ../_static/images/time_alignment_moves_together.png
   :width: 600px
   :align: center
   :alt: Three panels of one interface's three time-bearing objects. As loaded; after alignment.shift_times(3.0),
         every object 3.0 seconds from where it was; after alignment.move_start_to(5.0), the earliest start at
         5.0 seconds from session start. In both moved panels the gaps between the objects are unchanged.

``alignment.shift_times(delta)`` moves every object of the interface by ``delta``, so their relationships stay intact:
they slide together by the same amount. Use it when their relative timing is already correct and the whole group needs
the same correction:

.. code-block:: python

    events_interface.alignment.shift_times(3.0)   # every event now sits 3.0 seconds later on the session clock

A session recorded as separate trial files may have each file's clock starting near zero. When you know the time each
file began on the session clock, place each object with ``move_start_to``:

.. code-block:: python

    video_interface.alignment["trial_01"].move_start_to(0.0)
    video_interface.alignment["trial_02"].move_start_to(65.0)
    video_interface.alignment["trial_03"].move_start_to(130.0)

Each call places one file and leaves its siblings where they are. For video, :ref:`align_external_video` covers
placing the files of each camera setup, including one recording split into several files.

You can also move an entire interface to a known position:

.. code-block:: python

    video_interface.alignment.move_start_to(100.0)

The interface uses the earliest start among its objects and moves every object by the same amount. The three trials
placed above at 0, 65 and 130 seconds now start at 100, 165 and 230 seconds. Their relative timing stays intact.
Calling ``move_start_to(100.0)`` separately on each trial would instead put all three starts at 100 seconds.

A correction can also belong to one object. If a synchronization check finds one already-positioned trial video
40 milliseconds late, shift that video without moving its siblings:

.. code-block:: python

    video_interface.alignment["trial_02"].shift_times(-0.040)

An interface reads one source from one acquisition system, so its objects share a clock rather than merely happening to
agree, and a clock offset is corrected once, for all of them, with ``alignment.shift_times``. All of a pose interface's
keypoints come off the same video, and all of an events interface's tables off the same board. What can differ between
siblings is position, and only where the source does not record it: a camera or a microphone triggered once per trial
writes one file per trial, and nothing in those files says where each sits, so the interface names one object per file
and ``move_start_to`` places each. Where the source does record how its segments sit, as an electrophysiology recording
does, the interface names a single object and nothing has to be placed. An object whose samples themselves are wrong
against its siblings has a wrong array, which ``set_times`` replaces, and one that runs on a second clock wants a
second interface.

Alignment in a converter
------------------------

A converter is where alignment usually happens, since that is where several interfaces meet. A converter has an
``alignment`` of its own, and its keys nest: the first key is the name of an interface the converter holds, and
``converter.alignment[name]`` is that interface's ``alignment``. From there, indexing continues into the interface's
own objects as before:

.. code-block:: python

    converter.alignment.keys()               # e.g. ("Recording", "Behavior", "Video")
    converter.alignment["Video"].keys()      # e.g. ("trial_01", "trial_02", "trial_03")
    converter.alignment["Video"]["trial_02"].shift_times(-0.040)   # one file of the video interface

Called on the converter's ``alignment`` itself, ``shift_times`` and ``move_start_to`` move every interface it holds by
one common amount, just as an interface moves its objects, as long as each of them exposes an ``alignment``. Calling
``remap_times`` there applies one map to every interface, which is right only when all of them run on one clock. Each
interface usually has its own clock and its own correction, so most alignment is one call per interface.

With a ``ConverterPipe``
~~~~~~~~~~~~~~~~~~~~~~~~

A ``ConverterPipe`` joins interfaces you have already built. Pass them as a dictionary so that you choose their names;
given a list, the pipe names each interface after its class and numbers repeated classes. Align after building the pipe
and before running the conversion:

.. code-block:: python

    from neuroconv import ConverterPipe

    converter = ConverterPipe(data_interfaces=dict(Recording=recording_interface, Behavior=behavior_interface))

    behavior_delay = ...  # how far the behavior box starts after the recording, however you obtain it
    converter.alignment["Behavior"].shift_times(behavior_delay)

    converter.run_conversion(nwbfile_path="session.nwb")

With an ``NWBConverter``
~~~~~~~~~~~~~~~~~~~~~~~~

A subclass of :py:class:`.NWBConverter` packages a conversion you run repeatedly. Its interface names are the keys of
``data_interface_classes``, and the alignment goes in :py:meth:`.NWBConverter.temporally_align_data_interfaces`, which
``run_conversion`` calls before writing:

.. code-block:: python

    from neuroconv import NWBConverter

    class ExampleNWBConverter(NWBConverter):
        data_interface_classes = dict(
            Recording=SpikeGLXRecordingInterface,
            Behavior=TDTEventsInterface,
        )

        def temporally_align_data_interfaces(self, metadata=None, conversion_options=None):
            behavior_delay = ...  # how far the behavior box starts after the recording, however you obtain it
            self.alignment["Behavior"].shift_times(behavior_delay)

Inside this method you apply whatever each stream needs: ``shift_times`` for a correction, ``move_start_to`` for a
destination, or ``remap_times`` to re-time a drifting stream against the reference, on ``self.alignment[name]`` for a
whole interface or on ``self.alignment[name][key]`` for one of its objects.

One caveat applies to both: the calls mutate the live interfaces, so a step that runs twice compounds unless it states
a result. A ``shift_times`` shifts twice and a ``remap_times`` remaps times that were already remapped, while
``move_start_to`` and ``set_times`` can be repeated. Build the converter fresh per conversion.
