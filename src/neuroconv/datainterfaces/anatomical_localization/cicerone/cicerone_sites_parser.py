"""Pure-Python parser for MonkeyCicerone v1.0 sites files.

Sites files are tab-separated text written by Cicerone whenever the operator
saves a recording site (``Describe Site`` in the GUI, or pressing ``s``). The
file accumulates rows across one or more recording sessions. Each row carries
chamber-local microdrive coordinates (``AP``, ``ML``, ``Depth``) plus
clinical-observation columns (``Location``, ``SiteComment``, ``MotorResponse``,
``MicrostimResponse``, ``RecordFile``).

Column inventory follows Table 1 of the MonkeyCicerone v1.0 user manual,
Appendix. 17 columns total.

This parser does no math and no filtering. The caller (the interface)
filters by ``SiteNumber`` and joins each row to its chamber pose using the
chamber index against a separately-parsed configuration file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SiteRecord:
    """One recording site as written by Cicerone, one row of the sites file.

    Microdrive coordinates (``ap``, ``ml``, ``depth``) and the calibration
    value are in mm in the chamber's local frame. ``depth`` is negative for
    advanced electrodes (deeper into the brain) per Cicerone's GUI convention.

    String columns (``track_comment``, ``location``, ``site_comment``,
    ``motor_response``, ``microstim_response``, ``record_file``, ``date``)
    are kept verbatim from the file; blank cells become empty strings.
    """

    site_number: int
    track_number: int
    ap: float
    ml: float
    chamber: int
    monkey_id: str
    monkey_name: str
    track_comment: str
    date: str
    depth: float
    location: str
    site_comment: str
    motor_response: str
    microstim_response: str
    record_file: str
    electrode_calibr: float
    electrode_number: int


_COLUMN_ORDER = (
    "SiteNumber",
    "TrackNumber",
    "AP",
    "ML",
    "Chamber",
    "MonkeyID",
    "MonkeyName",
    "TrackComment",
    "Date",
    "Depth",
    "Location",
    "SiteComment",
    "MotorResponse",
    "MicrostimResponse",
    "RecordFile",
    "ElectrodeCalibr",
    "ElectrodeNumber",
)

_INT_COLUMNS = {"SiteNumber", "TrackNumber", "Chamber", "ElectrodeNumber"}
_FLOAT_COLUMNS = {"AP", "ML", "Depth", "ElectrodeCalibr"}

_COLUMN_TO_FIELD = {
    "SiteNumber": "site_number",
    "TrackNumber": "track_number",
    "AP": "ap",
    "ML": "ml",
    "Chamber": "chamber",
    "MonkeyID": "monkey_id",
    "MonkeyName": "monkey_name",
    "TrackComment": "track_comment",
    "Date": "date",
    "Depth": "depth",
    "Location": "location",
    "SiteComment": "site_comment",
    "MotorResponse": "motor_response",
    "MicrostimResponse": "microstim_response",
    "RecordFile": "record_file",
    "ElectrodeCalibr": "electrode_calibr",
    "ElectrodeNumber": "electrode_number",
}


def parse_sites_file(file_path: str | Path) -> list[SiteRecord]:
    """Parse a Cicerone sites file into a list of ``SiteRecord``s.

    Parameters
    ----------
    file_path : str or Path
        Path to the tab-separated sites file (typically
        ``Cicerone_Sites_<date>.txt`` or the bundled sample
        ``Cicerone_sample_MER.txt``).

    Returns
    -------
    list of SiteRecord
        One entry per data row in the file (header row excluded).

    Raises
    ------
    ValueError
        If the file's header line does not match the expected 17-column
        layout from Table 1 of the user manual.
    """
    path = Path(file_path)
    text = path.read_text()
    lines = text.splitlines()
    if not lines:
        raise ValueError(f"Sites file {path!r} is empty")

    header_tokens = lines[0].split("\t")
    if tuple(token.strip() for token in header_tokens) != _COLUMN_ORDER:
        raise ValueError(
            f"Sites file {path!r} header does not match the expected MonkeyCicerone "
            f"column order. Expected {_COLUMN_ORDER}, got {tuple(header_tokens)}."
        )

    records: list[SiteRecord] = []
    for line_number, raw in enumerate(lines[1:], start=2):
        if not raw.strip():
            continue
        tokens = raw.split("\t")
        # Pad with blanks so the loop below does not IndexError on trailing
        # blank cells (Cicerone writes blank fields as empty between tabs,
        # but a row ending in blanks may have been right-stripped on save).
        if len(tokens) < len(_COLUMN_ORDER):
            tokens = tokens + [""] * (len(_COLUMN_ORDER) - len(tokens))
        elif len(tokens) > len(_COLUMN_ORDER):
            raise ValueError(
                f"Sites file {path!r} line {line_number}: expected "
                f"{len(_COLUMN_ORDER)} tab-separated columns, got {len(tokens)}."
            )

        kwargs = {}
        for column, value in zip(_COLUMN_ORDER, tokens):
            field = _COLUMN_TO_FIELD[column]
            value = value.strip()
            if column in _INT_COLUMNS:
                kwargs[field] = int(value) if value else 0
            elif column in _FLOAT_COLUMNS:
                kwargs[field] = float(value) if value else 0.0
            else:
                kwargs[field] = value
        records.append(SiteRecord(**kwargs))

    return records
