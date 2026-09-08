Temporal Alignment
==================

Neurophysiology experiments combine several acquisition systems, and each system timestamps its data against its own
**clock**. A conversion has to bring all of them onto one shared clock, the NWB file's ``session_start_time``: every
time stored in the file is measured from it.

NeuroConv is deliberately agnostic about what the correct timestamps are; it does not try to infer them, because only
you know how your systems were wired and synchronized. When the source carries timing information the interface
pre-loads it, so you start from the times the acquisition system actually recorded. Those times are on that system's
clock, which need not coincide with the session clock. By default the interface writes them unchanged, which amounts
to assuming the two clocks coincide; when they do not, aligning is how you place the system's data on the session
clock. NeuroConv never resamples or changes the data values; it only sets the timing of the samples you already have.

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

Gross alignment
---------------

Gross alignment is the case where your data is already on one clock and only its placement is wrong. Every interface
exposes its alignment methods under ``interface.alignment``, and the whole-interface tool for gross alignment is
``shift_times``.

``alignment.shift_times(delta)`` moves **every time-bearing object in the interface**, every object it writes that
carries a time, by ``delta`` seconds. It
is a rigid translation: the spacing between samples, the gaps between events, and all durations are preserved,
only the position on the shared clock changes. It is relative, so repeated calls accumulate.

.. code-block:: python

    events_interface.alignment.shift_times(3.0)   # every event now sits 3.0 seconds later on the session clock

One canonical case is a secondary system that sends a single pulse to the primary system as it starts: that pulse
tells you the offset, and one call moves the whole stream onto the shared clock. Another is a session recorded as
separate trial files, each clock starting near zero, where one shift per trial lays them out along the session clock
with nothing inside a trial touched.

.. image:: ../_static/images/time_alignment_coarse.png
   :alt: A stream slides as a rigid block onto the recording clock, its sample spacing intact.
   :width: 600px
   :align: center

Because the move is rigid, all the objects in the interface keep their relationships exactly: they slide together by
the same amount. ``alignment.shift_times`` moves the whole set at once, which is what keeps their relative timing
intact: those objects came off one acquisition system, so their timing relative to one another is already correct. The
same holds one level up: a converter can shift everything it holds at once, moving all of its interfaces together by
one amount, as long as each of them exposes an ``alignment``.

.. image:: ../_static/images/time_alignment_moves_together.png
   :alt: An interface's time-bearing objects all shift together by the same amount; the gaps between them never change.
   :width: 600px
   :align: center

Fine alignment
--------------

Fine alignment is the case where the clocks themselves disagree, so no single shift lines things up and the times have
to be rewritten. There are two ways to do it, and which you use depends on what you already have.

**Set the times directly.** When you already have the correct per-sample times, from a per-sample synchronization
signal or any computation you trust, hand them to ``set_times`` on the object they belong to. Times are per-object, so
this call always names one, even where the interface writes only that one; the next section covers how to find the key:

.. code-block:: python

    imaging_interface.alignment["two_photon_series"].set_times(frame_times)

These are the times the file will carry: ``set_times`` writes them exactly as given. Call ``get_times`` afterwards
and you get back what you just set.

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
    pulses_local = ...       # on the timeline the interface currently reports
    pulses_reference = ...   # the same pulses on the reference clock

    imaging_interface.alignment.remap_times(
        local_sync_times=pulses_local,
        reference_sync_times=pulses_reference,
    )

.. image:: ../_static/images/time_alignment_interpolation.png
   :width: 600px
   :align: center
   :alt: The same synchronization pulses, recorded on both a camera clock and the reference clock, pin one clock's
         times to the other's. Because the pulses are sparser than the camera's frames, a frame that falls between
         two pulses is placed on the reference clock by interpolating between the surrounding anchors.

``local_sync_times`` is on the timeline the interface currently reports, so if you have already shifted it these have
to carry that shift too, while ``reference_sync_times`` is on the clock you are aligning to and cannot vary that way.
The two arrays pair up positionally, index by index, so a pulse that only one system recorded has to be dropped from
the other as well; equal lengths are not proof that the pairing is right.

Choosing how the map is built
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The map between the pulses is built with :func:`numpy.interp`, so a sample falling between two pulses is placed
proportionally between them, and samples outside the first and last pulse are clamped to the nearest reference time
rather than extrapolated. ``interpolation_function`` is how you change that, and there are two cases.

The first is when you want ``numpy.interp`` itself, with different arguments. Bind them with :func:`functools.partial`,
for instance to mark the samples outside the pulse range instead of clamping them:

.. code-block:: python

    from functools import partial

    imaging_interface.alignment.remap_times(
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

    imaging_interface.alignment.remap_times(
        local_sync_times=pulses_local,
        reference_sync_times=pulses_reference,
        interpolation_function=extrapolating,
    )

None of this is a closed set. If the map you need is not expressible this way, compute the times you want by whatever
means you like and hand them to ``set_times``, which writes exactly what you give it.

Multiple time-bearing objects
-----------------------------

Some interfaces carry only a single object to place in time, a ``TwoPhotonSeries`` in an imaging interface, for
instance, and the calls in the previous section act on it directly. Others carry several: a pose interface has one
object per keypoint, an events interface one per event type, and a converter gathers the objects of every interface it
holds. When there is more than one, you name which you mean.

Alignment acts on an interface's time-bearing objects: the parts of its data that carry their own times relative
to ``session_start_time``. Which parts those are depends on the interface. A few examples:

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
   * - Trials or epochs
     - the ``TimeIntervals`` table

In a generic ``DynamicTable`` (trials, epochs, or one of your own) the time-bearing values are the columns whose names
end in ``_time``, an NWB convention the `NWB Inspector checks
<https://nwbinspector.readthedocs.io/en/dev/best_practices/tables.html#timing-columns>`_. Structural and metadata
objects (a ``Device``, an ``electrodes`` table) carry no time and are left untouched.

``alignment`` exposes those objects as a mapping: its keys enumerate them, and indexing one reaches it, giving you that
object's times and the operations that rewrite them:

.. code-block:: python

    pose_interface.alignment.keys()                    # e.g. ("nose", "left_ear", "tail_base")

    pose_interface.alignment["nose"].get_times()
    pose_interface.alignment["nose"].set_times(times)
    pose_interface.alignment["nose"].remap_times(local_sync_times=pulses_local, reference_sync_times=pulses_reference)

What you call an operation on is what it applies to. ``shift_times`` places the whole interface, so it moves every
object and takes no key at all. ``remap_times`` is one clock's correction, so it is available at either scope: on the
interface it applies the same map to every object. Times themselves belong to one object, so ``set_times`` and
``get_times`` are only ever reached through the object.

There is no per-object shift, and none is needed: an interface reads one source from one acquisition system, so its
objects share a clock rather than merely happening to agree. All of a pose interface's keypoints come off the same
video, and all of an events interface's tables off the same board. An object that is genuinely misplaced against its
siblings has a wrong array, which ``set_times`` replaces, and one that runs on a second clock wants a second interface.

Alignment in a converter
------------------------

A converter is where alignment usually happens, since that is where several interfaces meet. Override
:py:meth:`.NWBConverter.temporally_align_data_interfaces` and place each stream on the shared clock:

.. code-block:: python

    from neuroconv import NWBConverter

    class ExampleNWBConverter(NWBConverter):
        data_interface_classes = dict(
            Recording=SpikeGLXRecordingInterface,
            Behavior=TDTEventsInterface,
        )

        def temporally_align_data_interfaces(self, metadata=None, conversion_options=None):
            behavior = self.data_interface_objects["Behavior"]
            behavior_offset = ...  # how far the behavior box starts after the recording, however you obtain it
            behavior.alignment.shift_times(behavior_offset)

Inside this method each interface exposes its full alignment surface under ``alignment``, so you apply whatever each
stream needs: ``alignment.shift_times`` to reposition one, ``alignment.remap_times`` to re-time a drifting one against
the reference. Each interface has its own clock and its own correction, so this is a loop over interfaces, never one
global remap. One caveat applies to any of them: they mutate the live interface, so an alignment step that runs twice
compounds (a ``shift_times`` would shift twice); build the converter fresh per conversion.
