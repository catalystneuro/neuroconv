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

The alignment state is a single **offset** per interface, applied at write:

.. code-block:: text

    output = native + offset

The default is ``0.0``, which is the identity, so an interface that is never aligned writes the times its source
recorded. The offset is stored rather than folded in, and the source times are never mutated, which means the
original timing is always recoverable and applying an alignment twice cannot silently double it.

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

``remap_times`` reads and writes in the same frame, which is what fixes where its arguments live: it interpolates the
times as they currently stand, so ``local_sync_times`` is on the timeline ``get_times`` reports and carries a shift
already applied, while ``reference_sync_times`` is on the clock being aligned to. The two arrays pair up positionally,
so a pulse only one system recorded has to be dropped from the other as well.

Whole-interface against per-object
----------------------------------

What an operation is called on is what it applies to.

``shift_times`` places the whole interface and takes no key. ``remap_times`` is one clock's correction, so it applies
to every object of the interface for the same reason. Times themselves belong to one object, so ``get_times`` and
``set_times`` are reached through the object: ``alignment[key].set_times(times)``.

The reason a shift moves everything at once is that an interface reads one source from one acquisition system, so its
objects share a clock: every keypoint of a pose interface comes off the same video, every table of an events
interface off the same board. Moving them together is what preserves the timing they already have relative to one
another, which is a fact about the recording rather than something the framework needs to compute.
