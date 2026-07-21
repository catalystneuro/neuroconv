"""Temporal-alignment machinery, held by interfaces via composition and exposed as ``interface.alignment``.

This is intentionally minimal: it currently holds only the offset applied to an interface's time-bearing
objects at write time, reached through ``interface.alignment.shift_times``. It is the designated home for the
addressable object map and the per-object set/interpolate operations once a concrete need for them appears;
until then it stays a plain offset holder. Only ``interface.alignment.shift_times`` is a stable contract;
everything else here may change.
"""


class _TemporalAlignment:
    """The alignment surface for an interface's time-bearing objects, exposed as ``interface.alignment``.

    It holds a single offset added to the objects' native times: ``output = native + offset``, default
    ``0.0`` (identity). The native times are never mutated; the offset is applied by the interface at write
    time. ``shift_times`` is relative and accumulates.
    """

    def __init__(self):
        self._offset = 0.0

    @property
    def offset(self) -> float:
        """The current offset, in seconds, added to the interface's time-bearing objects at write."""
        return self._offset

    def shift_times(self, delta: float) -> None:
        """Shift every time-bearing object in the interface by ``delta`` seconds (relative, accumulates)."""
        self._offset += float(delta)
