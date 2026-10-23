"""Temporal-alignment machinery, held by interfaces via composition and exposed as ``interface.temporal_alignment``.

An interface's alignment surface is a container. It names the interface's **time-bearing objects**, the
things it writes that carry a time coordinate, so that a single one can be reached and re-timed on its own::

    interface.temporal_alignment.shift_times(3.0)                       # every object, rigid, accumulates
    interface.temporal_alignment.move_start_to(100.0)                   # every object, the earliest start at 100 s
    interface.temporal_alignment.keys()                                 # the objects this interface can name
    interface.temporal_alignment["response"].get_times()                # the times this object will be written on
    interface.temporal_alignment["response"].set_times(times)           # this object's times outright
    interface.temporal_alignment["response"].shift_times(-0.040)        # this object alone, rigid, accumulates
    interface.temporal_alignment["response"].move_start_to(12.5)        # this object's first sample at 12.5 s, one number
    interface.temporal_alignment["response"].remap_times(...)           # this object's clock against a reference

What an operation is called on is what it applies to. ``shift_times`` and ``move_start_to`` work at both
scopes: on one object they move that object, on the interface they move every object by one common amount.
Literal times belong to one object and so cannot be given without one. Each object holds its own offset, and
the interface holds none, so an interface that names nothing has nothing to move and every operation on it
raises. Events interfaces register their event types on first access to alignment. An event object supports
every operation; its durations never change under a shift, are left alone by ``set_times``, and are recomputed
through the map by ``remap_times``, since two clocks that drift stretch an interval as well as move it.

The offset is **held and applied when times are asked for**, rather than added into the times when it is
given. The obvious alternative, walking every object on each shift and rewriting its times in place, reads
more simply and costs the property this component exists for: shifting would have to materialise every
object's times just to add a number to them, which for a three-hour recording at 30 kHz is a 2.6 GB float64
vector standing in for one scalar, and it would open every source a caller had merely named. Holding it
means nothing is read until someone asks for times.
"""

from abc import ABC, abstractmethod

import numpy as np


class _BaseTimeBearingObject(ABC):
    """One time-bearing object, reached as ``interface.temporal_alignment[key]``: a series, or the events of one type.

    Writes the operations once, in terms of a few steps a subclass provides: read the times, read the first time,
    read the number of samples, add an offset, and replace the times. A subclass decides where the alignment is
    kept, in its own fields or in the object that holds the data, and nothing else.
    """

    @abstractmethod
    def get_times(self) -> np.ndarray:
        """Return the times this object will be written on, its offset included."""

    @abstractmethod
    def _get_start_time(self) -> float:
        """The time this object's first sample will be written on, without building its times, for the write path."""

    @abstractmethod
    def _get_number_of_samples(self) -> int | None:
        """How many times ``set_times`` has to be given, or ``None`` when the count is not known and not checked."""

    @abstractmethod
    def _add_offset(self, delta: float) -> None:
        """Move every time of this object by ``delta`` seconds."""

    @abstractmethod
    def _replace_times(self, times: np.ndarray) -> None:
        """Make ``times`` this object's times, with no offset on top of them."""

    def get_durations(self) -> np.ndarray | None:
        """Return the durations of this object's events, or ``None`` for an object without durations."""
        return None

    def _replace_durations(self, durations: np.ndarray) -> None:
        """Make ``durations`` this object's durations. Only an object with durations provides it."""
        raise NotImplementedError

    @property
    def has_durations(self) -> bool:
        """Whether this object has one duration per timestamp, which only an event type can have."""
        return self.get_durations() is not None

    def _is_empty(self) -> bool:
        """Whether this object has no samples, which leaves it no start to place or to be placed by."""
        return self.get_times().size == 0

    def shift_times(self, delta: float) -> None:
        """Shift this object alone by ``delta`` seconds, leaving the interface's other objects where they are.

        For a correction that belongs to one object, a trial video a synchronization check finds 40
        milliseconds late. It is relative, so repeated calls accumulate; a correction for every object of the
        interface is ``interface.temporal_alignment.shift_times(delta)``.
        """
        self._add_offset(float(delta))

    def move_start_to(self, starting_time: float) -> None:
        """Place this object so that its first sample sits at ``starting_time`` seconds on the session clock.

        For a file that was triggered on its own and records nothing about where it sits, a video or an audio
        file written once per trial: the one number you know about it is when it began. This stores that
        number and reads nothing, so it costs the same for an hour of audio as for a second, and the object
        keeps its regular spacing and can still be written as a rate.

        It states a position rather than adding to one, so calling it twice with the same value changes
        nothing, and a ``shift_times`` applied earlier is superseded for this object while one applied
        afterwards still moves it. ``set_times`` and ``remap_times`` define the object's times outright and
        so supersede an earlier ``move_start_to``; called after them, ``move_start_to`` moves the given times
        rigidly.
        """
        starting_time = float(starting_time)
        if not np.isfinite(starting_time):
            raise ValueError(f"`move_start_to` needs a finite time in seconds, not {starting_time}.")
        start_time = self._get_start_time()
        if not np.isfinite(start_time):
            raise ValueError(
                "This object has no finite first time to place: it is empty, or a remap marked its first "
                "sample as outside the pulses."
            )
        self._add_offset(starting_time - start_time)

    def set_times(self, times) -> None:
        """Write these times for this object, exactly as given, one per sample.

        For per-sample times you already trust, from a synchronization signal or a computation of your own.
        They are the times the file will carry, so a shift or a ``move_start_to`` applied earlier is superseded
        for this object; a shift applied afterwards still moves it, the way any later correction would. For an
        event type they are the timestamps, and the durations are left as they are.
        """
        times = np.asarray(times)
        number_of_samples = self._get_number_of_samples()
        if number_of_samples is not None and times.shape != (number_of_samples,):
            raise ValueError(
                f"This object has {number_of_samples} samples, but {times.size} times were given. "
                "`set_times` needs one time per sample."
            )
        self._replace_times(times)

    def remap_times(self, *, local_sync_times, reference_sync_times, interpolation_function=None) -> None:
        """Re-express this object's times on a reference clock through synchronization pulses.

        Use this when the two clocks drift, so no single shift lines them up. When they differ only by a
        constant, ``interface.temporal_alignment.shift_times`` says so more cheaply and keeps a regular series
        regular.

        Parameters
        ----------
        local_sync_times : array-like of float
            The pulses as this object's own system timestamped them, on the timeline the object currently
            reports: if you have already shifted this interface, these have to carry that shift too.
        reference_sync_times : array-like of float
            The same pulses, in the same order, as timestamped by the clock being aligned to.
        interpolation_function : callable, optional
            How to turn the pulse pairs into a map, ``numpy.interp`` when not given. Called as
            ``interpolation_function(times, local_sync_times, reference_sync_times)`` and returns the
            remapped times, which is ``numpy.interp``'s own signature. Bind its options with
            ``functools.partial``, ``partial(numpy.interp, left=numpy.nan, right=numpy.nan)`` to mark
            samples outside the pulse range instead of clamping them. Anything of that shape works, so a
            different scheme is a small adapter::

                def extrapolating(times, local_sync_times, reference_sync_times):
                    return interp1d(local_sync_times, reference_sync_times, fill_value="extrapolate")(times)

        Notes
        -----
        The two arrays are one set of physical events read off two clocks. A synchronization line runs
        between the systems and each of them timestamps every pulse on it, so pulse ``i`` appears once in
        each array, at a different time::

                                 pulse 1    pulse 2    pulse 3
            this object's clock      0.0        1.9        3.8     <- local_sync_times
            reference clock         10.0       12.0       14.0     <- reference_sync_times

        For example, a behaviour camera records alongside an electrophysiology rig. On every tenth frame the
        camera sends a TTL pulse into a digital input on the electrophysiology acquisition board, and it
        also writes its own log of when it sent them. If we are writing the session time in the clock of the
        electrophysiology rig then we need to remap the times of the camera, so the parameters are

        - ``reference_sync_times``: the times the acquisition board recorded those pulses on its digital
          input. Those are on the session's clock.
        - ``local_sync_times``: the times the camera's own log gives for the same pulses. Those are on the
          (local) camera clock.

        So in this case, remap is called on the camera interface to remap its times towards the
        electrophysiology board.

        Times falling between two local pulses are interpolated proportionally, and nothing is resampled:
        the data is left alone and only the times move. The two arrays pair up positionally, so a pulse only
        one of the systems recorded has to be dropped from the other array as well, and a mismatched count
        raises rather than guessing an offset. Under the default, samples outside the first and last local
        pulse are clamped rather than extrapolated, following ``numpy.interp``, so anything recorded before
        the first local pulse lands on the first reference time; ``interpolation_function`` is how you
        choose otherwise.
        """
        local_sync_times = np.asarray(local_sync_times)
        reference_sync_times = np.asarray(reference_sync_times)
        if local_sync_times.shape != reference_sync_times.shape:
            raise ValueError(
                "The synchronization pulses have to pair up: `local_sync_times` has "
                f"{local_sync_times.size} of them and `reference_sync_times` has {reference_sync_times.size}."
            )
        if interpolation_function is None:
            interpolation_function = np.interp
        times = self.get_times()
        durations = self.get_durations()
        remapped_times = interpolation_function(times, local_sync_times, reference_sync_times)
        if durations is not None:
            remapped_ends = interpolation_function(times + durations, local_sync_times, reference_sync_times)
            self._replace_durations(remapped_ends - remapped_times)
        self._replace_times(remapped_times)


class _TimeBearingObject(_BaseTimeBearingObject):
    """One time-bearing object, reached as ``interface.temporal_alignment[key]``: a series, or the events of one type.

    Holds an optional replacement for the object's times and one offset of its own, so the source times are
    never mutated and what is written is ``(replacement or default) + offset``. The default times are what the
    interface writes when nothing has been said: the times its source recorded, or the ones its header gives
    where the source records none.

    Events are written to an ``EventsTable``, a ``DynamicTable`` with a ``timestamp`` column and an optional
    ``duration`` column. The times of an event type are its timestamps, and it may have one duration per
    timestamp. A rigid shift moves the timestamps and leaves the durations, since a translation cancels in a
    difference. ``set_times`` replaces the timestamps and leaves the durations, which the caller did not give.
    ``remap_times`` re-times both ends of every event, so a duration becomes ``map(timestamp + duration) -
    map(timestamp)``: it changes whenever the two clocks run at different rates.
    """

    def __init__(
        self,
        *,
        get_native_times,
        default_start_time=None,
        get_number_of_samples=None,
        get_native_durations=None,
    ):
        # A callable rather than an array, so an interface registers its objects without reading its source.
        # The start is separate so that placing an object needs one number, not every sample time; a number
        # where the interface knows it outright, a callable where it has to be read from a header.
        self._get_native_times = get_native_times
        self._default_start_time = default_start_time
        # The count is separate from the times because some objects know how many samples they have but not
        # when they were taken, which is when `set_times` is needed most.
        self._get_native_number_of_samples = get_number_of_samples
        self._get_native_durations = get_native_durations
        self._times: np.ndarray | None = None
        self._durations: np.ndarray | None = None
        self._object_offset = 0.0

    def get_times(self) -> np.ndarray:
        """Return the times this object will be written on, its offset included."""
        return self._get_times(get_default_times=self._get_native_times)

    def _get_times(self, *, get_default_times) -> np.ndarray:
        """``get_times`` with ``get_default_times`` standing in for the default, for a writer that needs another one."""
        times = self._times if self._times is not None else get_default_times()
        return times + self._object_offset

    def get_durations(self) -> np.ndarray | None:
        """Return the durations of this object's events, or ``None`` for an object without durations."""
        if self._durations is not None:
            return self._durations
        if self._get_native_durations is None:
            return None
        return self._get_native_durations()

    def _get_start_time(self) -> float:
        """The time this object's first sample will be written on, without building its times, for the write path."""
        return self._get_base_start_time() + self._object_offset

    def _get_base_start_time(self) -> float:
        """The first time of what the offsets are added to, without building the times where the interface said it."""
        if self._times is not None:
            base_start_time = self._times[0] if self._times.size else np.nan
        elif callable(self._default_start_time):
            base_start_time = self._default_start_time()
        elif self._default_start_time is not None:
            base_start_time = self._default_start_time
        else:
            default_times = np.asarray(self._get_native_times())
            base_start_time = default_times[0] if default_times.size else np.nan
        return float(base_start_time)

    def _get_number_of_samples(self) -> int | None:
        if self._get_native_number_of_samples is None:
            return None
        return self._get_native_number_of_samples()

    def _add_offset(self, delta: float) -> None:
        self._object_offset += delta

    def _replace_times(self, times: np.ndarray) -> None:
        self._times = times
        self._object_offset = 0.0

    def _replace_durations(self, durations: np.ndarray) -> None:
        self._durations = durations


class _TemporalAlignment:
    """The alignment surface for an interface's time-bearing objects, exposed as ``interface.temporal_alignment``.

    Names the objects the interface registered, each holding its own offset, ``output = default + offset``,
    ``0.0`` by default (identity). ``shift_times``,
    ``move_start_to`` and ``remap_times`` called here act on every object: the first two move them all by one
    common amount, and ``remap_times`` is one clock's correction. Called on ``temporal_alignment[key]`` they act on that
    object alone, and times for one object are given only through the object itself,
    ``temporal_alignment[key].set_times(times)``.
    """

    def __init__(self):
        self._name_to_time_bearing_object: dict[str, _BaseTimeBearingObject] = {}

    def _register(
        self,
        *,
        key: str,
        get_native_times,
        default_start_time=None,
        get_number_of_samples=None,
        get_native_durations=None,
    ) -> _TimeBearingObject:
        """Name one time-bearing object. Called by the interface, not by a user.

        ``get_native_times`` returns the times the object has when nothing has been said. ``default_start_time``
        is their first value, a number or a callable, given so that ``move_start_to`` and the compact write build
        no array to learn it. Without it the first default time is read from the array.
        ``get_number_of_samples`` returns how many times ``set_times`` has to be given, and without it the count
        is not checked. ``get_native_durations`` returns one duration per time, or ``None``, for an event type.
        """
        time_bearing_object = _TimeBearingObject(
            get_native_times=get_native_times,
            default_start_time=default_start_time,
            get_number_of_samples=get_number_of_samples,
            get_native_durations=get_native_durations,
        )
        self._register_time_bearing_object(key=key, time_bearing_object=time_bearing_object)
        return time_bearing_object

    def _register_time_bearing_object(self, *, key: str, time_bearing_object: _BaseTimeBearingObject) -> None:
        """Name a time-bearing object the interface built itself. Called by the interface, not by a user.

        For an object that keeps its alignment somewhere other than a ``_TimeBearingObject``, a recording
        segment whose alignment SpikeInterface holds.
        """
        self._name_to_time_bearing_object[key] = time_bearing_object

    def keys(self) -> tuple[str, ...]:
        """The time-bearing objects this interface can name, empty when it names none."""
        return tuple(self._name_to_time_bearing_object)

    def __getitem__(self, key: str) -> _BaseTimeBearingObject:
        if key not in self._name_to_time_bearing_object:
            named = ", ".join(repr(name) for name in self._name_to_time_bearing_object) or "nothing"
            raise KeyError(f"{key!r} is not a time-bearing object of this interface. It names {named}.")
        return self._name_to_time_bearing_object[key]

    def shift_times(self, delta: float) -> None:
        """Shift every time-bearing object in the interface by ``delta`` seconds (relative, accumulates)."""
        if not self._name_to_time_bearing_object:
            raise NotImplementedError(
                "This interface has registered no time-bearing objects, so there is nothing to shift."
            )
        for time_bearing_object in self._name_to_time_bearing_object.values():
            time_bearing_object.shift_times(delta)

    def move_start_to(self, starting_time: float) -> None:
        """Move every time-bearing object by one amount, so that the earliest of their starts sits at ``starting_time``.

        The relative placement of the objects is kept: starts at 10 and 15 seconds become 100 and 105 after
        ``move_start_to(100.0)``, where placing each object at 100 would put both there. A series starts at its
        first sample, as it currently stands, earlier alignment included. Each object takes the common shift
        and nothing else is stored, so calling it twice with the same value changes nothing.

        Empty objects have no start and are left out of the earliest one. All starts are read and checked
        before anything moves, so a failure leaves every object where it was.
        """
        starting_time = float(starting_time)
        if not np.isfinite(starting_time):
            raise ValueError(f"`move_start_to` needs a finite time in seconds, not {starting_time}.")
        if not self._name_to_time_bearing_object:
            raise NotImplementedError(
                "This interface has registered no time-bearing objects, so it has no start to move."
            )
        starts = []
        for key, time_bearing_object in self._name_to_time_bearing_object.items():
            start = time_bearing_object._get_start_time()
            if np.isfinite(start):
                starts.append(start)
            elif not time_bearing_object._is_empty():
                raise ValueError(
                    f"{key!r} has no finite first time to place by: a remap marked its first sample as outside "
                    "the pulses."
                )
        if not starts:
            raise ValueError("Every time-bearing object of this interface is empty, so there is no start to move.")
        self.shift_times(starting_time - min(starts))

    def remap_times(self, *, local_sync_times, reference_sync_times, interpolation_function=None) -> None:
        """Re-express every time-bearing object on a reference clock through synchronization pulses.

        One acquisition clock means one correction, so this needs no key. See
        :meth:`_BaseTimeBearingObject.remap_times`.
        """
        if not self._name_to_time_bearing_object:
            raise NotImplementedError(
                "This interface has registered no time-bearing objects, so there is nothing to remap."
            )
        for time_bearing_object in self._name_to_time_bearing_object.values():
            time_bearing_object.remap_times(
                local_sync_times=local_sync_times,
                reference_sync_times=reference_sync_times,
                interpolation_function=interpolation_function,
            )
