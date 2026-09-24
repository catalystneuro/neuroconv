Timing Model
============

For alignment workflows and examples, see the :doc:`../user_guide/temporal_alignment`. The converter alignment surface
described here is not yet implemented.

Objects and state
-----------------

A **time-bearing object** is a unit of timed data an interface exposes for alignment. Its time coordinates are
relative to ``session_start_time``. Examples include an ``ElectricalSeries`` and an ``EventsTable``. A ``Device``, an
electrodes table or a ``Skeleton`` carries no time coordinate and therefore is not a time-bearing object.

Each object can be aligned independently, so it owns its base times and one scalar offset. The offset translates
the base times without changing the intervals between them, and the output times are their sum:

.. code-block:: text

    get_times() = base_times + offset

The ``base_times`` come from two places. Initially they are the source's **native times**: the times its source
recorded or, where it records none, the ones its header gives. A call to ``set_times`` can supply a replacement, or
``remap_times`` can compute one from the current times and synchronization pairs. The offset starts at ``0.0``, so an
object with no alignment writes its native times.

This state remains on the object when an interface or converter groups it with others. A collection can move all of
its members by updating their offsets, so it needs no offset of its own. A shared collection offset would spread an
object's timing state across several places: an absolute placement on that object would then have to compensate for
the shared value. Keeping one offset per object makes its state sufficient to determine what it writes, regardless
of the collections around it. Writers obtain those times through alignment, including the aligned start when writing
a regular series with a rate.

Object registration
-------------------

**Registration** is how an interface declares its time-bearing objects to the alignment component. For each object,
it supplies a key and a callable that reads its native times, plus a scalar start accessor where available. The
component can then expose that object for alignment without knowing how its source format stores time.

Storing the callables without invoking them keeps registration independent of when timestamp values are needed.

Choosing what to register determines which data can be aligned independently. That choice belongs to each
interface's alignment design, and the registered objects need not map one to one to source files or written NWB
objects. Trial video illustrates this distinction: each file is registered separately so its start can be placed
independently, even when several files contribute to one written series.

Registration finishes during ``__init__``, before alignment begins, because every operation acts on the objects
present when it is called. A later registration would miss earlier shifts or remaps and leave the interface partly
aligned. A shared collection offset would only recover shifts, so it would not solve that ordering problem.

Lazy evaluation
---------------

**Lazy evaluation** means building timestamp arrays only when an operation needs their values. An object can retain
access to its native times through a reader instead of loading them during registration. This matters for long
recordings, where a timing correction should not require reading or allocating an array with one entry per sample.

The separation between base times and an offset makes this possible for translations. ``shift_times`` updates the
offset without reading timestamps. ``move_start_to`` needs the current start, so it can use a scalar start accessor
when one is available. Otherwise finding that start may require reading timestamps, even though the placement itself
still changes only the offset. Laziness therefore depends on what information the operation needs and what the
interface can supply without a full array.

Operations that need the timestamp values evaluate them at that point. ``get_times`` returns the output array, and
``remap_times`` evaluates the current times and stores the remapped result. They read through the native-time
callable only when no replacement times have been supplied. ``set_times`` already receives the replacement values,
so it does not need to read the native times first.

The benefit also depends on preserving compact timing through writing. A regular series remains representable by a
starting time and a rate after a shift or placement. Its writer can use the aligned start and the existing rate
without constructing a timestamp array just to express the correction.

Operation semantics
-------------------

Although storage separates base times from an offset, the public operations all refer to the resulting output times.
``get_times`` returns the times the file will carry, and ``set_times`` replaces them with exactly the supplied values.
Passing the result of ``get_times`` to ``set_times`` therefore leaves the output unchanged.

Using output times makes that guarantee independent of earlier alignment. If ``set_times`` instead accepted base
times, an existing offset would be added to the supplied values. The caller would have to know about that offset to
predict what the file receives, even when a converter applied it elsewhere. With the selected semantics, the values
passed to the setter are sufficient to know the result.

The other operations follow the same convention. For one nonempty series, their effects can be expressed directly on
``T``, its current output times:

.. code-block:: text

    shift_times(d):      T' = T + d
    move_start_to(t):    T' = T + (t - T[0])
    set_times(A):        T' = A
    remap_times(L, R):   T' = interp(T, L, R)

The first two operations translate the times, so they change only the offset and preserve sample spacing and
durations. Their difference is how the translation is determined: ``shift_times`` adds a correction, while
``move_start_to`` computes the correction needed to reach a destination. For a series, that destination refers to
the first sample. For an events table, it refers to the earliest onset. An object with base start ``s`` therefore
receives ``offset = t - s`` when placed at ``t``. Repeating the same placement leaves it in place, while repeating a
shift accumulates.

``set_times`` and ``remap_times`` store their resulting output times directly as new base times and reset the offset
to zero. Retaining the offset could satisfy the same output-time contract, but would require subtracting it from the
replacement values. Resetting it keeps the new base times equal to the operation's result.

The output-time contract also determines operation order:
``shift_times(2.0)`` followed by ``set_times(v)`` writes ``v``, while ``set_times(v)`` followed by
``shift_times(2.0)`` writes ``v + 2.0``. This is the same asymmetry as assignment and increment, and follows from the
setter promising the supplied output times.

For ``remap_times``, using the current output times also determines where the synchronization arguments belong.
``local_sync_times`` must describe the timeline reported by ``get_times``, including any shift already applied,
while ``reference_sync_times`` describe the target timeline. Each local time is paired with the reference time at the
same array position, and both must identify the same event.

Collection operations
---------------------

Once an interface has registered its objects, its alignment component can also address them as a collection.
A converter extends this grouping to interfaces or other converters. At either level, the collection selects which
objects an operation reaches without adding timing state.
``shift_times`` and ``move_start_to`` are available on both objects and collections because knowing a correction or a
destination is independent of how many objects need it.

Moving a collection means preserving the relative timing of its members. For ``shift_times(delta)``, this follows
directly from adding the same delta to every descendant object's offset. For ``move_start_to(t)``, the collection
first needs a common anchor: its earliest current start. It computes ``delta = t - min(current_starts)`` across all
descendant objects and applies that one shift. Starts at 10 and 15 seconds therefore become 100 and 105 after
placement at 100. Placing each child independently at 100 would erase their relative timing. The same reasoning
holds through nested converters, where one earliest descendant start determines the shift for the entire selection.

The collection model extends to operations that have a meaningful result for every member. ``remap_times`` can apply
one map to every object in an interface or converter, provided that map is valid for all their current timestamps.
``get_times`` and ``set_times`` address one object's times, so they require selecting that object. Automatically
forwarding those calls through a collection with one object remains deferred.

Nested addressing
-----------------

Because intermediate collections are useful operation targets, alignment addressing follows the converter's
structure. ``converter.alignment[name]`` exposes ``converter.data_interface_objects[name].alignment``, and indexing
continues through nested converters until an interface's keys select its time-bearing objects. ``keys()`` lists the
immediate members of the selected collection. This reuses child names from converter configuration and gives each
intermediate collection a handle.

The alternative is flat access through **qualified keys**, such as ``"Behavior/Video/trial_02"``, with each key
encoding an object's full path. That would require separator and escaping rules and provide no direct handle for
intermediate collections. Nested access expresses the same path through successive lookups, and each step can also
be the target of a collection operation.

Each collection has its own keys. Equal local keys in different interfaces need no global renaming because their
parent collections distinguish them.

The hierarchy follows public composition boundaries. A composite interface exposes its own registered object keys
and keeps its internal interfaces private, even if those interfaces help it read or write the data. Its users see
the timing units the composite presents, without needing to follow its internal implementation.

Composition
-----------

To make this object-level model available across modalities, interfaces expose timing operations through
``interface.alignment``. The component manages alignment state and operations, while each interface identifies its
objects and supplies access to their native times. This division lets the same implementation handle an interface
with one series or several independent sets of times, without knowing how either source format stores them.
Modality-specific code defines what can be aligned, and the shared component defines how alignment behaves.

The distinction between an interface and its objects matters when considering inheritance. An inherited contract
such as ``get_timestamps() -> np.ndarray`` and ``set_aligned_timestamps(np.ndarray)`` assumes one array per interface.
An events interface has separate times for each event type, so returning a dictionary violates that contract and
combining the arrays loses their separate identities. Inheritance could support object registration too, but it would
still tie alignment to the interface hierarchy and place timing methods beside ``get_metadata`` and
``add_to_nwbfile``. A held component keeps those methods together under ``alignment`` without requiring a particular
interface base class. That same attribute gives converters a common surface through which to check alignment support
and apply collection operations.

Edge cases
----------

Placement depends on finding a meaningful start, and some objects have none. An **empty object** has no samples or
events, so collection-level ``move_start_to`` excludes it when finding the earliest start. Other members can still
determine the placement, but the operation fails if every object is empty. Object-level ``move_start_to`` rejects an
empty object for the same reason: there is no start to move.

Having samples is not sufficient if their start is invalid. A **nonfinite time** is ``NaN`` (not a number), positive
infinity, or negative infinity, none of which defines a meaningful placement. ``move_start_to`` therefore rejects a
nonfinite target or a nonfinite start in any selected nonempty object. The target and all relevant starts are checked
before offsets change, so a failed placement does not leave only part of the collection shifted.

Successful alignment operations still leave the writer responsible for constraints on how its objects fit together.
For multi-file video and audio, each file defaults to start at zero, and those defaults overlap when several nonempty
files are supplied. In the supplied file order, each file's first sample must be strictly later than the previous
file's last sample. The writer rejects overlapping or reversed placements, including a shared boundary timestamp.
Checking the resulting times makes the outcome independent of which alignment methods were called or at which
scope. A common shift preserves an overlap, so it does not make unplaced files valid. This establishes ordering only:
a first file left at zero can pass when later files start after it ends.
