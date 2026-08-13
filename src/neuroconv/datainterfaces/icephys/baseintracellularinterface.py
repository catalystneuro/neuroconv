"""Shared base for the intracellular interfaces that write one ``PatchClampSeries`` per electrode."""

import numpy as np

from ..._temporal_alignment import _TemporalAlignment
from ...basedatainterface import BaseDataInterface

__all__ = ["BaseIntracellularInterface"]


class BaseIntracellularInterface(BaseDataInterface):
    """Base class for the intracellular interfaces reading a format directly (Axon, Bruker VoltageRecording).

    Distinct from :class:`~neuroconv.datainterfaces.icephys.baseicephysinterface.BaseIcephysInterface`, which is
    the older Neo-extractor path that ``AbfInterface`` still uses. What lives here is what the direct readers
    share about time, since each of them writes its series on the clock its own file states and needs the same two
    things to put that on a session timeline.

    There is one offset, reached as ``interface.alignment.shift_times(delta)``, the same surface the events and
    fiber photometry interfaces carry. A converter combining several files uses it too: it resolves the files
    against each other, which a lone interface cannot do, and shifts each one onto the shared timeline through
    the same public method. A user shifting afterwards moves that placed block as a whole, since the offset
    accumulates. It is applied at write, so the times the reader stated are never mutated.
    """

    def __init__(self, *, verbose: bool = False, **source_data):
        super().__init__(verbose=verbose, **source_data)
        self.alignment = _TemporalAlignment()

    def _align_timestamps(self, timestamps: np.ndarray) -> np.ndarray:
        """Return ``timestamps`` placed on the session timeline, ready to be written."""
        return timestamps + self.alignment.offset
