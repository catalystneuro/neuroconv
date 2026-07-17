"""Data-free unit tests for the Inscopix GPIO events derivation.

These exercise the pure ``_derive_events`` function on synthetic change-point arrays (opening sample,
changes, closing sample), so they need neither pyisx nor the ``.gpio`` fixture. End-to-end behavior on
the real file is covered in ``tests/test_on_data/events``.
"""

import numpy as np
import pytest

from neuroconv.datainterfaces.events.inscopix_gpio_events.inscopixgpioeventsdatainterface import (
    _derive_events,
)


def _derive(entry, times, amps):
    return _derive_events(
        "channel",
        entry,
        np.asarray(times, dtype="float64"),
        np.asarray(amps, dtype="float64"),
    )


class TestReadingsOnADigitalLine:
    # Opening sample at t=0 (low), then two pulses. Like a change-point-stored 0/1 line.
    times = [0.0, 1.0, 2.0, 3.0, 4.0]
    amps = [0.0, 1.0, 0.0, 1.0, 0.0]

    def test_changes_keeps_every_transition_with_value(self):
        event = _derive({"reading": "changes"}, self.times, self.amps)
        assert event.timestamps.tolist() == [1.0, 2.0, 3.0, 4.0]
        assert event.payload["value"].tolist() == [1.0, 0.0, 1.0, 0.0]
        assert event.durations is None

    def test_rising_is_timestamp_only(self):
        event = _derive({"reading": "rising"}, self.times, self.amps)
        assert event.timestamps.tolist() == [1.0, 3.0]  # the 0->1 transitions
        assert event.payload == {}  # raw line + directional reading -> no value column

    def test_falling(self):
        event = _derive({"reading": "falling"}, self.times, self.amps)
        assert event.timestamps.tolist() == [2.0, 4.0]

    def test_interval_pairs_rise_with_next_fall(self):
        event = _derive({"reading": "interval"}, self.times, self.amps)
        assert event.timestamps.tolist() == [1.0, 3.0]
        assert event.durations.tolist() == [1.0, 1.0]

    def test_default_reading_is_changes(self):
        event = _derive({}, self.times, self.amps)
        assert event.timestamps.tolist() == [1.0, 2.0, 3.0, 4.0]


def test_opening_and_closing_boundary_samples_are_not_events():
    # (0, 0) opening, one real change to 1, then a closing sample repeating the held value 1.
    event = _derive({"reading": "changes"}, [0.0, 5.0, 10.0], [0.0, 1.0, 1.0])
    assert event.timestamps.tolist() == [5.0]  # only the real change; opening and closing repeat dropped


def test_rising_works_on_a_nonzero_baseline_line():
    # A 48/64 line: "rising" must mean "value increased", not "amplitude > 0" (which would call all high).
    event = _derive({"reading": "rising"}, [0.0, 1.0, 2.0, 3.0], [48.0, 64.0, 48.0, 64.0])
    assert event.timestamps.tolist() == [1.0, 3.0]  # the 48->64 increases


class TestLevels:
    def test_bands_and_categorical_value(self):
        # digitize([0,100,200,0], [50,150]) -> bands [0,1,2,0]; a coded line always carries its band.
        event = _derive(
            {"levels": [50, 150], "field": "concentration"},
            [0.0, 1.0, 2.0, 3.0],
            [0.0, 100.0, 200.0, 0.0],
        )
        assert event.timestamps.tolist() == [1.0, 2.0, 3.0]
        assert event.payload["concentration"].tolist() == [1, 2, 0]

    def test_rising_on_a_coded_line_keeps_the_band(self):
        event = _derive(
            {"levels": [50, 150], "reading": "rising"},
            [0.0, 1.0, 2.0],
            [0.0, 100.0, 200.0],
        )
        assert event.timestamps.tolist() == [1.0, 2.0]  # band went 0->1 then 1->2
        assert event.payload["value"].tolist() == [1, 2]


def test_flat_channel_yields_none():
    assert _derive({"reading": "changes"}, [0.0, 1.0], [5.0, 5.0]) is None


def test_invalid_reading_raises():
    with pytest.raises(ValueError, match="Invalid reading"):
        _derive({"reading": "both"}, [0.0, 1.0], [0.0, 1.0])
