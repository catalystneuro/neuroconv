"""Private temporal-alignment machinery, held by interfaces via composition.

This is intentionally minimal and **private** (unstable): it currently holds only the offset applied to an
interface's time-bearing objects at write time, and exposes it through the interface's ``shift_times`` method.
It is the designated home for the addressable object map and the per-object set/interpolate operations once a
concrete need for them appears; until then it stays a plain offset holder. Only the public ``shift_times`` on
the interface is a stable contract; everything here may change.
"""


class _TemporalAlignment:
    """Alignment state for an interface's time-bearing objects: an offset added to their native times.

    ``output = native + offset``, default ``0.0`` (identity). The native times are never mutated; the offset
    is applied by the interface at write time. ``shift`` is relative and accumulates.
    """

    def __init__(self):
        self._offset = 0.0

    @property
    def offset(self) -> float:
        """The current offset, in seconds, added to the interface's time-bearing objects at write."""
        return self._offset

    def shift(self, delta: float) -> None:
        """Add ``delta`` seconds to the offset (relative, accumulates)."""
        self._offset += float(delta)
