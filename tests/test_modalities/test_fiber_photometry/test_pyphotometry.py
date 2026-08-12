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


@pytest.fixture
def write_ppd_file(tmp_path):
    """Write a ``.ppd``: a two-byte header length, a header, then the packed words.

    Fields passed override a header version 1.1 recording, which is the generation these tests are
    about. Passing ``header_bytes`` writes them verbatim instead, for the cases where the point is a
    header that cannot be read as either generation.
    """

    def write(header_overrides: dict | None = None, *, header_bytes: bytes | None = None) -> object:
        if header_bytes is None:
            header = {
                "subject_ID": "test",
                "date_time": "2025-11-18T10:00:00",
                "mode": "2EX_2EM_pulsed",
                "sampling_rate": 130,
                "volts_per_division": [0.00010122, 0.00010122],
                "n_analog_signals": 2,
                "n_digital_signals": 2,
                "version": "1.1",
            }
            header_bytes = json.dumps(header | (header_overrides or {})).encode("utf-8")

        words = (np.array([1000, 100, 2000, 200, 1010, 110, 2010, 210], dtype=np.uint16) << 1).astype("<u2")
        file_path = tmp_path / "recording.ppd"
        file_path.write_bytes(len(header_bytes).to_bytes(2, "little") + header_bytes + words.tobytes())
        return file_path

    return write


def test_an_unknown_mode_is_refused(write_ppd_file):
    """A mode the interface does not know must raise rather than fall back to two signals.

    That fallback is what turns the four-colour fork's recording, which is indistinguishable from an
    ordinary two-signal file except by this string, into interleaved colours that look like a trace.
    """
    file_path = write_ppd_file({"mode": "5EX_3EM_whatever"})

    with pytest.raises(ValueError, match="Unknown pyPhotometry acquisition mode '5EX_3EM_whatever'"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path)


def test_a_header_that_is_neither_json_nor_the_fixed_layout_is_refused(write_ppd_file):
    """A failed JSON parse means the pre-2018 fixed layout, and anything else is not a recording.

    Pointing the interface at another file is how this happens: pyPhotometry also exports a CSV, and its
    first two characters become a declared header length.
    """
    file_path = write_ppd_file(header_bytes=b"\x00\x01\x02\x03\x04\x05\x06\x07")

    with pytest.raises(ValueError, match="neither JSON nor the 42-byte fixed layout"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path)


def test_a_version_1_1_recording_warns_that_its_layout_is_unverified(write_ppd_file):
    """Version 1.1 stores an LED-on sample and an LED-off baseline, and no recording of it exists.

    The interface reads that layout from pyPhotometry's own reader source rather than from a file, so it
    says so instead of presenting the traces as it does every other generation's. This asserts the
    warning, not the traces: certifying values for a layout nobody has seen is what the warning exists to
    avoid.
    """
    file_path = write_ppd_file()

    expected_warning = (
        "This recording states header version 1.1 or later, where a strobed mode stores an LED-on sample "
        "and the LED-off baseline beside it, and the trace written here is their difference. No file of "
        "that version was available when this interface was written, so this path is untested and its "
        "output is less certain than for the other recordings the format has. If you have such a "
        "recording, please open an issue at https://github.com/catalystneuro/neuroconv/issues so we can "
        "test this path and improve it."
    )

    with pytest.warns(UserWarning) as raised:
        PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_1")

    assert str(raised[0].message) == expected_warning
