Timing Model
============

This page records the design decisions behind NeuroConv's temporal alignment surface, ``interface.alignment``. The
user guide (:doc:`../user_guide/temporal_alignment`) explains how to align a conversion; this page explains why the
surface has the shape it does, which is what you need when adding alignment to a new modality.

The model
---------

The primitive is the **time-bearing object**: anything an interface writes that carries a time coordinate relative
to ``session_start_time``. An ``ElectricalSeries`` is one, so is each ``PoseEstimationSeries`` of a pose interface,
each ``EventsTable`` of an events interface, and a trials table. A ``Device``, an electrodes table and a ``Skeleton``
are not.

What makes it the right primitive is how little it claims. It says this object has times, and nothing more: not which
clock they came from, not which other objects share that clock. That is the weakest statement that still supports
every operation the surface offers, and weakest is what you want here, because anything stronger would have to be
true of the data and the framework has no way to check it.

The alternatives all claim more. A timebase, a clock or a timeline names a *group* of objects sharing one basis, so
building on one means the framework has to know which objects belong together. That is a fact about how the rig was
wired rather than anything present in the files: a converter holding an Intan recording, pose estimation and a
behavior camera has three such groups and nothing in the data distinguishes them. With time-bearing objects the
question never arises. Two objects are co-timed because you gave them times that agree, which is a description of
what you did rather than a claim the framework makes on your behalf.

The alignment state is two scalar **offsets** and, optionally, one replacement array, applied at write:

.. code-block:: text

    output = base + object_offset + interface_offset

``base`` is the object's native times, or a replacement array once ``set_times`` or ``remap_times`` has provided one.
``interface_offset`` is written by ``shift_times`` and is shared by every object the interface names. ``object_offset``
is written by ``start_at`` and belongs to one object. Both default to ``0.0``, the identity, so an interface that is
never aligned writes the times its source recorded. The offsets are stored rather than folded into the times, and the
source times are never mutated, so the original timing stays recoverable and nothing is read from the source until
someone asks for times.

Two axes, two operations
------------------------

Every operation on the surface sits on two axes. **Scope**: does it move the whole interface rigidly, or one object
relative to its siblings? **Arithmetic**: is the number it takes relative, a delta added to where the object is, or
absolute, a statement of where the object should be? Whether the operation stores a scalar or materialises every
sample time follows from those two.

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - scope
     - relative, a delta
     - absolute, a position
   * - whole interface
     - ``shift_times(delta)``
     - empty
   * - one object
     - empty
     - ``start_at(t)``, and ``set_times(times)`` when the times themselves are known

``shift_times`` is interface-wide and relative because the number it takes is a fact about a device's clock: this
rig's clock reads 3.2 seconds behind the reference, so everything it wrote moves by 3.2 seconds, including objects
that were placed individually, which keep their relative positions. An interface reads one source from one
acquisition system, so one clock offset is the right granularity.

``start_at`` is per-object and absolute because the number it takes is a fact about one object: this file began 12.5
seconds into the session. It arises where the source records nothing about where its pieces sit, a camera or a
microphone triggered once per trial, and there the user knows a position per file and never a delta. It stores one
scalar, so placing an hour of audio costs nothing, where expressing the same fact through ``set_times`` would build
158 million sample times to carry one number and would force the series to be written as a timestamps array rather
than a rate.

The empty cells are empty because nobody has a number to put in them. A per-object shift would need a delta for one
file among its siblings on the same device, which no workflow produces, and it would accumulate on a re-run, which is
the failure ``start_at`` exists to remove. An interface-wide absolute setter would write into the same offset
``shift_times`` accumulates into and silently discard an earlier shift, since it has nothing to store itself against.
The per-object form escapes that because its scalar is separate from the interface's.

Composition, not inheritance
----------------------------

Interfaces *hold* the alignment component, as ``interface.alignment``, rather than inheriting a base class that
provides the methods directly. The base class alternative is ``BaseTemporalAlignmentInterface``, whose contract is
``get_timestamps() -> np.ndarray`` and ``set_aligned_timestamps(np.ndarray)``.

Holding it wins on four counts.

**It promises nothing about shape.** The inherited contract is one array per interface, and an events interface has
no such array, since its times live per event type. Satisfying it means fabricating one, which is how a dict-returning
``get_timestamps`` ends up violating its own annotation. A held component makes no shape promise at all.

**It gives a converter a capability check.** A converter can align its interfaces if each one has an ``alignment``,
and can name the one that does not. That is a plain attribute test rather than duck-typing individual methods.

**It keeps one implementation.** Every modality shares the same component, so a fix or an addition lands once instead
of being reimplemented per base class, and the modalities cannot drift apart in behaviour.

**It leaves the interface's own surface alone.** An interface class is already large, and half a dozen alignment
methods at the top level would bury ``get_metadata`` and ``add_to_nwbfile`` among them. Under a namespace they stay
together and are discoverable as a unit.

Everything a user passes or reads is in file time
--------------------------------------------------

``get_times`` returns the times the file will carry, and ``set_times`` writes exactly the times it is given, so
calling the getter and handing the result straight back to the setter changes nothing.

There were two coherent readings of ``set_times`` and this is the one that was chosen. Under the other, the argument
is the object's times *inside* the interface and the file receives ``times + offset``; that version composes with a
shift and commutes with it, but the file then quietly disagrees with the numbers the caller passed, and the
disagreement is only discoverable by reading the file back or by knowing about a scalar the caller never typed, since
the offset is often applied by a converter rather than by the user. The chosen reading puts the surprise in the API
instead: whatever ``get_times`` reports is what will be written, always.

A consequence worth stating plainly, because it looks like a bug and is not: a shift and a set do **not** commute.
``shift_times(2.0)`` followed by ``set_times(v)`` writes ``v``, while ``set_times(v)`` followed by
``shift_times(2.0)`` writes ``v + 2.0``. This is assignment against increment, the same asymmetry as ``x = 10``
against ``x += 2``, and it follows from ``set_times`` being absolute and ``shift_times`` being relative.

``start_at`` is absolute in the same way, and the cleanest statement of how the four operations compose is as functions
on ``T``, the times an object will be written on:

.. code-block:: text

    shift_times(d):      T' = T + d
    start_at(t):         T' = T + (t - T[0])
    set_times(A):        T' = A
    remap_times(L, R):   T' = interp(T, L, R)

Composition is function composition, so order matters exactly as it does for functions. ``start_at`` twice is a no-op.
``set_times`` or ``remap_times`` after ``start_at`` supersede it, since they define the times outright, and
``start_at`` after either moves the given times rigidly. A later ``shift_times`` moves everything. In storage,
``start_at`` writes ``object_offset = t - base[0] - interface_offset``, the two array writers reset ``object_offset``
to zero, and the start is read back as ``base[0] + object_offset + interface_offset`` rather than stored, so there is
no second copy of it to fall out of step. ``start_at`` needs ``base[0]`` without materialising the array, which is
what the optional native start an interface can register alongside its native times is for; absent it, the first
native time is read.

``remap_times`` reads and writes in the same frame, which is what fixes where its arguments live: it interpolates the
times as they currently stand, so ``local_sync_times`` is on the timeline ``get_times`` reports and carries a shift
already applied, while ``reference_sync_times`` is on the clock being aligned to. The two arrays pair up positionally,
so a pulse only one system recorded has to be dropped from the other as well.

How many objects an interface names
-----------------------------------

An interface registers its time-bearing objects, and how many it names follows from where their placement comes from.
Where the source records how its segments sit, the interface names one object and its times carry the layout. A
multi-segment electrophysiology recording is the case: each segment's start is in the file and the extractor already
exposes it, and the segment count is a reader setting, a gap tolerance, rather than a fact about the session, so it
cannot carry a public address. Where only the user can say where a piece sits, the interface names one object per
piece. Trialised external video and per-trial audio files are the cases: the files record nothing about their
position, so each is placed with ``start_at``. Files an acquisition system split at a size limit are neither. They are
one continuous recording, and the extractor concatenates them before the interface sees them.
