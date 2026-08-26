"""On-data tests for the pyPhotometry fiber photometry interface.

One round-trip class per recording and per signal, under directories named for the header generation the
recording belongs to. Cases no recording covers are written by
``tests/test_modalities/test_fiber_photometry/test_pyphotometry_edge_cases.py`` instead.

Beyond reading at all, what the round trips assert is timing. Classes come in pairs where a recording's
signals are staggered, one per signal, so the second one's ``expected_starting_time`` is the claim.

Each expected trace is the leading samples of that signal, read off the file by hand rather than through
the interface, with ``stub_samples`` keeping them short.
"""

import re
from datetime import datetime

import numpy as np
import pytest
from pynwb import read_nwb

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
    interface_kwargs = dict(file_path=file_path, stream_name="detector_1_excitation_1")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array([0.91067634, 0.91067634, 0.91067634, 0.91057512, 0.91057512])
    expected_rate = 130.0
    expected_starting_time = 0.0

    def test_get_available_streams(self):
        """The header states two analog signals, so the file offers two."""
        assert self.data_interface_cls.get_available_streams(file_path=self.file_path) == [
            "detector_1_excitation_1",
            "detector_2_excitation_2",
        ]

    def run_custom_checks(self):
        """A recording that stores no LED-off baseline writes one series and nothing beside it.

        The shared checks look their own series up by name, so they pass with anything else sitting
        beside it. Only recordings written by header version 1.1 or later carry the raw measurements that
        would add series here, and this is the assertion that says so.
        """
        nwbfile = read_nwb(self.nwbfile_path)

        assert set(nwbfile.acquisition) == {"FiberPhotometryResponseSeries"}


class TestPyPhotometryOneColourTimeDivisionSignal(FiberPhotometryInterfaceTestMixin):
    """Round-trip the first analog input of a ``1 colour time div.`` recording, header version 0.3."""

    data_interface_cls = PyPhotometryFiberPhotometryInterface
    file_path = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "one_colour_time_division.ppd"
    interface_kwargs = dict(file_path=file_path, stream_name="detector_1_excitation_1")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array([0.77757204, 0.77706594, 0.77979888, 0.7788879, 0.78020376])
    expected_rate = 130.0
    expected_starting_time = 0.0

    def check_extracted_metadata(self, metadata: dict):
        """A ``.ppd`` header states when the session started and what the animal was called.

        The stagger of a strobed recording is exact, so it is carried by the start time and the series
        needs no prose about its timing.
        """
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 6, 8, 16, 52, 48)
        assert metadata["Subject"]["subject_id"] == "FFC_AF50-202"
        assert "description" not in metadata["FiberPhotometry"][self.interface.metadata_key]

    def test_asking_for_a_signal_the_file_does_not_have_is_refused(self):
        """Which signals exist depends on the acquisition mode, so this is a mistake worth naming."""
        with pytest.raises(ValueError, match="'detector_9_excitation_9' is not a signal of"):
            PyPhotometryFiberPhotometryInterface(file_path=self.file_path, stream_name="detector_9_excitation_9")

    def test_the_first_signal_is_read_when_none_is_named(self):
        """A file holding one signal needs no argument; one holding several is only unambiguous with it."""
        interface = PyPhotometryFiberPhotometryInterface(file_path=self.file_path)

        assert interface.stream_names == ["detector_1_excitation_1"]


class TestPyPhotometryOneColourTimeDivisionControl(FiberPhotometryInterfaceTestMixin):
    """The second analog input of that recording, which is where the format's timing claim shows.

    The sampling timer runs at the header's rate times the number of analog inputs and the interrupt
    advances one input per tick, so this signal starts one tick of 260 Hz after the first. Every existing
    reader reports both as starting at zero.
    """

    data_interface_cls = PyPhotometryFiberPhotometryInterface
    file_path = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "one_colour_time_division.ppd"
    interface_kwargs = dict(file_path=file_path, stream_name="detector_1_excitation_2")
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
    interface_kwargs = dict(file_path=file_path, stream_name="detector_1_excitation_1")
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
    interface_kwargs = dict(file_path=file_path, stream_name="detector_2_excitation_2")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array([0.32704182, 0.32694059999999997, 0.32683938, 0.32704182, 0.32714304])
    expected_rate = 1000.0
    expected_starting_time = 0.0

    def check_extracted_metadata(self, metadata: dict):
        """The lag is real in a continuous mode but its size is not in the file, so it is said in prose."""
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
    interface_kwargs = dict(file_path=file_path, stream_name="detector_1_excitation_1")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array(
        [0.9060699462890625, 0.9060699462890625, 0.9060699462890625, 0.90596923828125, 0.90596923828125]
    )
    expected_rate = 130.0
    expected_starting_time = 0.0


class TestPyPhotometryForkIsRefused:
    """The Wiegert-lab fork's ``4 colour time div.`` is recognized and refused, not read.

    Its analog lines each alternate two excitation sources, so it holds four signals at half the rate its
    header states, and nothing distinguishes it from an ordinary two-signal recording except the mode
    string. Reading it the documented way returns interleaved colours that look like traces. It is listed
    rather than left to the unknown-mode path so the message names the fork and says support can be added.
    """

    file_path = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "four_colour_time_division.ppd"

    def test_the_fork_is_refused_by_name(self):
        expected_error = (
            "This recording was written by the Wiegert-lab fork of the pyPhotometry acquisition software "
            "(Formozov, Dieter and Wiegert 2023, Cell Reports Methods 3:100418), whose analog lines each "
            "alternate two excitation sources, so it holds four signals at half the rate its header "
            "states. Reading it with the layout the format documents returns two traces of interleaved "
            "colours that look like signals and are not, so it is refused rather than guessed at. "
            "Support can be added: please open an issue at "
            "https://github.com/catalystneuro/neuroconv/issues."
        )

        with pytest.raises(ValueError, match=re.escape(expected_error)):
            PyPhotometryFiberPhotometryInterface(file_path=self.file_path)


class TestPyPhotometryPreJsonHeader(FiberPhotometryInterfaceTestMixin):
    """Round-trip a recording older than the JSON header, whose 42 bytes are a fixed layout.

    A failed JSON parse is what identifies the generation. Byte 31 is a code indexing the three modes
    that generation offered, so it resolves to a layout the same way a mode string does.
    """

    data_interface_cls = PyPhotometryFiberPhotometryInterface
    file_path = PYPHOTOMETRY_PATH / "header_predates_json" / "two_signals_200hz.ppd"
    interface_kwargs = dict(file_path=file_path, stream_name="detector_1_excitation_1")
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    expected_response_series_data = np.array(
        [0.906069876, 0.906069876, 0.906069876, 0.9059691679999999, 0.9059691679999999]
    )
    expected_rate = 200.0
    expected_starting_time = 0.0

    def test_the_mode_code_staggers_the_second_signal(self):
        """Byte 31 of this file is 3, which was ``GCaMP/RFP_dif``: two receivers, strobed.

        So its signals are a timer tick apart like any other strobed recording, rather than sharing the
        header's timebase. The code is what says so; nothing else in the file does.
        """
        second = PyPhotometryFiberPhotometryInterface(file_path=self.file_path, stream_name="detector_2_excitation_2")

        assert second.get_original_timestamps()[0] == pytest.approx(1 / (200 * 2))
