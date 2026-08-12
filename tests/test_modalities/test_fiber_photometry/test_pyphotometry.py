"""Tests for :class:`.PyPhotometryFiberPhotometryInterface` on files built here rather than recorded.

These cover what no recording can. A file whose header is malformed, or whose mode nothing recognizes,
has to be constructed: the interface refuses those rather than reading them with a default layout,
because the format's own fallback rule turns a laboratory fork's recording into interleaved colours
without raising. And header version 1.1, which stores an LED-on sample beside the LED-off baseline it is
corrected against, exists in no public deposit at all, so what is asserted about it here is the warning
the interface raises, not the traces it produces. Certifying values for a layout nobody has seen is what
that warning exists to avoid.

Everything a real recording does cover is asserted against the recordings themselves in
``tests/test_on_data/fiber_photometry/test_pyphotometry_interface.py``.
"""

import json

import numpy as np
import pytest

from neuroconv.datainterfaces import PyPhotometryFiberPhotometryInterface

VOLTS_PER_DIVISION = 0.00010122


def write_ppd_file(file_path, header: dict, analog_values) -> None:
    """Assemble a ``.ppd`` file: a header length, a JSON header, then the packed words."""
    header_bytes = json.dumps(header).encode("utf-8")
    words = np.asarray(analog_values, dtype=np.uint16) << 1
    file_path.write_bytes(len(header_bytes).to_bytes(2, "little") + header_bytes + words.astype("<u2").tobytes())


def paired_header(version="1.1") -> dict:
    return {
        "subject_ID": "test",
        "date_time": "2025-11-18T10:00:00",
        "mode": "2EX_2EM_pulsed",
        "sampling_rate": 130,
        "volts_per_division": [VOLTS_PER_DIVISION, VOLTS_PER_DIVISION],
        "n_analog_signals": 2,
        "n_digital_signals": 2,
        "version": version,
    }


def test_an_unknown_mode_is_refused(tmp_path):
    """A mode the interface does not know must raise rather than fall back to two signals.

    That fallback is what turns the four-colour fork's recording, which is indistinguishable from an
    ordinary two-signal file except by this string, into interleaved colours that look like a trace.
    """
    file_path = tmp_path / "unknown.ppd"
    header = paired_header() | {"mode": "5EX_3EM_whatever"}
    write_ppd_file(file_path, header, [1000, 2000])

    with pytest.raises(ValueError, match="Unknown pyPhotometry acquisition mode '5EX_3EM_whatever'"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path)


def test_a_mode_disagreeing_with_the_declared_signal_count_is_refused(tmp_path):
    """From version 1.0 the header states the count, so a mode contradicting it is not readable."""
    file_path = tmp_path / "contradictory.ppd"
    write_ppd_file(file_path, paired_header() | {"n_analog_signals": 3}, [1000, 2000, 3000])

    with pytest.raises(ValueError, match="interleaves 2 analog lines but the header declares"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path)


def test_a_header_that_is_neither_json_nor_the_fixed_layout_is_refused(tmp_path):
    """A failed JSON parse means the pre-2018 fixed layout, and anything else is not a recording."""
    file_path = tmp_path / "garbage.ppd"
    file_path.write_bytes((8).to_bytes(2, "little") + b"\x00\x01\x02\x03\x04\x05\x06\x07" + b"\x00\x00")

    with pytest.raises(ValueError, match="neither JSON nor the 42-byte fixed layout"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path)


def test_a_version_1_1_recording_warns_that_its_layout_is_unverified(tmp_path):
    """Version 1.1 stores an LED-on sample and an LED-off baseline, and no recording of it exists.

    The interface reads that layout from pyPhotometry's own reader source rather than from a file, so it
    says so instead of presenting the traces as it does every other generation's. This asserts the
    warning, not the traces: certifying values for a layout nobody has seen is what the warning exists to
    avoid.
    """
    file_path = tmp_path / "version_1_1.ppd"
    write_ppd_file(file_path, paired_header(), [1000, 100, 2000, 200, 1010, 110, 2010, 210])

    with pytest.warns(UserWarning, match="this path is untested"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_1")
