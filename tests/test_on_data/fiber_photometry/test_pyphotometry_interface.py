"""On-data tests for :class:`.PyPhotometryFiberPhotometryInterface`.

One interface reads one signal, so what these check is the seam between the reader and the write: which
signals a file offers, that asking for one that is not there fails rather than reading the wrong words,
that the header's session start reaches the file, and above all that a signal is written with the start
time the acquisition gave it. The last is the reason the interface exists rather than deferring to the
vendor reader, which reports every signal as starting at zero.

The paired LED-on and baseline write path is exercised in
``tests/test_modalities/test_fiber_photometry/test_pyphotometry_ppd.py``, since no version 1.1 recording
exists to run it against here.

TODO: these recordings are not on gin yet, so this module skips unless a local copy is present. Stub
them and publish them under ``fiber_photometry_datasets/pyphotometry``, then delete the skip so CI
covers this. Tracked in ``ongoing_work/fiber_photometry/pyphotometry_interface_plan``.
"""

from datetime import datetime

import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import PyPhotometryFiberPhotometryInterface

from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH

PYPHOTOMETRY_PATH = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "pyphotometry"


def get_fixture_file_path(directory_name: str):
    directory = PYPHOTOMETRY_PATH / directory_name
    file_paths = sorted(directory.glob("*.ppd")) if directory.exists() else []
    if not file_paths:
        pytest.skip(f"No pyPhotometry fixture in {directory}; the corpus is not published yet.")
    return file_paths[0]


def test_available_streams_are_named_after_the_analog_lines():
    file_path = get_fixture_file_path("legacy_one_colour_time_division")

    assert PyPhotometryFiberPhotometryInterface.get_available_streams(file_path=file_path) == [
        "analog_1",
        "analog_2",
    ]


def test_color_multiplexed_lines_are_named_by_line_and_color():
    """The fork's two analog lines each carry two colors, so a line alone does not name a signal."""
    file_path = get_fixture_file_path("four_colour_fork")

    assert PyPhotometryFiberPhotometryInterface.get_available_streams(file_path=file_path) == [
        "analog_1",
        "analog_2",
        "analog_1_color_2",
        "analog_2_color_2",
    ]


def test_asking_for_a_signal_the_file_does_not_have_is_refused():
    """Which signals exist depends on the acquisition mode, so this is a mistake worth naming."""
    file_path = get_fixture_file_path("legacy_one_colour_time_division")

    with pytest.raises(ValueError, match="'analog_3' is not a signal of"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_3")


def test_session_start_time_comes_from_the_header():
    file_path = get_fixture_file_path("legacy_one_colour_time_division")
    interface = PyPhotometryFiberPhotometryInterface(file_path=file_path)

    metadata = interface.get_metadata()

    assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 6, 8, 16, 52, 48)


@pytest.mark.parametrize(
    "stream_name, expected_starting_time",
    [("analog_1", 0.0), ("analog_2", 1 / 260)],
)
def test_each_signal_is_written_with_the_start_time_it_was_sampled_at(stream_name, expected_starting_time, tmp_path):
    """A pulsed recording strobes its lines in turn, so the second one starts one timer tick later.

    Both signals are regular and at the header's rate, so the difference between them is a start time
    and nothing else. Writing both at zero, which is what the vendor reader implies, would place two
    measurements taken 3.8 ms apart at the same instant.
    """
    file_path = get_fixture_file_path("legacy_one_colour_time_division")
    interface = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name=stream_name)
    metadata = interface.get_metadata()

    nwbfile_path = tmp_path / f"pyphotometry_{stream_name}.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        series = nwbfile.acquisition["FiberPhotometryResponseSeries"]
        assert series.rate == 130.0
        assert series.starting_time == pytest.approx(expected_starting_time)
        assert series.data.shape == (len(interface.get_timestamps()),)


def test_the_written_signal_matches_the_file():
    """The values written are the file's own, scaled by the header's volts per division."""
    file_path = get_fixture_file_path("legacy_two_colour_continuous")
    interface = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_1")
    expected = interface.recording.analog_signals[0].data_in_volts

    nwbfile_path = OUTPUT_PATH / "pyphotometry_values.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=interface.get_metadata(), overwrite=True)

    with NWBHDF5IO(nwbfile_path, "r") as io:
        series = io.read().acquisition["FiberPhotometryResponseSeries"]
        assert series.data[:] == pytest.approx(expected)
