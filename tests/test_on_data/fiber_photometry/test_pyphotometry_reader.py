"""On-data tests for the pyPhotometry ``.ppd`` reader, one fixture per header generation.

The format's layout is decided by its ``mode`` string, and the vocabulary changed twice: version 0.1
names the indicators, 0.2 and 0.3 describe the acquisition in prose, and 1.0 onward uses symbolic names.
A sixth generation predates the JSON header entirely. The recordings below are grouped by which of those
vocabularies their header speaks, so between them they exercise every branch of the mode table against a
real recording.

Two branches cannot be covered here and are unit tested against files assembled in
``tests/test_modalities/test_fiber_photometry/test_pyphotometry_ppd.py`` instead: the paired
LED-on/baseline storage of version 1.1, for which no public recording exists anywhere, and the refusals.

TODO: these recordings are not on gin yet, so this module skips unless a local copy is present. Publish
them under ``fiber_photometry_datasets/pyphotometry``, then delete the skip so CI covers this. Tracked in
``ongoing_work/fiber_photometry/pyphotometry_interface_plan``.
"""

import json

import numpy as np
import pytest

from neuroconv.datainterfaces.fiber_photometry.pyphotometry._ppd import read_ppd

from ..setup_paths import OPHYS_DATA_PATH

PYPHOTOMETRY_PATH = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "pyphotometry"

# What each recording holds, read off the file's own header. `starting_times` is what the
# reader must reconstruct: the signals are sampled one after another, so they do not all start at zero.
FIXTURE_EXPECTATIONS = {
    "mode_named_symbolically/two_excitation_two_emission_pulsed.ppd": dict(
        mode="2EX_2EM_pulsed",
        signal_count=2,
        signal_rate=130.0,
        starting_times=[0.0, 1 / 260],
    ),
    "mode_named_in_prose/one_colour_time_division.ppd": dict(
        mode="1 colour time div.",
        signal_count=2,
        signal_rate=130.0,
        starting_times=[0.0, 1 / 260],
    ),
    "mode_named_in_prose/two_colour_continuous.ppd": dict(
        mode="2 colour continuous",
        signal_count=2,
        signal_rate=1000.0,
        starting_times=[0.0, 0.0],
    ),
    "mode_named_by_indicators/gcamp_rfp_dif.ppd": dict(
        mode="GCaMP/RFP_dif",
        signal_count=2,
        signal_rate=130.0,
        starting_times=[0.0, 1 / 260],
    ),
    "mode_named_in_prose/four_colour_time_division.ppd": dict(
        mode="4 colour time div.",
        signal_count=4,
        signal_rate=32.5,
        starting_times=[0.0, 1 / 130, 2 / 130, 3 / 130],
    ),
    "header_predates_json/two_signals_200hz.ppd": dict(
        mode=None,
        signal_count=2,
        signal_rate=200.0,
        starting_times=[0.0, 0.0],
    ),
}


def get_recording_path(relative_path: str):
    """Return a recording by name, or skip when this machine does not have the corpus."""
    file_path = PYPHOTOMETRY_PATH / relative_path
    if not file_path.exists():
        pytest.skip(f"{file_path} is not present; the recordings are not published yet.")
    return file_path


@pytest.mark.parametrize("recording_path", list(FIXTURE_EXPECTATIONS))
def test_every_header_generation_reads(recording_path):
    """Each generation's mode string resolves to a layout, and the signals come out with their timing."""
    expectations = FIXTURE_EXPECTATIONS[recording_path]
    file_path = get_recording_path(recording_path)

    recording = read_ppd(file_path)

    assert recording.header.get("mode") == expectations["mode"]
    assert len(recording.analog_signals) == expectations["signal_count"]
    assert [signal.rate_in_hz for signal in recording.analog_signals] == [expectations["signal_rate"]] * len(
        recording.analog_signals
    )
    assert [signal.starting_time_in_seconds for signal in recording.analog_signals] == pytest.approx(
        expectations["starting_times"]
    )
    for signal in recording.analog_signals:
        assert signal.data_in_volts.size > 0
        assert np.all(np.isfinite(signal.data_in_volts))


@pytest.mark.parametrize(
    "recording_path",
    [name for name in FIXTURE_EXPECTATIONS if name != "mode_named_in_prose/four_colour_time_division.ppd"],
)
def test_signals_match_the_upstream_de_interleave(recording_path):
    """Every ordinary recording must decode to exactly what pyPhotometry's own reader returns.

    Upstream takes ``analog[signal_index::signal_count] * volts_per_division``. Agreeing with it on the
    modes it reads correctly is what makes the disagreement on the fork a claim rather than a bug.
    """
    file_path = get_recording_path(recording_path)
    raw = file_path.read_bytes()
    header_length = int.from_bytes(raw[:2], "little")
    words = np.frombuffer(raw[2 + header_length :], dtype="<u2")
    analog_words = (words >> 1).astype(np.float64)

    recording = read_ppd(file_path)

    signal_count = len(recording.analog_signals)
    for signal_index, signal in enumerate(recording.analog_signals):
        volts_per_division = recording.header["volts_per_division"][signal.analog_input]
        expected = analog_words[signal_index::signal_count] * volts_per_division
        np.testing.assert_array_equal(signal.data_in_volts, expected)


def test_the_pre_json_header_carries_the_same_scale_as_the_json_one():
    """The fixed layout packs volts per division as a scaled integer rather than a float."""
    file_path = get_recording_path("header_predates_json/two_signals_200hz.ppd")

    recording = read_ppd(file_path)

    with pytest.raises(json.JSONDecodeError):
        header_length = int.from_bytes(file_path.read_bytes()[:2], "little")
        json.loads(file_path.read_bytes()[2 : 2 + header_length].decode("utf-8", errors="replace"))

    assert recording.header["volts_per_division"] == [pytest.approx(0.000100708), pytest.approx(0.000100708)]
    assert "mode_code" in recording.header
