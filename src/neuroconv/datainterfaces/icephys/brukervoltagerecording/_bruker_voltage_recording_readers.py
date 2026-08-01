"""Parsing helpers for the CSV/XML pair Bruker PrairieView writes per VoltageRecording cycle."""

import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

# PrairieView stamps each cycle with .NET's round-trip datetime format, whose fractional part runs to seven
# digits; datetime.fromisoformat accepts at most six before Python 3.11, so the tail is trimmed off.
_EXCESS_FRACTIONAL_SECONDS = re.compile(r"(\.\d{6})\d+")

# The acquisition stem PrairieView writes into `DataFile`, for example
# "cell1-001_Cycle00001_VoltageRecording_001". Stripping the per-cycle tail leaves the stem its cycles share.
_CYCLE_SUFFIX = re.compile(r"_Cycle\d+_VoltageRecording_\d+$")

# How far the sampling interval implied by the CSV's own time column may sit from the XML's `Rate` before the
# two are called inconsistent. Generous, since the check exists to catch a header describing different data,
# not to measure clock jitter (the time column is generated from the same nominal rate).
_RATE_AGREEMENT_TOLERANCE = 1e-3


@dataclass(frozen=True)
class _VRecSignal:
    """One ``SignalList`` entry: an input the acquisition card can sample, recorded or not."""

    name: str
    enabled: bool
    unit_name: str
    multiplier: float
    divisor: float
    patchclamp_device: str


@dataclass(frozen=True)
class _CycleHeader:
    """What one cycle's XML and CSV header state, with no samples read."""

    file_path: Path
    xml_file_path: Path
    stem: str
    rate: float
    start_datetime: datetime
    signal_column_names: list[str]
    signals: dict[str, _VRecSignal]

    def column_index(self, signal_name: str) -> int:
        """Position of a recorded signal's column in the CSV, past the leading time column."""
        return self.signal_column_names.index(signal_name) + 1


def _parse_prairie_view_datetime(text: str) -> datetime:
    """Parse a ``DateTime`` element, which carries the rig's UTC offset and needs no timezone guessing."""
    return datetime.fromisoformat(_EXCESS_FRACTIONAL_SECONDS.sub(r"\1", text.strip()))


def _read_cycle_header(file_path: Path) -> _CycleHeader:
    """
    Read one cycle's metadata from its XML and the CSV's header line, without loading any samples.

    The XML is the CSV's sibling; PrairieView names both from the same ``DataFile`` stem. The CSV header is the
    authority on which signals were actually recorded (``Enabled`` selects them at acquisition time, but the
    header states the outcome), and its first column is the time base.
    """
    file_path = Path(file_path)
    xml_file_path = file_path.with_suffix(".xml")
    if not xml_file_path.is_file():
        raise FileNotFoundError(
            f"No VoltageRecording XML beside '{file_path}'. PrairieView writes '{xml_file_path.name}' next to "
            "the CSV, and it carries the units, scaling and acquisition time the CSV does not."
        )

    root = ElementTree.parse(xml_file_path).getroot()
    if root.tag != "VRecSessionEntry":
        raise ValueError(
            f"'{xml_file_path}' has root element '{root.tag}', expected 'VRecSessionEntry'. This interface reads "
            "the per-cycle VoltageRecording XML, not PrairieView's master 'PVScan' XML."
        )

    signals = {}
    for element in root.findall(".//VRecSignal"):
        unit = element.find("Unit")
        name = element.findtext("Name")
        signals[name] = _VRecSignal(
            name=name,
            enabled=element.findtext("Enabled", "").strip().lower() == "true",
            unit_name=(unit.findtext("UnitName") or "").strip(),
            multiplier=float(unit.findtext("Multiplier")),
            divisor=float(unit.findtext("Divisor")),
            patchclamp_device=(unit.findtext("PatchclampDevice") or "").strip(),
        )

    rate = float(root.findtext(".//Rate"))
    start_datetime = _parse_prairie_view_datetime(root.findtext("DateTime"))
    stem = _CYCLE_SUFFIX.sub("", root.findtext("DataFile").strip())

    signal_column_names, sampling_interval_ms = _read_csv_header(file_path)
    _check_time_column_agrees_with_rate(file_path=file_path, rate=rate, sampling_interval_ms=sampling_interval_ms)

    return _CycleHeader(
        file_path=file_path,
        xml_file_path=xml_file_path,
        stem=stem,
        rate=rate,
        start_datetime=start_datetime,
        signal_column_names=signal_column_names,
        signals=signals,
    )


def _read_csv_header(file_path: Path) -> tuple[list[str], float | None]:
    """
    Return the recorded signal column names and the interval between the first two samples, in milliseconds.

    Only three lines are read. The column names carry a leading space in the file (``"Time(ms), Primary"``),
    which is stripped here so callers match them against the XML's ``Name`` values directly.
    """
    with open(file_path, "r") as file:
        header_line = file.readline()
        first_rows = [file.readline(), file.readline()]

    column_names = [name.strip() for name in header_line.split(",")]
    if not column_names or not column_names[0].startswith("Time"):
        raise ValueError(
            f"'{file_path}' does not look like a VoltageRecording CSV: its first column is "
            f"'{column_names[0] if column_names else ''}', expected the 'Time(ms)' time base."
        )

    times = [float(row.split(",", 1)[0]) for row in first_rows if row.strip()]
    sampling_interval_ms = times[1] - times[0] if len(times) == 2 else None
    return column_names[1:], sampling_interval_ms


def _check_time_column_agrees_with_rate(file_path: Path, rate: float, sampling_interval_ms: float | None) -> None:
    """Fail loudly when the XML's ``Rate`` and the CSV's own time column describe different acquisitions."""
    if sampling_interval_ms is None:
        return
    implied_rate = 1000.0 / sampling_interval_ms
    if abs(implied_rate - rate) / rate > _RATE_AGREEMENT_TOLERANCE:
        raise ValueError(
            f"'{file_path}' and its XML disagree on the sampling rate: the XML states {rate} Hz while the CSV's "
            f"time column steps by {sampling_interval_ms} ms ({implied_rate} Hz). The pair may be mismatched."
        )


def _read_signal_column(header: _CycleHeader, signal_name: str) -> np.ndarray:
    """Read one recorded signal's samples, as written, leaving the scaling to the series' ``conversion``."""
    import pandas as pd

    column_index = header.column_index(signal_name)
    frame = pd.read_csv(header.file_path, usecols=[column_index], dtype="float64")
    return frame.to_numpy().reshape(-1)
