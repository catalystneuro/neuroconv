"""Unit tests for the pyPhotometry ``.ppd`` reader, on files built here rather than recorded.

These cover the layouts and the refusals that no recording available to us exercises: the paired
LED-on/baseline storage that arrived in header version 1.1, for which no public file exists at all, the
fixed-layout header that predates JSON, an unknown mode string, and the fact that the header's version
field is a JSON number in one generation and a string in another. Everything that a real recording does
cover is asserted against the recordings themselves in ``tests/test_on_data``.
"""

import json

import numpy as np
import pytest

from neuroconv.datainterfaces.fiber_photometry.pyphotometry._ppd import read_ppd

VOLTS_PER_DIVISION = 0.00010122


def write_ppd_file(file_path, header: dict, analog_values, digital_bits=None) -> None:
    """Assemble a ``.ppd`` file: a header length, a JSON header, then the packed words."""
    header_bytes = json.dumps(header).encode("utf-8")
    analog_values = np.asarray(analog_values, dtype=np.uint16)
    digital_bits = np.zeros_like(analog_values) if digital_bits is None else np.asarray(digital_bits, dtype=np.uint16)
    words = (analog_values << 1) | digital_bits
    file_path.write_bytes(len(header_bytes).to_bytes(2, "little") + header_bytes + words.astype("<u2").tobytes())


def test_paired_samples_are_subtracted_and_both_raws_kept(tmp_path):
    """From version 1.1 a pulsed file stores the LED-on sample and the baseline it was measured against.

    The reader must both report the difference, which is what the firmware used to compute on the board
    and what every downstream tool expects, and keep the two measurements it came from.
    """
    header = {
        "mode": "2EX_2EM_pulsed",
        "sampling_rate": 130,
        "volts_per_division": [VOLTS_PER_DIVISION, VOLTS_PER_DIVISION],
        "n_analog_signals": 2,
        "n_digital_signals": 2,
        "version": "1.1",
    }
    # One cycle is four words: signal 0's LED-on and baseline, then signal 1's.
    analog_values = [1000, 100, 2000, 200, 1010, 110, 2010, 210]
    file_path = tmp_path / "paired.ppd"
    write_ppd_file(file_path, header, analog_values)

    recording = read_ppd(file_path)

    assert recording.has_paired_samples
    first, second = recording.analog_signals
    np.testing.assert_allclose(first.raw_led_on_in_volts, np.array([1000, 1010]) * VOLTS_PER_DIVISION)
    np.testing.assert_allclose(first.raw_baseline_in_volts, np.array([100, 110]) * VOLTS_PER_DIVISION)
    np.testing.assert_allclose(first.data_in_volts, np.array([900, 900]) * VOLTS_PER_DIVISION)
    np.testing.assert_allclose(second.data_in_volts, np.array([1800, 1800]) * VOLTS_PER_DIVISION)

    # The pair occupies one slot, so the signals are staggered by one tick of the 260 Hz timer and each
    # still runs at the rate the header states.
    assert first.starting_time_in_seconds == 0.0
    assert second.starting_time_in_seconds == pytest.approx(1 / 260)
    assert first.rate_in_hz == 130.0


def test_unpaired_file_reports_no_raws(tmp_path):
    """Before 1.1 the board did the subtraction itself, so there is no pair to keep."""
    header = {
        "mode": "2EX_2EM_pulsed",
        "sampling_rate": 130,
        "volts_per_division": [VOLTS_PER_DIVISION, VOLTS_PER_DIVISION],
        "n_analog_signals": 2,
        "n_digital_signals": 2,
        "version": "1.0",
    }
    file_path = tmp_path / "unpaired.ppd"
    write_ppd_file(file_path, header, [1000, 2000, 1010, 2010])

    recording = read_ppd(file_path)

    assert not recording.has_paired_samples
    first, second = recording.analog_signals
    assert first.raw_led_on_in_volts is None and first.raw_baseline_in_volts is None
    np.testing.assert_allclose(first.data_in_volts, np.array([1000, 1010]) * VOLTS_PER_DIVISION)
    np.testing.assert_allclose(second.data_in_volts, np.array([2000, 2010]) * VOLTS_PER_DIVISION)


def test_unknown_mode_is_refused(tmp_path):
    """A mode the table does not know must raise rather than fall back to the two-signal default.

    The default is what turns a fork's file, which is indistinguishable from an ordinary two-signal
    recording except by this string, into interleaved colors that look like a trace.
    """
    header = {
        "mode": "5EX_3EM_whatever",
        "sampling_rate": 130,
        "volts_per_division": [VOLTS_PER_DIVISION, VOLTS_PER_DIVISION],
        "version": "1.0",
    }
    file_path = tmp_path / "unknown.ppd"
    write_ppd_file(file_path, header, [1000, 2000])

    with pytest.raises(ValueError, match="Unknown pyPhotometry acquisition mode '5EX_3EM_whatever'"):
        read_ppd(file_path)


def test_mode_disagreeing_with_the_declared_signal_count_is_refused(tmp_path):
    """The header states the count from version 1.0 on, so a mode that contradicts it is not readable."""
    header = {
        "mode": "2EX_2EM_pulsed",
        "sampling_rate": 130,
        "volts_per_division": [VOLTS_PER_DIVISION, VOLTS_PER_DIVISION],
        "n_analog_signals": 3,
        "version": "1.0",
    }
    file_path = tmp_path / "contradictory.ppd"
    write_ppd_file(file_path, header, [1000, 2000, 3000])

    with pytest.raises(ValueError, match="interleaves 2 analog lines but the header declares"):
        read_ppd(file_path)


def test_version_is_read_whether_it_is_a_number_or_a_string(tmp_path):
    """0.1 and 0.2 write the version as a JSON number and 0.3 onward as a string.

    The version decides whether the samples are paired, so a comparison that works on one spelling and
    not the other reads half the corpus with the wrong stride.
    """
    for version in (1.1, "1.1"):
        header = {
            "mode": "2EX_2EM_pulsed",
            "sampling_rate": 130,
            "volts_per_division": [VOLTS_PER_DIVISION, VOLTS_PER_DIVISION],
            "n_analog_signals": 2,
            "version": version,
        }
        file_path = tmp_path / f"version_{type(version).__name__}.ppd"
        write_ppd_file(file_path, header, [1000, 100, 2000, 200])

        assert read_ppd(file_path).has_paired_samples, f"version {version!r} was not read as paired"


def test_digital_lines_are_read_from_the_low_bit(tmp_path):
    """Each word carries one analog sample and one digital line, and a line shares its signal's slot."""
    header = {
        "mode": "2EX_2EM_pulsed",
        "sampling_rate": 130,
        "volts_per_division": [VOLTS_PER_DIVISION, VOLTS_PER_DIVISION],
        "n_analog_signals": 2,
        "n_digital_signals": 2,
        "version": "1.0",
    }
    file_path = tmp_path / "digital.ppd"
    write_ppd_file(file_path, header, [1000, 2000, 1010, 2010], digital_bits=[1, 0, 0, 1])

    recording = read_ppd(file_path)

    first, second = recording.digital_signals
    np.testing.assert_array_equal(first.data, [1, 0])
    np.testing.assert_array_equal(second.data, [0, 1])
    assert second.starting_time_in_seconds == pytest.approx(1 / 260)
    # The analog values must be untouched by the digital bit sharing their word.
    np.testing.assert_allclose(recording.analog_signals[0].data_in_volts, np.array([1000, 1010]) * VOLTS_PER_DIVISION)


def test_header_older_than_json_is_read_as_a_version_signal(tmp_path):
    """A header that fails to parse as JSON is the pre-2018 fixed layout, not a corrupt file."""
    header_bytes = (
        b"P10V_16".ljust(12, b" ")
        + b"2018-08-16T08:51:15"
        + bytes([3])
        + (200).to_bytes(2, "little")
        + (100708).to_bytes(4, "little")
        + (100708).to_bytes(4, "little")
    )
    words = np.array([1000, 2000, 1010, 2010], dtype=np.uint16) << 1
    file_path = tmp_path / "prejson.ppd"
    file_path.write_bytes(len(header_bytes).to_bytes(2, "little") + header_bytes + words.astype("<u2").tobytes())

    recording = read_ppd(file_path)

    assert recording.header["subject_ID"] == "P10V_16"
    assert recording.header["mode_code"] == 3
    assert recording.sampling_rate_in_hz == 200.0
    np.testing.assert_allclose(recording.analog_signals[0].data_in_volts, np.array([1000, 1010]) * 100708 / 1e9)
    # The mode code's meaning is unpublished, so the reader must not claim the signals are staggered.
    assert [signal.starting_time_in_seconds for signal in recording.analog_signals] == [0.0, 0.0]


def test_header_that_is_neither_json_nor_the_fixed_layout_is_rejected(tmp_path):
    file_path = tmp_path / "garbage.ppd"
    file_path.write_bytes((8).to_bytes(2, "little") + b"\x00\x01\x02\x03\x04\x05\x06\x07" + b"\x00\x00")

    with pytest.raises(ValueError, match="neither JSON nor the 42-byte fixed layout"):
        read_ppd(file_path)


def test_color_multiplexed_lines_split_and_halve_their_rate(tmp_path):
    """The four-color fork multiplexes two colors onto each analog line.

    Its header advertises 65 Hz and carries no signal count, so reading it the documented way gives two
    signals of alternating colors. The mode string is the only thing that says otherwise.
    """
    header = {
        "mode": "4 colour time div.",
        "sampling_rate": 65,
        "volts_per_division": [VOLTS_PER_DIVISION, VOLTS_PER_DIVISION],
        "version": "0.3",
    }
    # Two cycles of: line 0 color 0, line 1 color 0, line 0 color 1, line 1 color 1.
    file_path = tmp_path / "fork.ppd"
    write_ppd_file(file_path, header, [10, 20, 30, 40, 11, 21, 31, 41])

    recording = read_ppd(file_path)

    assert len(recording.analog_signals) == 4
    assert [signal.rate_in_hz for signal in recording.analog_signals] == [32.5] * 4
    assert [signal.starting_time_in_seconds for signal in recording.analog_signals] == pytest.approx(
        [0 / 130, 1 / 130, 2 / 130, 3 / 130]
    )
    np.testing.assert_allclose(recording.analog_signals[0].data_in_volts, np.array([10, 11]) * VOLTS_PER_DIVISION)
    np.testing.assert_allclose(recording.analog_signals[3].data_in_volts, np.array([40, 41]) * VOLTS_PER_DIVISION)
