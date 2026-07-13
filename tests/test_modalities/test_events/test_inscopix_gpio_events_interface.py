"""Data-free unit tests for the Inscopix GPIO events derivation logic.

These exercise the pure ``_derive_digital`` / ``_derive_coded_analog`` static methods directly on
synthetic change-event arrays, so they need neither pyisx nor the ``.gpio`` fixture. The end-to-end
behavior against the real file is covered in ``tests/test_on_data/events``.
"""

import numpy as np
import pytest

from neuroconv.datainterfaces import InscopixGpioEventsInterface as Interface


class TestDeriveDigital:
    # A line that rests at 0 and pulses high twice: change-events land on 1 (rising) then 0 (falling).
    timestamps = np.array([1.0, 1.5, 2.0, 2.5])
    amplitudes = np.array([1.0, 0.0, 1.0, 0.0])

    def test_rising(self):
        event = Interface._derive_digital("line", {"reading": "rising"}, self.timestamps, self.amplitudes)
        assert event.timestamps.tolist() == [1.0, 2.0]
        assert event.durations is None
        assert event.payload == {}

    def test_falling(self):
        event = Interface._derive_digital("line", {"reading": "falling"}, self.timestamps, self.amplitudes)
        assert event.timestamps.tolist() == [1.5, 2.5]
        assert event.durations is None

    def test_interval_pairs_rising_with_next_falling(self):
        event = Interface._derive_digital("line", {"reading": "interval"}, self.timestamps, self.amplitudes)
        assert event.timestamps.tolist() == [1.0, 2.0]
        assert event.durations.tolist() == [0.5, 0.5]

    def test_default_reading_is_rising(self):
        event = Interface._derive_digital("line", {}, self.timestamps, self.amplitudes)
        assert event.timestamps.tolist() == [1.0, 2.0]

    def test_interval_unclosed_final_high_is_nan(self):
        # Ends high with no later falling edge: that interval's duration is a missing value (NaN).
        timestamps = np.array([1.0, 1.5, 2.0])
        amplitudes = np.array([1.0, 0.0, 1.0])
        event = Interface._derive_digital("line", {"reading": "interval"}, timestamps, amplitudes)
        assert event.timestamps.tolist() == [1.0, 2.0]
        assert event.durations[0] == 0.5
        assert np.isnan(event.durations[1])

    def test_never_toggling_line_yields_none(self):
        event = Interface._derive_digital("line", {"reading": "rising"}, np.array([0.0, 1.0]), np.array([0.0, 0.0]))
        assert event is None

    def test_invalid_reading_raises(self):
        with pytest.raises(ValueError, match="Invalid reading"):
            Interface._derive_digital("line", {"reading": "both"}, self.timestamps, self.amplitudes)


class TestDeriveCodedAnalog:
    def test_bands_and_change_points(self):
        # Levels cut the trace into 4 bands; an event is emitted at the first sample and each band change.
        timestamps = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        amplitudes = np.array([0.0, 100.0, 200.0, 200.0, 0.0, 150.0])
        event = Interface._derive_coded_analog(
            "GPIO-2",
            {"levels": [50, 120, 180], "field": "concentration"},
            timestamps,
            amplitudes,
        )
        # digitize -> [0,1,3,3,0,2]; the repeated 3 collapses, so events are at indices 0,1,2,4,5.
        assert event.timestamps.tolist() == [0.0, 1.0, 2.0, 4.0, 5.0]
        assert event.payload["concentration"].tolist() == [0, 1, 3, 0, 2]

    def test_field_defaults_to_value(self):
        event = Interface._derive_coded_analog("c", {"levels": [1.0]}, np.array([0.0, 1.0]), np.array([0.0, 2.0]))
        assert set(event.payload) == {"value"}
