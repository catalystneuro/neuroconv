"""On-data tests for the pyPhotometry converter.

A ``.ppd`` file carries its fluorescence and its digital lines in the same words, so converting one
whole means one fiber photometry interface per signal plus one events interface for the lines. What the
converter owns beyond wiring them up is the naming, since every single-series interface calls its series
``FiberPhotometryResponseSeries`` and a file holding several of them needs each named apart.

One class per recording, as the interface tests are organized: a two-input recording, whose signals and
lines pair off one to one, and the four-colour fork, whose two inputs each multiplex two colours so that
a name has to carry the colour as well as the slot.

Assertions are made on the in-memory file ``create_nwbfile`` builds, which starts from the metadata the
converter supplies for itself and so covers the session start time the header states. Serialization is
pynwb's business, and each sub-interface round-trips to disk on its own elsewhere.
"""

from datetime import datetime

import pytest

from neuroconv.converters import PyPhotometryConverter

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH

PYPHOTOMETRY_PATH = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "pyphotometry"


class TestPyPhotometryConverter:
    """A two-input recording converted whole: a series per signal, a table per line."""

    file_path = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "two_colour_time_division.ppd"

    def test_get_available_streams(self):
        """Signals first, then lines, each in the order the words interleave them."""
        assert PyPhotometryConverter.get_available_streams(file_path=self.file_path) == [
            "detector_1_excitation_1",
            "detector_2_excitation_2",
            "digital_1",
            "digital_2",
        ]

    def test_conversion(self):
        """The whole file in one call: named apart, timed by slot, dated from the header."""
        nwbfile = PyPhotometryConverter(file_path=self.file_path).create_nwbfile()

        assert set(nwbfile.acquisition) == {
            "FiberPhotometryResponseSeriesDetector1Excitation1",
            "FiberPhotometryResponseSeriesDetector2Excitation2",
        }
        assert set(nwbfile.events) == {"Digital1", "Digital2"}
        # Nothing was passed in, so the session start time is the one the header states.
        assert nwbfile.session_start_time.replace(tzinfo=None) == datetime(2019, 5, 6, 12, 17, 0)
        # The converter changes no timing: the second signal is still a tick of the 260 Hz timer behind.
        assert nwbfile.acquisition["FiberPhotometryResponseSeriesDetector1Excitation1"].starting_time == 0.0
        assert nwbfile.acquisition["FiberPhotometryResponseSeriesDetector2Excitation2"].starting_time == pytest.approx(
            1 / 260
        )


class TestPyPhotometryForkIsRefused:
    """The fork's mode reaches the converter through the same reader, so it is refused there too."""

    file_path = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "four_colour_time_division.ppd"

    def test_the_fork_is_refused_by_name(self):
        with pytest.raises(ValueError, match="Wiegert-lab fork of the pyPhotometry acquisition software"):
            PyPhotometryConverter(file_path=self.file_path)
