import re
from functools import partial

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal

from neuroconv._temporal_alignment import _TemporalAlignment


@pytest.fixture
def alignment():
    native_times = {
        "a": np.array([0.0, 0.1, 0.2, 0.3, 0.4]),
        "b": np.array([2.0, 2.1, 2.2]),
    }
    alignment = _TemporalAlignment()
    alignment._register_series(key="a", get_native_times=lambda: native_times["a"])
    alignment._register_series(key="b", get_native_times=lambda: native_times["b"])
    return alignment


class TestObjectAlignment:
    def test_object_shift_times_moves_that_object_alone(self, alignment):
        """Check that shifting one object leaves the other object unchanged."""
        alignment["a"].shift_times(1.0)

        assert_allclose(alignment["a"].get_times(), [1.0, 1.1, 1.2, 1.3, 1.4])
        assert_allclose(alignment["b"].get_times(), [2.0, 2.1, 2.2])

    def test_set_times_supersedes_earlier_shifts_and_accepts_later_shifts(self, alignment):
        """Check that replacement timestamps discard an earlier shift but still accept later shifts."""
        alignment.shift_times(5.0)
        alignment["a"].set_times([10, 11, 12, 13, 14])

        assert_allclose(alignment["a"].get_times(), [10, 11, 12, 13, 14])
        assert_allclose(alignment["b"].get_times(), [7.0, 7.1, 7.2])

        alignment.shift_times(1.0)

        assert_allclose(alignment["a"].get_times(), [11, 12, 13, 14, 15])
        assert_allclose(alignment["b"].get_times(), [8.0, 8.1, 8.2])

    def test_object_move_start_to_is_absolute_and_idempotent(self, alignment):
        """Check that placement overrides an earlier shift and repeating it changes nothing. Later shifts still apply."""
        alignment["a"].shift_times(3.0)
        alignment["a"].move_start_to(100.0)

        assert_allclose(alignment["a"].get_times(), [100.0, 100.1, 100.2, 100.3, 100.4])
        assert_allclose(alignment["b"].get_times(), [2.0, 2.1, 2.2])

        alignment["a"].move_start_to(100.0)

        assert_allclose(alignment["a"].get_times(), [100.0, 100.1, 100.2, 100.3, 100.4])

        alignment["a"].shift_times(1.0)

        assert_allclose(alignment["a"].get_times(), [101.0, 101.1, 101.2, 101.3, 101.4])

    def test_move_start_to_and_set_times_respect_operation_order(self, alignment):
        """Check that replacement overrides placement and a later placement preserves replacement spacing."""
        alignment["a"].move_start_to(100.0)
        alignment["a"].set_times([10, 11, 13, 16, 20])

        assert_allclose(alignment["a"].get_times(), [10, 11, 13, 16, 20])

        alignment["a"].move_start_to(100.0)

        assert_allclose(alignment["a"].get_times(), [100, 101, 103, 106, 110])

    def test_object_remap_times_uses_current_times_and_accepts_later_shifts(self, alignment):
        """Remap the selected object's shifted times, leave the other object unchanged, and allow later shifts."""
        alignment["a"].shift_times(1.0)
        alignment["a"].remap_times(local_sync_times=[1.0, 2.0], reference_sync_times=[10.0, 12.0])

        assert_allclose(alignment["a"].get_times(), [10.0, 10.2, 10.4, 10.6, 10.8])
        assert_allclose(alignment["b"].get_times(), [2.0, 2.1, 2.2])

        alignment["a"].shift_times(1.0)

        assert_allclose(alignment["a"].get_times(), [11.0, 11.2, 11.4, 11.6, 11.8])

    def test_remap_times_reads_the_replacement_times(self, alignment):
        """Check that remapping operates on replacement timestamps when present."""
        alignment["a"].set_times([10, 11, 12, 13, 14])
        alignment["a"].remap_times(local_sync_times=[10.0, 14.0], reference_sync_times=[20.0, 28.0])

        assert_allclose(alignment["a"].get_times(), [20, 22, 24, 26, 28])

    def test_remap_times_uses_custom_interpolation(self, alignment):
        """Check the timestamps and pulses passed to custom interpolation and that its result is used."""

        def interpolate(times, local_sync_times, reference_sync_times):
            assert_allclose(times, [0.0, 0.1, 0.2, 0.3, 0.4])
            assert_allclose(local_sync_times, [0.0, 1.0])
            assert_allclose(reference_sync_times, [10.0, 12.0])
            return times + 100.0

        alignment["a"].remap_times(
            local_sync_times=[0.0, 1.0],
            reference_sync_times=[10.0, 12.0],
            interpolation_function=interpolate,
        )

        assert_allclose(alignment["a"].get_times(), [100.0, 100.1, 100.2, 100.3, 100.4])

    def test_native_times_are_never_mutated(self):
        """Check that alignment operations and timestamp reads leave the source arrays unchanged."""
        native_times = np.array([0.0, 0.1, 0.2])
        original_times = native_times.copy()
        alignment = _TemporalAlignment()
        alignment._register_series(key="a", get_native_times=lambda: native_times)

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


class TestInterfaceAlignment:
    def test_registered_objects_are_accessible_by_key(self, alignment):
        """Check key order, initial timestamps, and the error for an unknown key."""
        assert alignment.keys() == ("a", "b")
        assert_allclose(alignment["a"].get_times(), [0.0, 0.1, 0.2, 0.3, 0.4])
        assert_allclose(alignment["b"].get_times(), [2.0, 2.1, 2.2])

        message = "'missing' is not a time-bearing object of this interface. It names 'a', 'b'."
        with pytest.raises(KeyError, match=re.escape(message)):
            alignment["missing"]

    def test_interface_shift_times_accumulates_for_every_object(self, alignment):
        """Check that a shift reaches both registered objects and successive shifts add together."""
        alignment.shift_times(1.0)

        assert_allclose(alignment["a"].get_times(), [1.0, 1.1, 1.2, 1.3, 1.4])
        assert_allclose(alignment["b"].get_times(), [3.0, 3.1, 3.2])

        alignment.shift_times(0.5)

        assert_allclose(alignment["a"].get_times(), [1.5, 1.6, 1.7, 1.8, 1.9])
        assert_allclose(alignment["b"].get_times(), [3.5, 3.6, 3.7])

    def test_interface_move_start_to_preserves_current_relative_placement(self, alignment):
        """Check that placement preserves current relative times and is unchanged when repeated."""
        alignment["a"].shift_times(3.0)
        alignment.move_start_to(100.0)

        assert_allclose(alignment["a"].get_times(), [101.0, 101.1, 101.2, 101.3, 101.4])
        assert_allclose(alignment["b"].get_times(), [100.0, 100.1, 100.2])

        alignment.move_start_to(100.0)

        assert_allclose(alignment["a"].get_times(), [101.0, 101.1, 101.2, 101.3, 101.4])
        assert_allclose(alignment["b"].get_times(), [100.0, 100.1, 100.2])

    def test_interface_remap_times_reaches_every_object(self, alignment):
        """Check that remapping reaches both objects and clamps timestamps beyond the last synchronization pulse."""
        alignment.remap_times(local_sync_times=[0.0, 1.0], reference_sync_times=[10.0, 12.0])

        assert_allclose(alignment["a"].get_times(), [10.0, 10.2, 10.4, 10.6, 10.8])
        assert_allclose(alignment["b"].get_times(), [12.0, 12.0, 12.0])


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

    @pytest.mark.parametrize("starting_time", [np.nan, np.inf, -np.inf])
    @pytest.mark.parametrize("scope", ["object", "interface"])
    def test_move_start_to_needs_a_finite_time(self, alignment, starting_time, scope):
        """Check that nonfinite placement targets are rejected at both object and interface scopes."""
        target = alignment["a"] if scope == "object" else alignment
        message = f"`move_start_to` needs a finite time in seconds, not {starting_time}."
        with pytest.raises(ValueError, match=re.escape(message)):
            target.move_start_to(starting_time)

    def test_interface_move_start_to_rejects_a_nonfinite_start_without_moving_objects(self, alignment):
        """Check that a start remapped to NaN is rejected before any object's timestamps change."""
        alignment["b"].remap_times(
            local_sync_times=[2.1, 2.2],
            reference_sync_times=[2.1, 2.2],
            interpolation_function=partial(np.interp, left=np.nan, right=np.nan),
        )

        with pytest.raises(ValueError, match="'b' has no finite first time to place by"):
            alignment.move_start_to(100.0)

        assert_allclose(alignment["a"].get_times(), [0.0, 0.1, 0.2, 0.3, 0.4])
        assert_allclose(alignment["b"].get_times(), [np.nan, 2.1, 2.2])

    def test_remap_times_needs_paired_pulses(self, alignment):
        """Check that synchronization arrays with different pulse counts are rejected."""
        message = "The synchronization pulses have to pair up: `local_sync_times` has 2 of them and `reference_sync_times` has 3."
        with pytest.raises(ValueError, match=re.escape(message)):
            alignment["a"].remap_times(local_sync_times=[0, 1], reference_sync_times=[0, 1, 2])


class TestEventsAlignment:
    @pytest.fixture
    def events_alignment(self):
        alignment = _TemporalAlignment()
        alignment._register_events(
            key="e",
            get_native_times=lambda: np.array([1.0, 4.0, 5.0]),
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
        message = "`set_times` needs one onset per event: this event type has 3 events and 2 times were given."
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
        alignment._register_events(key="e", get_native_times=lambda: np.array([1.0, 2.0]))

        assert alignment["e"].get_durations() is None

        alignment.remap_times(local_sync_times=[0.0, 10.0], reference_sync_times=[0.0, 20.0])

        assert_allclose(alignment["e"].get_times(), [2.0, 4.0])
        assert alignment["e"].get_durations() is None
