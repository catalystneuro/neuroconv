"""Temporal-alignment machinery, held by interfaces via composition and exposed as ``interface.alignment``.

An interface's alignment surface is a container. It carries the whole-interface offset, and it names the
interface's **time-bearing objects**, the things it writes that carry a time coordinate, so that a single one
can be reached and re-timed on its own::

    interface.alignment.shift_times(3.0)                   # every object, rigid, accumulates
    interface.alignment.keys()                             # the objects this interface can name
    interface.alignment["response"].set_times(times)       # this object's times outright
    interface.alignment["response"].remap_times(...)       # this object's clock against a reference

An interface that names nothing still shifts: registration is what a keyed operation needs, and the events
interfaces register nothing because enumerating their event types means reading the source. The units are
split by shape because the operations are: a series has one sample axis and takes all three operations, while
a table is timestamps plus durations and cannot take ``set_times`` at all, since there is no single array to
hand it. Only the series-shaped unit exists here so far.
"""

from collections.abc import Iterator

import numpy as np


class _TimeSeriesAlignment:
    """The alignment of one series-shaped time-bearing object, reached as ``interface.alignment[key]``.

    Holds what re-times this object and nothing else: an optional replacement for its times, and an offset of
    its own. The source times are never mutated, so what is written is
    ``(replacement or native) + own offset + the interface's offset``, the last of which is added by the
    container.
    """

    def __init__(self, *, get_native_times):
        # A callable rather than an array, so an interface registers its objects without reading its source.
        self._get_native_times = get_native_times
        self._times: np.ndarray | None = None
        self._offset = 0.0

    @property
    def offset(self) -> float:
        """The offset, in seconds, this object carries on its own, before the interface's own offset."""
        return self._offset

    def get_times(self) -> np.ndarray:
        """Return this object's times as they stand, without the interface-wide offset."""
        times = self._times if self._times is not None else np.asarray(self._get_native_times())
        return times + self._offset

    def set_times(self, times) -> None:
        """Replace this object's times with the ones given.

        For per-sample times you already trust, from a synchronization signal or a computation of your own.
        The interface's own offset still applies on top, since that positions the whole interface and this
        positions one object inside it.
        """
        self._times = np.asarray(times)
        self._offset = 0.0

    def shift_times(self, delta: float) -> None:
        """Shift this object alone by ``delta`` seconds (relative, accumulates).

        This breaks the relationship between this object and its siblings, which the interface-wide shift is
        there to protect, so it is for a deliberate single-object correction (a cable latency on one stream)
        rather than for placing an interface.
        """
        self._offset += float(delta)

    def remap_times(self, *, stream_sync_times, reference_sync_times) -> None:
        """Re-express this object's times on a reference clock through synchronization pulses.

        ``stream_sync_times`` are the pulses as this object's own clock recorded them and
        ``reference_sync_times`` are the same pulses on the clock being aligned to. Times between pulses are
        interpolated. Use this when the two clocks drift, so no single shift lines them up.
        """
        stream_sync_times = np.asarray(stream_sync_times)
        reference_sync_times = np.asarray(reference_sync_times)
        if stream_sync_times.shape != reference_sync_times.shape:
            raise ValueError(
                "The synchronization pulses have to pair up: `stream_sync_times` has "
                f"{stream_sync_times.size} of them and `reference_sync_times` has {reference_sync_times.size}."
            )
        self._times = np.interp(self.get_times(), stream_sync_times, reference_sync_times)
        self._offset = 0.0


class _TemporalAlignment:
    """The alignment surface for an interface's time-bearing objects, exposed as ``interface.alignment``.

    Carries the interface-wide offset, ``output = native + offset``, default ``0.0`` (identity), and names the
    objects the interface registered. ``shift_times`` and ``remap_times`` need no key, as one correction
    applies to every object; ``set_times`` is per-object literal values, so it needs one unless the interface
    has exactly one object to mean.
    """

    def __init__(self):
        self._offset = 0.0
        self._objects: dict[str, _TimeSeriesAlignment] = {}

    def _register_series(self, *, key: str, get_native_times) -> _TimeSeriesAlignment:
        """Name one series-shaped time-bearing object. Called by the interface, not by a user."""
        alignment = _TimeSeriesAlignment(get_native_times=get_native_times)
        self._objects[key] = alignment
        return alignment

    @property
    def offset(self) -> float:
        """The current offset, in seconds, added to every one of the interface's time-bearing objects."""
        return self._offset

    def keys(self) -> tuple[str, ...]:
        """The time-bearing objects this interface can name, empty when it names none."""
        return tuple(self._objects)

    def __getitem__(self, key: str) -> _TimeSeriesAlignment:
        if key not in self._objects:
            named = ", ".join(repr(name) for name in self._objects) or "nothing"
            raise KeyError(f"{key!r} is not a time-bearing object of this interface. It names {named}.")
        return self._objects[key]

    def __contains__(self, key: str) -> bool:
        return key in self._objects

    def __iter__(self) -> Iterator[str]:
        return iter(self._objects)

    def __len__(self) -> int:
        return len(self._objects)

    def shift_times(self, delta: float) -> None:
        """Shift every time-bearing object in the interface by ``delta`` seconds (relative, accumulates)."""
        self._offset += float(delta)

    def set_times(self, times) -> None:
        """Replace the times of this interface's single time-bearing object.

        Literal per-sample values belong to one object, so this is only keyless where there is one object to
        mean. With several, name it: ``interface.alignment[key].set_times(times)``.
        """
        if len(self._objects) != 1:
            named = ", ".join(repr(name) for name in self._objects) or "none"
            raise ValueError(
                "`set_times` writes the times of one object, so it can only be called without a key on an "
                f"interface that has exactly one. This one names {named}. Reach the object you mean with "
                "`alignment[key].set_times(times)`."
            )
        (single_object,) = self._objects.values()
        single_object.set_times(times)

    def remap_times(self, *, stream_sync_times, reference_sync_times) -> None:
        """Re-express every time-bearing object on a reference clock through synchronization pulses.

        One acquisition clock means one correction, so this needs no key. See
        :meth:`_TimeSeriesAlignment.remap_times`.
        """
        for single_object in self._objects.values():
            single_object.remap_times(stream_sync_times=stream_sync_times, reference_sync_times=reference_sync_times)

    def _get_times(self, key: str) -> np.ndarray:
        """Return the times that will be written for one object, the interface's offset included."""
        return self[key].get_times() + self._offset
