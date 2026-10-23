import re

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal

from neuroconv._temporal_alignment import _TemporalAlignment
from neuroconv.tools.testing._temporal_alignment_rules import _TemporalAlignmentRulesTestMixin


class TestTimeBearingObjectRules(_TemporalAlignmentRulesTestMixin):
    """The shared rules, run on ``_TimeBearingObject``, which keeps the alignment in its own fields."""

    @pytest.fixture
    def alignment(self):
        native_times = {
            "a": np.array([0.0, 0.1, 0.2, 0.3, 0.4]),
            "b": np.array([2.0, 2.1, 2.2]),
        }
        alignment = _TemporalAlignment()
        alignment._register(key="a", get_native_times=lambda: native_times["a"])
        alignment._register(key="b", get_native_times=lambda: native_times["b"])
        return alignment


class TestObjectAlignment:
    def test_native_times_are_never_mutated(self):
        """Check that alignment operations and timestamp reads leave the source arrays unchanged."""
        native_times = np.array([0.0, 0.1, 0.2])
        original_times = native_times.copy()
        alignment = _TemporalAlignment()
        alignment._register(key="a", get_native_times=lambda: native_times)

        alignment.shift_times(1.0)
        alignment["a"].get_times()
        assert_array_equal(native_times, original_times)

        alignment["a"].move_start_to(10.0)
        alignment["a"].get_times()
        assert_array_equal(native_times, original_times)

        alignment["a"].remap_times(local_sync_times=[10.0, 11.0], reference_sync_times=[20.0, 22.0])
        alignment["a"].get_times()
        assert_array_equal(native_times, original_times)

        alignment["a"].set_times([30, 31, 32])
        alignment["a"].get_times()
        assert_array_equal(native_times, original_times)


class TestAlignmentEdgeCases:
    def test_empty_alignment_rejects_operations(self):
        """Check that shifting, placement, and remapping are rejected when no objects are registered."""
        alignment = _TemporalAlignment()
        with pytest.raises(
            NotImplementedError,
            match="This interface has registered no time-bearing objects, so there is nothing to shift",
        ):
            alignment.shift_times(1.0)

        with pytest.raises(
            NotImplementedError,
            match="This interface has registered no time-bearing objects, so it has no start to move",
        ):
            alignment.move_start_to(0.0)

        with pytest.raises(
            NotImplementedError,
            match="This interface has registered no time-bearing objects, so there is nothing to remap",
        ):
            alignment.remap_times(local_sync_times=[0, 1], reference_sync_times=[0, 1])


class TestEventsAlignment:
    @pytest.fixture
    def events_alignment(self):
        alignment = _TemporalAlignment()
        alignment._register(
            key="e",
            get_native_times=lambda: np.array([1.0, 4.0, 5.0]),
            get_number_of_samples=lambda: 3,
            get_native_durations=lambda: np.array([2.0, 0.5, np.nan]),
        )
        return alignment

    def test_shift_moves_onsets_and_keeps_durations(self, events_alignment):
        """Check that a rigid shift moves the onsets and leaves every duration, including a missing one."""
        events_alignment.shift_times(10.0)

        assert_allclose(events_alignment["e"].get_times(), [11.0, 14.0, 15.0])
        assert_allclose(events_alignment["e"].get_durations(), [2.0, 0.5, np.nan])

    def test_set_times_replaces_onsets_and_keeps_durations(self, events_alignment):
        """Check that replacement onsets are written as given and the durations are not touched."""
        events_alignment["e"].set_times([20.0, 30.0, 50.0])

        assert_allclose(events_alignment["e"].get_times(), [20.0, 30.0, 50.0])
        assert_allclose(events_alignment["e"].get_durations(), [2.0, 0.5, np.nan])

    def test_set_times_needs_one_onset_per_event(self, events_alignment):
        """Check that replacement onsets with the wrong count are rejected."""
        message = "This object has 3 samples, but 2 times were given. `set_times` needs one time per sample."
        with pytest.raises(ValueError, match=re.escape(message)):
            events_alignment["e"].set_times([1.0, 2.0])

    def test_remap_times_recomputes_durations_through_the_map(self, events_alignment):
        """Check that remapping against a clock running at twice the rate doubles the durations and keeps a missing one."""
        events_alignment.remap_times(local_sync_times=[0.0, 10.0], reference_sync_times=[0.0, 20.0])

        assert_allclose(events_alignment["e"].get_times(), [2.0, 8.0, 10.0])
        assert_allclose(events_alignment["e"].get_durations(), [4.0, 1.0, np.nan])

    def test_remap_times_after_a_shift_uses_the_shifted_onsets(self, events_alignment):
        """Check that a duration is remapped from where its interval currently sits, a shift applied earlier included."""
        events_alignment.shift_times(1.0)
        events_alignment.remap_times(local_sync_times=[0.0, 10.0], reference_sync_times=[0.0, 20.0])

        assert_allclose(events_alignment["e"].get_times(), [4.0, 10.0, 12.0])
        assert_allclose(events_alignment["e"].get_durations(), [4.0, 1.0, np.nan])

    def test_a_type_without_durations_has_none(self):
        """Check that an event type registered without durations reports none before and after remapping."""
        alignment = _TemporalAlignment()
        alignment._register(key="e", get_native_times=lambda: np.array([1.0, 2.0]))

        assert alignment["e"].get_durations() is None

        alignment.remap_times(local_sync_times=[0.0, 10.0], reference_sync_times=[0.0, 20.0])

        assert_allclose(alignment["e"].get_times(), [2.0, 4.0])
        assert alignment["e"].get_durations() is None
