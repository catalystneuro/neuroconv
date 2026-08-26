"""Edge cases of the pyPhotometry reader, on files this module writes itself.

Every case here is one no recording covers, which is why the files are written rather than read: a mode
nothing recognizes, a header readable as neither generation, a subject id long enough to fill its fixed
field, and a version 1.1 recording, which exists in no public deposit at all.
"""

import json
from datetime import datetime

import numpy as np
import pytest

from neuroconv.datainterfaces import PyPhotometryFiberPhotometryInterface


def write_ppd_file(tmp_path, header_overrides: dict | None = None, header_bytes: bytes | None = None):
    """Write a ``.ppd``: a two-byte header length, a header, then the packed words.

    Fields passed override a header version 1.1 recording. Passing ``header_bytes`` writes them verbatim
    instead, for the case where the point is a header readable as neither generation.
    """
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


def write_legacy_ppd_file(tmp_path, subject_id: str = "test", mode_code: int = 3):
    """Write a recording with the 42-byte fixed header, packed the way that generation's writer packed it.

    The subject is padded to exactly twelve bytes and the timestamp occupies the nineteen after it, so the
    two are adjacent with no separator when the subject fills its field.
    """
    header = bytearray(42)
    header[0:12] = subject_id.ljust(12).encode("utf-8")
    header[12:31] = b"2018-08-16T08:51:15"
    header[31] = mode_code
    header[32:34] = (200).to_bytes(2, "little")
    header[34:38] = (100708).to_bytes(4, "little")
    header[38:42] = (100708).to_bytes(4, "little")

    words = (np.array([1000, 100, 2000, 200, 1010, 110, 2010, 210], dtype=np.uint16) << 1).astype("<u2")
    file_path = tmp_path / "legacy.ppd"
    file_path.write_bytes(len(header).to_bytes(2, "little") + bytes(header) + words.tobytes())
    return file_path


def test_a_blank_subject_id_writes_no_subject(tmp_path):
    """Every header carries the field, so a blank one means it was left blank in the GUI.

    No published recording has one, since an experimenter who bothers to save a file usually names
    the animal, but the field is free text and nothing enforces it.
    """
    file_path = write_ppd_file(tmp_path, {"subject_ID": "", "version": "1.0"})

    assert "Subject" not in PyPhotometryFiberPhotometryInterface(file_path=file_path).get_metadata()


def test_an_unknown_mode_is_refused(tmp_path):
    """A mode the interface does not know must raise rather than fall back to two signals.

    That fallback is what turns the four-colour fork's recording, which is indistinguishable from an
    ordinary two-signal file except by this string, into interleaved colours that look like a trace.
    """
    file_path = write_ppd_file(tmp_path, {"mode": "5EX_3EM_whatever"})

    with pytest.raises(ValueError, match="Unknown pyPhotometry acquisition mode '5EX_3EM_whatever'"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path)


def test_a_subject_id_filling_its_field_still_leaves_the_timestamp_readable(tmp_path):
    """The fixed header pads the subject to twelve bytes, and the GUI caps the field at twelve.

    So a subject that long leaves no gap before the timestamp, and the two are only separable by
    slicing at the offsets the writer used. Both recordings held have short identifiers, which is why
    this is written here rather than read.
    """
    file_path = write_legacy_ppd_file(tmp_path, subject_id="LONGSUBJECT1")

    metadata = PyPhotometryFiberPhotometryInterface(file_path=file_path).get_metadata()

    assert metadata["Subject"]["subject_id"] == "LONGSUBJECT1"
    assert metadata["NWBFile"]["session_start_time"] == datetime(2018, 8, 16, 8, 51, 15)


def test_an_unknown_legacy_mode_code_is_refused(tmp_path):
    """The code indexes three modes, so a fourth value means the byte is not what we think it is.

    Refusing matches how an unrecognized mode string is treated: the layout comes from the mode, and
    guessing it is what silently interleaves signals.
    """
    file_path = write_legacy_ppd_file(tmp_path, mode_code=7)

    with pytest.raises(ValueError, match="Unknown pyPhotometry mode code 7 in the pre-JSON header"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path)


def test_a_header_that_is_neither_json_nor_the_fixed_layout_is_refused(tmp_path):
    """A failed JSON parse means the pre-2018 fixed layout, and anything else is not a recording.

    Pointing the interface at another file is how this happens: pyPhotometry also exports a CSV, and
    its first two characters become a declared header length.
    """
    file_path = write_ppd_file(tmp_path, header_bytes=b"\x00\x01\x02\x03\x04\x05\x06\x07")

    with pytest.raises(ValueError, match="neither JSON nor the 42-byte fixed layout"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path)


def test_a_version_1_1_recording_warns_that_its_layout_is_unverified(tmp_path):
    """Version 1.1 stores an LED-on sample and an LED-off baseline, and no recording of it exists.

    The interface reads that layout from pyPhotometry's own reader rather than from a file, so it
    says so instead of presenting the traces as it does every other generation's. This asserts the
    warning, not the traces: certifying values for a layout nobody has seen is what it exists to
    avoid.
    """
    file_path = write_ppd_file(tmp_path)

    expected_warning = (
        "This recording states header version 1.1 or later, where a strobed mode stores an LED-on "
        "sample and the LED-off baseline beside it, and the trace written here is their difference. "
        "No file of that version was available when this interface was written, so this path is "
        "untested and its output is less certain than for the other recordings the format has. If "
        "you have such a recording, please open an issue at "
        "https://github.com/catalystneuro/neuroconv/issues so we can test this path and improve it."
    )

    with pytest.warns(UserWarning) as raised:
        PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="detector_1_excitation_1")

    assert str(raised[0].message) == expected_warning
