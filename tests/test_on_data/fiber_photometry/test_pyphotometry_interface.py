"""On-data tests for :class:`.PyPhotometryFiberPhotometryInterface`.

A ``.ppd`` file holds every signal the board recorded interleaved word by word, and nothing in it says
how to separate them except the header's ``mode`` field, whose spelling changed across four header
generations. The recordings under ``fiber_photometry_datasets/pyphotometry`` are one per generation, so
converting each of them exercises every branch of that mapping against a file rather than against an
assumption.

What the conversions assert, beyond reading at all, is timing. The board samples its analog inputs one
after another, so each signal is written with the start time its slot implies, where the vendor's reader
reports every signal as starting at zero.

The paired LED-on and baseline path, which arrived with header version 1.1, and the refusals are covered
in ``tests/test_modalities/test_fiber_photometry/test_pyphotometry.py``, since no version 1.1 recording
exists anywhere and a malformed header has to be built rather than found.
"""

from datetime import datetime

import numpy as np
import pytest

from neuroconv.datainterfaces import PyPhotometryFiberPhotometryInterface

from ..setup_paths import OPHYS_DATA_PATH

PYPHOTOMETRY_PATH = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "pyphotometry"

# One recording per header generation, with what its own header says it holds. `starting_times` is the
# claim worth testing: the signals were sampled one after another, so they do not all start at zero.
RECORDINGS = {
    "mode_named_symbolically/two_excitation_two_emission_pulsed.ppd": dict(
        streams=["analog_1", "analog_2"],
        rate=130.0,
        starting_times=[0.0, 1 / 260],
    ),
    "mode_named_in_prose/one_colour_time_division.ppd": dict(
        streams=["analog_1", "analog_2"],
        rate=130.0,
        starting_times=[0.0, 1 / 260],
    ),
    "mode_named_in_prose/two_colour_time_division.ppd": dict(
        streams=["analog_1", "analog_2"],
        rate=130.0,
        starting_times=[0.0, 1 / 260],
    ),
    "mode_named_in_prose/two_colour_continuous.ppd": dict(
        streams=["analog_1", "analog_2"],
        rate=1000.0,
        starting_times=[0.0, 0.0],
    ),
    "mode_named_by_indicators/gcamp_rfp_dif.ppd": dict(
        streams=["analog_1", "analog_2"],
        rate=130.0,
        starting_times=[0.0, 1 / 260],
    ),
    "mode_named_in_prose/four_colour_time_division.ppd": dict(
        streams=["analog_1", "analog_2", "analog_1_color_2", "analog_2_color_2"],
        rate=32.5,
        starting_times=[0.0, 1 / 130, 2 / 130, 3 / 130],
    ),
    "header_predates_json/two_signals_200hz.ppd": dict(
        streams=["analog_1", "analog_2"],
        rate=200.0,
        starting_times=[0.0, 0.0],
    ),
}

ONE_COLOUR_TIME_DIVISION = "mode_named_in_prose/one_colour_time_division.ppd"
TWO_COLOUR_CONTINUOUS = "mode_named_in_prose/two_colour_continuous.ppd"


@pytest.mark.parametrize("relative_path", list(RECORDINGS))
def test_every_header_generation_converts_with_its_own_timing(relative_path):
    """Each generation's mode resolves to a layout, and each signal keeps the time it was sampled at."""
    expectations = RECORDINGS[relative_path]
    file_path = PYPHOTOMETRY_PATH / relative_path

    assert PyPhotometryFiberPhotometryInterface.get_available_streams(file_path=file_path) == expectations["streams"]

    for stream_index, stream_name in enumerate(expectations["streams"]):
        interface = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name=stream_name)
        nwbfile = interface.create_nwbfile(metadata=interface.get_metadata())

        series = nwbfile.acquisition["FiberPhotometryResponseSeries"]
        assert series.rate == expectations["rate"]
        assert series.starting_time == pytest.approx(expectations["starting_times"][stream_index])
        assert series.data.size > 0
        assert np.all(np.isfinite(series.data))


def test_written_values_are_the_file_own_samples():
    """The values written are the file's words, de-interleaved and scaled by its volts per division.

    That is what pyPhotometry's own reader returns for this file, so agreeing with it here is what makes
    the timing a correction to that reader rather than a different reading of the format.
    """
    file_path = PYPHOTOMETRY_PATH / ONE_COLOUR_TIME_DIVISION
    raw = file_path.read_bytes()
    header_length = int.from_bytes(raw[:2], "little")
    analog_words = (np.frombuffer(raw[2 + header_length :], dtype="<u2") >> 1).astype(np.float64)

    for stream_index, stream_name in enumerate(["analog_1", "analog_2"]):
        interface = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name=stream_name)
        nwbfile = interface.create_nwbfile(metadata=interface.get_metadata())

        expected = analog_words[stream_index::2] * 0.00010122
        np.testing.assert_array_equal(nwbfile.acquisition["FiberPhotometryResponseSeries"].data, expected)


def test_session_start_time_comes_from_the_header():
    interface = PyPhotometryFiberPhotometryInterface(file_path=PYPHOTOMETRY_PATH / ONE_COLOUR_TIME_DIVISION)

    metadata = interface.get_metadata()

    assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 6, 8, 16, 52, 48)


def test_asking_for_a_signal_the_file_does_not_have_is_refused():
    """Which signals exist depends on the acquisition mode, so this is a mistake worth naming."""
    with pytest.raises(ValueError, match="'analog_3' is not a signal of"):
        PyPhotometryFiberPhotometryInterface(
            file_path=PYPHOTOMETRY_PATH / ONE_COLOUR_TIME_DIVISION, stream_name="analog_3"
        )


def test_continuous_recordings_say_why_their_signals_share_a_timebase():
    """The lag between a continuous file's signals is real but its size is not knowable from the file.

    The board reads its inputs one after the other there too, but neither the oversampling constants nor
    the interrupt overhead is recorded anywhere, and no upstream document states the resulting offset. So
    the series carry the header's timebase and say so, rather than a start time that would read as
    measured.
    """
    interface = PyPhotometryFiberPhotometryInterface(
        file_path=PYPHOTOMETRY_PATH / TWO_COLOUR_CONTINUOUS, stream_name="analog_2"
    )

    nwbfile = interface.create_nwbfile(metadata=interface.get_metadata())

    series = nwbfile.acquisition["FiberPhotometryResponseSeries"]
    assert series.starting_time == 0.0
    assert "213 microseconds" in series.description
    assert "sequentially" in series.description


def test_strobed_recordings_carry_no_such_note():
    """A strobed file's stagger is exact, so it is in the start time and needs no explanation."""
    interface = PyPhotometryFiberPhotometryInterface(
        file_path=PYPHOTOMETRY_PATH / ONE_COLOUR_TIME_DIVISION, stream_name="analog_2"
    )

    assert "description" not in interface.get_metadata()["FiberPhotometry"][interface.metadata_key]
