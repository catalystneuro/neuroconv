"""Temporal-alignment machinery, held by interfaces via composition and exposed as ``interface.alignment``.

An interface's alignment surface is a container. It carries the whole-interface offset, and it names the
interface's **time-bearing objects**, the things it writes that carry a time coordinate, so that a single one
can be reached and re-timed on its own::

    interface.alignment.shift_times(3.0)                   # every object, rigid, accumulates
    interface.alignment.keys()                             # the objects this interface can name
    interface.alignment["response"].get_times()            # the times this object will be written on
    interface.alignment["response"].set_times(times)       # this object's times outright
    interface.alignment["response"].remap_times(...)       # this object's clock against a reference

What an operation is called on is what it applies to: a shift positions the whole interface and so cannot take
a key, while literal times belong to one object and so cannot be given without one. An interface that names
nothing still shifts: registration is what a keyed operation needs, and the events interfaces register nothing
because enumerating their event types means reading the source. The objects are typed by shape, since a series
is a single sample axis and takes ``set_times`` while a table is timestamps plus durations and cannot, there
being no one array to hand it. Only the series-shaped one exists here so far.
"""

from collections.abc import Iterator

import numpy as np


class _TimeBearingSeries:
    """One series-shaped time-bearing object, reached as ``interface.alignment[key]``.

    Holds an optional replacement for the object's times and nothing else, so the source times are never
    mutated and what is written is ``(replacement or native) + the interface's offset``.
    """

    def __init__(self, *, get_native_times, alignment: "_TemporalAlignment"):
        # A callable rather than an array, so an interface registers its objects without reading its source.
        self._get_native_times = get_native_times
        self._alignment = alignment
        self._times: np.ndarray | None = None

    def get_times(self) -> np.ndarray:
        """Return the times this object will be written on, the interface's offset included."""
        times = self._times if self._times is not None else np.asarray(self._get_native_times())
        return times + self._alignment.offset

    def set_times(self, times) -> None:
        """Replace this object's times with the ones given.

        For per-sample times you already trust, from a synchronization signal or a computation of your own.
        The interface's offset still applies on top, since that positions the whole interface and this
        positions one object inside it.
        """
        self._times = np.asarray(times)

    def remap_times(self, *, local_sync_times, reference_sync_times) -> None:
        """Re-express this object's times on a reference clock through synchronization pulses.

        ``local_sync_times`` are the pulses as this object's own clock recorded them and
        ``reference_sync_times`` are the same pulses on the clock being aligned to. Times between pulses are
        interpolated. Use this when the two clocks drift, so no single shift lines them up.
        """
        local_sync_times = np.asarray(local_sync_times)
        reference_sync_times = np.asarray(reference_sync_times)
        if local_sync_times.shape != reference_sync_times.shape:
            raise ValueError(
                "The synchronization pulses have to pair up: `local_sync_times` has "
                f"{local_sync_times.size} of them and `reference_sync_times` has {reference_sync_times.size}."
            )
        remapped_times = np.interp(self.get_times(), local_sync_times, reference_sync_times)
        # These are the times to be written, and ``get_times`` adds the interface's offset on the way back
        # out, so what is stored is the remapped times less that offset.
        self._times = remapped_times - self._alignment.offset


class _TemporalAlignment:
    """The alignment surface for an interface's time-bearing objects, exposed as ``interface.alignment``.

    Carries the interface-wide offset, ``output = native + offset``, default ``0.0`` (identity), and names the
    objects the interface registered. ``shift_times`` positions the whole interface, so it takes no key, and
    ``remap_times`` is one clock's correction, so it applies to every object. Times for one object are given
    through the object itself: ``alignment[key].set_times(times)``.
    """

    def __init__(self):
        self._offset = 0.0
        self._name_to_time_bearing_object: dict[str, _TimeBearingSeries] = {}

    def _register_series(self, *, key: str, get_native_times) -> _TimeBearingSeries:
        """Name one series-shaped time-bearing object. Called by the interface, not by a user."""
        time_bearing_object = _TimeBearingSeries(get_native_times=get_native_times, alignment=self)
        self._name_to_time_bearing_object[key] = time_bearing_object
        return time_bearing_object

    @property
    def offset(self) -> float:
        """The current offset, in seconds, added to every one of the interface's time-bearing objects."""
        return self._offset

    def keys(self) -> tuple[str, ...]:
        """The time-bearing objects this interface can name, empty when it names none."""
        return tuple(self._name_to_time_bearing_object)

    def __getitem__(self, key: str) -> _TimeBearingSeries:
        if key not in self._name_to_time_bearing_object:
            named = ", ".join(repr(name) for name in self._name_to_time_bearing_object) or "nothing"
            raise KeyError(f"{key!r} is not a time-bearing object of this interface. It names {named}.")
        return self._name_to_time_bearing_object[key]

    def __contains__(self, key: str) -> bool:
        return key in self._name_to_time_bearing_object

    def __iter__(self) -> Iterator[str]:
        return iter(self._name_to_time_bearing_object)

    def __len__(self) -> int:
        return len(self._name_to_time_bearing_object)

    def shift_times(self, delta: float) -> None:
        """Shift every time-bearing object in the interface by ``delta`` seconds (relative, accumulates)."""
        self._offset += float(delta)

    def remap_times(self, *, local_sync_times, reference_sync_times) -> None:
        """Re-express every time-bearing object on a reference clock through synchronization pulses.

        One acquisition clock means one correction, so this needs no key. See
        :meth:`_TimeBearingSeries.remap_times`.
        """
        for time_bearing_object in self._name_to_time_bearing_object.values():
            time_bearing_object.remap_times(
                local_sync_times=local_sync_times, reference_sync_times=reference_sync_times
            )
