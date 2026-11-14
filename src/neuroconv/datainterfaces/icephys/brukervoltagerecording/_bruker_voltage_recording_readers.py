"""Parsing helpers for the CSV/XML pair Bruker PrairieView writes per VoltageRecording cycle."""

import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np

# The fractional-seconds part of a `DateTime`, however many digits PrairieView wrote.
_NORMALIZE_FRACTIONAL_SECONDS = re.compile(r"\.(\d+)")

# The acquisition stem PrairieView writes into `DataFile`, for example
# "cell1-001_Cycle00001_VoltageRecording_001". Stripping the per-cycle tail leaves the stem its cycles share.
_CYCLE_SUFFIX = re.compile(r"_Cycle\d+_VoltageRecording_\d+$")


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
    # The acquisition's PVScan XML the start was read from, or None when it was missing and the start is `DateTime`.
    pvscan_xml_file_path: Path | None
    recorded_signals: list[_VRecSignal]
    header_names: list[str]
    signals: dict[str, _VRecSignal]

    def column_index(self, signal_name: str) -> int:
        """Position of a recorded signal's column in the CSV, past the leading time column.

        Resolved by position in the enabled ``SignalList``, never by matching the CSV header's names. The
        header names are wrong on real published data: a whole recording day of the Zhai et al. 2025 deposit
        carries ``Time(ms), Secondary, LED`` on files whose enabled signals are ``Primary`` and ``Secondary``,
        and the physiology (a current step in one column evoking spikes in the other) shows the XML is right.
        """
        names = [signal.name for signal in self.recorded_signals]
        return names.index(signal_name) + 1


def _parse_prairie_view_datetime(text: str) -> datetime:
    """Parse a ``DateTime`` element, which carries the rig's UTC offset and needs no timezone guessing."""
    return datetime.fromisoformat(_NORMALIZE_FRACTIONAL_SECONDS.sub(_pad_fractional_seconds, text.strip()))


def _pad_fractional_seconds(match: "re.Match") -> str:
    """Render the fractional part as exactly six digits.

    PrairieView writes .NET's round-trip format, whose fraction is as long as it needs to be: seven digits
    usually, but five in some 2016 files. Before Python 3.11 ``datetime.fromisoformat`` accepts exactly three
    or exactly six, so both the long and the short case have to be normalized, not just truncated.
    """
    return "." + match.group(1)[:6].ljust(6, "0")


def _read_cycle_header(file_path: Path) -> _CycleHeader:
    """
    Read one cycle's metadata from its XML and the CSV's header line, without loading any samples.

    The XML is the CSV's sibling; PrairieView names both from the same ``DataFile`` stem. The XML's ``Enabled`` flags are the
    authority on which signals were recorded and in what order; the CSV header's names are not (see
    ``_CycleHeader.column_index``). The CSV's first column is the time base.
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

    declared_signals = []
    for element in root.findall(".//VRecSignal"):
        unit = element.find("Unit")
        if unit is None:
            raise ValueError(f"A VRecSignal in '{xml_file_path}' has no Unit block, so it cannot be scaled.")
        name = element.findtext("Name")
        declared_signals.append(
            _VRecSignal(
                name=name,
                enabled=element.findtext("Enabled", "").strip().lower() == "true",
                unit_name=(unit.findtext("UnitName") or "").strip(),
                multiplier=_required_float(unit, "Multiplier", xml_file_path),
                divisor=_required_float(unit, "Divisor", xml_file_path),
                patchclamp_device=(unit.findtext("PatchclampDevice") or "").strip(),
            )
        )

    # The enabled signals, in SignalList order, are the CSV's columns in order. Names can repeat (they are
    # operator-editable free text), so the list is the authority and the dict is only a lookup convenience.
    recorded_signals = [signal for signal in declared_signals if signal.enabled]
    _check_names_are_unique(recorded_signals, xml_file_path)
    signals = {signal.name: signal for signal in declared_signals}

    nominal_rate = _required_float(root, ".//Rate", xml_file_path)
    start_datetime = _parse_prairie_view_datetime(_required_text(root, "DateTime", xml_file_path))
    pvscan_xml_file_path = _find_pvscan_xml(file_path)
    if pvscan_xml_file_path is not None:
        start_datetime = _read_sequence_start_datetime(
            pvscan_xml_file_path=pvscan_xml_file_path, file_path=file_path, date_time=start_datetime
        )
    stem = _CYCLE_SUFFIX.sub("", _required_text(root, "DataFile", xml_file_path))

    header_names, sampling_interval_ms = _read_csv_header(file_path)
    # The CSV's own time column wins over the XML's `Rate`, which is nominal and can genuinely differ: one
    # public recording declares 29.9999850000075 Hz while its time column steps at exactly 29 Hz throughout.
    # Treating that as a mismatch rejected a perfectly good file, so the data is taken as the authority.
    rate = 1000.0 / sampling_interval_ms if sampling_interval_ms else nominal_rate
    _check_column_count(
        file_path=file_path,
        xml_file_path=xml_file_path,
        recorded_signals=recorded_signals,
        header_names=header_names,
    )

    return _CycleHeader(
        file_path=file_path,
        xml_file_path=xml_file_path,
        stem=stem,
        rate=rate,
        start_datetime=start_datetime,
        pvscan_xml_file_path=pvscan_xml_file_path,
        recorded_signals=recorded_signals,
        header_names=header_names,
        signals=signals,
    )


def _find_pvscan_xml(file_path: Path) -> Path | None:
    """
    Return the acquisition's PVScan XML beside a cycle CSV, or None when it is not there.

    PrairieView names it after the acquisition, the cycle file name before ``_Cycle``, so it is looked up by
    that stem and not by the folder name, which deposits often rename.
    """
    acquisition_stem, match_count = _CYCLE_SUFFIX.subn("", file_path.stem)
    pvscan_xml_file_path = file_path.with_name(f"{acquisition_stem}.xml")
    if match_count == 0 or not pvscan_xml_file_path.is_file():
        return None
    return pvscan_xml_file_path


def _read_sequence_start_datetime(pvscan_xml_file_path: Path, file_path: Path, date_time: datetime) -> datetime:
    """
    Read a cycle's start from the ``Sequence`` the PVScan XML lists it under.

    The cycle's own ``DateTime`` can be seconds early (24.9 s at most on the Zhai et al. 2025 deposit), while
    the ``Sequence`` time agrees with the PVScan XML's ``date`` and with the files' modification times. The
    recording starts at the ``Sequence`` time plus the ``absoluteTime`` the PVScan XML gives the cycle's
    ``VoltageRecording``. The ``Sequence`` time has no date and no zone, so the date comes from the PVScan
    XML's ``date`` and the zone from ``date_time``, the cycle's ``DateTime``.
    """
    root = ElementTree.parse(pvscan_xml_file_path).getroot()
    for sequence in root.findall("Sequence"):
        for voltage_recording in sequence.findall("VoltageRecording"):
            if voltage_recording.get("dataFile") == file_path.name:
                # `date` reads "5/27/2016 6:43:47 PM", and only its date is needed.
                date = datetime.strptime(root.get("date").split(" ")[0], "%m/%d/%Y").date()
                sequence_time = time.fromisoformat(
                    _NORMALIZE_FRACTIONAL_SECONDS.sub(_pad_fractional_seconds, sequence.get("time"))
                )
                sequence_start = datetime.combine(date, sequence_time, tzinfo=date_time.tzinfo)
                return sequence_start + timedelta(seconds=float(voltage_recording.get("absoluteTime")))

    raise ValueError(
        f"'{pvscan_xml_file_path}' lists no VoltageRecording with dataFile '{file_path.name}', so the start of "
        "that cycle cannot be read from it."
    )


def _required_text(element, path: str, xml_file_path: Path) -> str:
    """Read a required element's text, naming the missing element rather than raising on ``None``."""
    text = element.findtext(path)
    if text is None:
        raise ValueError(f"'{xml_file_path}' has no <{path.lstrip('./')}> element, which is required.")
    return text.strip()


def _required_float(element, path: str, xml_file_path: Path) -> float:
    """Read a required element's text as a float, naming the element when it is missing or unparsable."""
    text = _required_text(element, path, xml_file_path)
    try:
        return float(text)
    except ValueError as exception:
        raise ValueError(f"'{xml_file_path}' has a non-numeric <{path.lstrip('./')}> of {text!r}.") from exception


def _check_names_are_unique(recorded_signals: list[_VRecSignal], xml_file_path: Path) -> None:
    """Reject a duplicated signal name, which would make a name ambiguous as a column selector."""
    names = [signal.name for signal in recorded_signals]
    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        raise ValueError(
            f"'{xml_file_path}' records more than one signal named {', '.join(sorted(duplicates))}, so a name "
            "cannot identify a column. Signal names are operator-editable, so this is a rig configuration issue."
        )


def _check_column_count(
    file_path: Path, xml_file_path: Path, recorded_signals: list[_VRecSignal], header_names: list[str]
) -> None:
    """
    Require as many data columns as enabled signals, which is what makes the positional mapping safe.

    The header's *names* are not checked, deliberately: they are wrong in real published data (see
    ``_CycleHeader.column_index``). The count is a different matter, since a mismatch means neither the XML
    nor the header describes the file and no mapping can be trusted.
    """
    if len(header_names) != len(recorded_signals):
        enabled = ", ".join(signal.name for signal in recorded_signals) or "none"
        raise ValueError(
            f"'{file_path}' has {len(header_names)} data column(s) ({', '.join(header_names) or 'none'}) but "
            f"'{xml_file_path.name}' marks {len(recorded_signals)} signal(s) as enabled ({enabled}). The pair "
            "does not describe one acquisition, so which column is which cannot be determined."
        )


def _read_csv_header(file_path: Path) -> tuple[list[str], float | None]:
    """
    Return the header's column names and the interval between the first two samples, in milliseconds.

    Only three lines are read. The names carry a leading space in the file (``"Time(ms), Primary"``) and are
    stripped, but they are returned for reporting only: column identity comes from the XML's enabled signals,
    since these names are wrong on real data (see ``_CycleHeader.column_index``).
    """
    with open(file_path, "r", encoding="utf-8") as file:
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


def _read_signal_column(header: _CycleHeader, signal_name: str) -> np.ndarray:
    """Read one recorded signal's samples, as written, leaving the scaling to the series' ``conversion``."""
    import pandas as pd

    column_index = header.column_index(signal_name)
    frame = pd.read_csv(header.file_path, usecols=[column_index], dtype="float64")
    return frame.to_numpy().reshape(-1)


@dataclass(frozen=True)
class _CommandWaveform:
    """One output line's command during one cycle, drawn sample by sample from the cycle's protocol."""

    unit_name: str
    rate: float
    data: np.ndarray


# Pulse-train fields this reader does not draw, with the value at which they have no effect. Every enabled
# waveform of the Zhai et al. 2025 deposit (5,338 protocols) holds these values, so no file is known to show how
# PrairieView plays the others.
_UNDRAWN_PULSE_TRAIN_FIELDS = {"Repetitions": 1.0, "PulsePotentialDelta": 0.0, "RestPotential": 0.0}


def _read_enabled_waveforms(header: _CycleHeader) -> tuple[Path, ElementTree.Element, dict]:
    """
    Read the cycle's ``VoltageOutput`` XML: its path, its root and its enabled waveforms by name.

    PrairieView writes this protocol beside the recording, named from the same stem
    (``cell1-001_Cycle00001_VoltageOutput_001.xml``), with one ``Waveform`` per analog output line.
    """
    file_path = header.xml_file_path.with_name(
        header.xml_file_path.name.replace("_VoltageRecording_", "_VoltageOutput_")
    )
    if not file_path.is_file():
        raise FileNotFoundError(
            f"No VoltageOutput XML beside '{header.file_path}'. PrairieView writes '{file_path.name}' next to the "
            "recording, and the stimulus is drawn from it."
        )
    root = ElementTree.parse(file_path).getroot()
    waveforms = {
        waveform.findtext("Name"): waveform
        for waveform in root.findall("Waveform")
        if waveform.findtext("Enabled", "").strip().lower() == "true"
    }
    return file_path, root, waveforms


def _read_command_waveform(header: _CycleHeader, command_name: str) -> _CommandWaveform:
    """
    Draw the command one output waveform played during a cycle, from the cycle's ``VoltageOutput`` XML.

    A waveform is a sequence of components played back to back. A pulse-train component waits its
    ``FirstPulseDelay``, gives ``PulseCount`` pulses of ``PulseWidth`` at ``PulsePotentialStart`` separated by
    ``PulseSpacing``, and ends with its last pulse. Times are in milliseconds and levels in volts on the output
    line, which ``UnitScaleFactor`` takes into the waveform's ``Units``. On the dendritic runs of the Zhai et al.
    2025 deposit, a 100 ms component followed by three pulses 900 ms into the next puts the pulses at 1000, 1020
    and 1040 ms, which is when the recorded spikes occur.

    The command is drawn at the protocol's ``UpdateRate`` over the span of its components, which can end before
    or after the recording does.
    """
    file_path, root, waveforms = _read_enabled_waveforms(header)
    if command_name not in waveforms:
        raise ValueError(
            f"'{file_path.name}' has no enabled waveform named '{command_name}'. Enabled waveforms: "
            f"{', '.join(waveforms) or 'none'}."
        )
    waveform = waveforms[command_name]
    for field in ("UnitVoltageOffset", "UnitScaleOffset"):
        if _required_float(waveform, field, file_path) != 0:
            raise ValueError(
                f"Waveform '{command_name}' of '{file_path.name}' has a non-zero {field}, which this reader does "
                "not apply."
            )
    scale_factor = Decimal(_required_text(waveform, "UnitScaleFactor", file_path))
    rate = _required_float(root, "UpdateRate", file_path)

    pulses = []
    component_start = 0.0
    for component in waveform:
        if not component.tag.startswith("WaveformComponent_"):
            continue
        if component.tag != "WaveformComponent_PulseTrain":
            raise ValueError(
                f"Waveform '{command_name}' of '{file_path.name}' has a {component.tag} component; only pulse "
                "trains can be drawn."
            )
        for field, undrawn_value in _UNDRAWN_PULSE_TRAIN_FIELDS.items():
            if _required_float(component, field, file_path) != undrawn_value:
                raise ValueError(
                    f"Component '{component.findtext('Name')}' of waveform '{command_name}' in '{file_path.name}' "
                    f"has {field} {component.findtext(field)}, which this reader does not draw."
                )
        count = int(_required_float(component, "PulseCount", file_path))
        width = _required_float(component, "PulseWidth", file_path)
        spacing = _required_float(component, "PulseSpacing", file_path)
        first_pulse_start = component_start + _required_float(component, "FirstPulseDelay", file_path)
        # In decimal, so 0.55 V at 400 pA/V is 220 pA and not 220.00000000000003.
        level = float(Decimal(_required_text(component, "PulsePotentialStart", file_path)) * scale_factor)
        pulses.extend((first_pulse_start + number * (width + spacing), width, level) for number in range(count))
        component_start = first_pulse_start + count * width + (count - 1) * spacing

    data = np.zeros(round(component_start * rate / 1000))
    for start, width, level in pulses:
        data[round(start * rate / 1000) : round((start + width) * rate / 1000)] = level
    return _CommandWaveform(unit_name=_required_text(waveform, "Units", file_path), rate=rate, data=data)
