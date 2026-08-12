"""On-data tests for the pyPhotometry fiber photometry interface.

A ``.ppd`` file holds every signal the board recorded interleaved word by word, and nothing in it says
how to separate them except the header's ``mode`` field, whose spelling changed across four header
generations. The recordings under ``fiber_photometry_datasets/pyphotometry`` are one per generation, and
this module is organized to match, one round-trip class per recording and signal:

- ``mode_named_symbolically`` -- the current vocabulary, ``2EX_2EM_pulsed``, header version 1.0, the only
  generation whose header states its signal counts.
- ``mode_named_in_prose`` -- versions 0.2 and 0.3, where the mode describes the acquisition in words:
  ``1 colour time div.``, ``2 colour time div.``, ``2 colour continuous``, and the four-colour fork whose
  analog lines each multiplex two colours.
- ``mode_named_by_indicators`` -- version 0.1, where the mode names the fluorophores.
- ``header_predates_json`` -- the fixed-layout header, whose mode is an unpublished byte code.

What the round trips assert beyond reading at all is timing. The board samples its analog inputs one
after another, so each signal is written with the start time its slot implies, where the vendor's reader
reports every signal as starting at zero. Classes come in pairs where that matters, one per signal, so
the second one's ``expected_starting_time`` is the claim.

Each expected trace is the leading samples of that signal, read off the file by hand rather than through
the interface, with ``stub_samples`` keeping them short. Construction errors, which the mixin cannot
express, live in a dedicated plain class. The version 1.1 paired path and the refusals for malformed
headers are in ``tests/test_modalities/test_fiber_photometry/test_pyphotometry.py``, since no recording
of that version exists and a broken header has to be built.
"""

from datetime import datetime

import numpy as np
import pytest

from neuroconv.datainterfaces import PyPhotometryFiberPhotometryInterface
from neuroconv.tools.testing.data_interface_mixins import (
    FiberPhotometryInterfaceTestMixin,
)

try:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH

PYPHOTOMETRY_PATH = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "pyphotometry"


class TestPyPhotometrySymbolicMode(FiberPhotometryInterfaceTestMixin):
    """Round-trip the first analog input of a ``2EX_2EM_pulsed`` recording, header version 1.0."""

    data_interface_cls = PyPhotometryFiberPhotometryInterface
    file_path = PYPHOTOMETRY_PATH / "mode_named_symbolically" / "two_excitation_two_emission_pulsed.ppd"
    interface_kwargs = dict(file_path=file_path, stream_name="analog_1")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array([0.91067634, 0.91067634, 0.91067634, 0.91057512, 0.91057512])
    expected_rate = 130.0
    expected_starting_time = 0.0

    def test_get_available_streams(self):
        """The header states two analog signals, so the file offers two."""
        assert self.data_interface_cls.get_available_streams(file_path=self.file_path) == [
            "analog_1",
            "analog_2",
        ]


class TestPyPhotometryOneColourTimeDivisionSignal(FiberPhotometryInterfaceTestMixin):
    """Round-trip the first analog input of a ``1 colour time div.`` recording, header version 0.3."""

    data_interface_cls = PyPhotometryFiberPhotometryInterface
    file_path = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "one_colour_time_division.ppd"
    interface_kwargs = dict(file_path=file_path, stream_name="analog_1")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array([0.77757204, 0.77706594, 0.77979888, 0.7788879, 0.78020376])
    expected_rate = 130.0
    expected_starting_time = 0.0

    def test_session_start_time_comes_from_the_header(self, setup_interface):
        """Unlike most fiber photometry formats, a ``.ppd`` records when the session started."""
        assert self.interface.get_metadata()["NWBFile"]["session_start_time"] == datetime(2021, 6, 8, 16, 52, 48)

    def test_strobed_recordings_carry_no_timing_note(self, setup_interface):
        """The stagger of a strobed recording is exact, so it is in the start time and needs no prose."""
        metadata = self.interface.get_metadata()
        assert "description" not in metadata["FiberPhotometry"][self.interface.metadata_key]


class TestPyPhotometryOneColourTimeDivisionControl(FiberPhotometryInterfaceTestMixin):
    """The second analog input of that recording, which is where the format's timing claim shows.

    The sampling timer runs at the header's rate times the number of analog inputs and the interrupt
    advances one input per tick, so this signal starts one tick of 260 Hz after the first. Every existing
    reader reports both as starting at zero.
    """

    data_interface_cls = PyPhotometryFiberPhotometryInterface
    file_path = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "one_colour_time_division.ppd"
    interface_kwargs = dict(file_path=file_path, stream_name="analog_2")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array([0.74882556, 0.74892678, 0.7495341, 0.74791458, 0.7485219])
    expected_rate = 130.0
    expected_starting_time = 1 / 260


class TestPyPhotometryTwoColourTimeDivision(FiberPhotometryInterfaceTestMixin):
    """Round-trip a ``2 colour time div.`` recording, header version 0.2.

    Version 0.2 differs from 0.3 only in carrying ``LED_current``, so this recording is here for its mode
    string rather than for its version.
    """

    data_interface_cls = PyPhotometryFiberPhotometryInterface
    file_path = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "two_colour_time_division.ppd"
    interface_kwargs = dict(file_path=file_path, stream_name="analog_1")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array(
        [2.5123816199999998, 2.51359626, 2.51724018, 2.5045876799999998, 2.52381948]
    )
    expected_rate = 130.0
    expected_starting_time = 0.0


class TestPyPhotometryTwoColourContinuous(FiberPhotometryInterfaceTestMixin):
    """Round-trip the second input of a ``2 colour continuous`` recording, at the board's 1 kHz ceiling.

    Continuous acquisition is the one case where a signal keeps the header's timebase. The board reads
    its inputs sequentially there too, but by an amount the file does not record and no pyPhotometry
    document states, so the series says so in prose instead of carrying a start time that would read as
    measured.
    """

    data_interface_cls = PyPhotometryFiberPhotometryInterface
    file_path = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "two_colour_continuous.ppd"
    interface_kwargs = dict(file_path=file_path, stream_name="analog_2")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array([0.32704182, 0.32694059999999997, 0.32683938, 0.32704182, 0.32714304])
    expected_rate = 1000.0
    expected_starting_time = 0.0

    def test_the_series_says_why_it_shares_the_headers_timebase(self, setup_interface):
        metadata = self.interface.get_metadata()
        description = metadata["FiberPhotometry"][self.interface.metadata_key]["description"]
        assert "sequentially" in description
        assert "213 microseconds" in description


class TestPyPhotometryIndicatorNamedMode(FiberPhotometryInterfaceTestMixin):
    """Round-trip a ``GCaMP/RFP_dif`` recording, header version 0.1, where the mode names fluorophores.

    This generation writes its version as a JSON number rather than a string and carries neither
    ``LED_current`` nor a signal count, so the mode is the only thing that gives the layout.
    """

    data_interface_cls = PyPhotometryFiberPhotometryInterface
    file_path = PYPHOTOMETRY_PATH / "mode_named_by_indicators" / "gcamp_rfp_dif.ppd"
    interface_kwargs = dict(file_path=file_path, stream_name="analog_1")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array(
        [0.9060699462890625, 0.9060699462890625, 0.9060699462890625, 0.90596923828125, 0.90596923828125]
    )
    expected_rate = 130.0
    expected_starting_time = 0.0


class TestPyPhotometryFourColourFork(FiberPhotometryInterfaceTestMixin):
    """Round-trip the first signal of the four-colour fork, whose layout its header does not state.

    Each analog input time-multiplexes two colours, so the file holds four signals at half the rate the
    header advertises. Nothing but the mode string distinguishes it from an ordinary two-signal
    recording, and reading it by the rule documented for this header generation returns two traces of
    interleaved colours.
    """

    data_interface_cls = PyPhotometryFiberPhotometryInterface
    file_path = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "four_colour_time_division.ppd"
    interface_kwargs = dict(file_path=file_path, stream_name="analog_1")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array(
        [0.17166911999999998, 0.10132121999999999, 0.18766188, 0.09929682, 0.18745944]
    )
    expected_rate = 32.5
    expected_starting_time = 0.0

    def test_get_available_streams(self):
        """A multiplexed line is named by its input and its colour, since the input alone is ambiguous."""
        assert self.data_interface_cls.get_available_streams(file_path=self.file_path) == [
            "analog_1",
            "analog_2",
            "analog_1_color_2",
            "analog_2_color_2",
        ]


class TestPyPhotometryFourColourForkLastSlot(FiberPhotometryInterfaceTestMixin):
    """The fork's last slot, three ticks into the cycle and at half the header's rate."""

    data_interface_cls = PyPhotometryFiberPhotometryInterface
    file_path = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "four_colour_time_division.ppd"
    interface_kwargs = dict(file_path=file_path, stream_name="analog_2_color_2")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array(
        [0.2864526, 0.23857554, 0.26296956, 0.24424385999999998, 0.24879875999999998]
    )
    expected_rate = 32.5
    expected_starting_time = 3 / 130


class TestPyPhotometryPreJsonHeader(FiberPhotometryInterfaceTestMixin):
    """Round-trip a recording older than the JSON header, whose 42 bytes are a fixed layout.

    A failed JSON parse is what identifies the generation. Its mode is a one-byte code whose meaning was
    never published, so no stagger is claimed for its signals.
    """

    data_interface_cls = PyPhotometryFiberPhotometryInterface
    file_path = PYPHOTOMETRY_PATH / "header_predates_json" / "two_signals_200hz.ppd"
    interface_kwargs = dict(file_path=file_path, stream_name="analog_1")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array(
        [0.906069876, 0.906069876, 0.906069876, 0.9059691679999999, 0.9059691679999999]
    )
    expected_rate = 200.0
    expected_starting_time = 0.0


class TestPyPhotometryConstruction:
    """Errors raised before a conversion, which the round-trip mixin cannot express."""

    file_path = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "one_colour_time_division.ppd"

    def test_asking_for_a_signal_the_file_does_not_have_is_refused(self):
        """Which signals exist depends on the acquisition mode, so this is a mistake worth naming."""
        with pytest.raises(ValueError, match="'analog_3' is not a signal of"):
            PyPhotometryFiberPhotometryInterface(file_path=self.file_path, stream_name="analog_3")

    def test_the_first_signal_is_read_when_none_is_named(self):
        """A file holding one signal needs no argument; one holding several is only unambiguous with it."""
        interface = PyPhotometryFiberPhotometryInterface(file_path=self.file_path)

        assert interface.stream_names == ["analog_1"]
