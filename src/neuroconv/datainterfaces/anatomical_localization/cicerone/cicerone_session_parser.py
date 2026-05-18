"""Pure-Python parser for MonkeyCicerone v1.0 plain-text session files.

The session file is a key-value text format. Field meanings and value ranges are
documented in Table 2 of the MonkeyCicerone v1.0 user manual (Miocinovic et al.
2007). Every chamber field name is suffixed with the chamber index (1, 2, or 3).

The parser intentionally ignores fields outside the scope of NWB conversion:
the 4x4 MRI/CT registration matrices, the DICOM folder paths, the Standard
Atlas STL filenames, the site_markers vocabulary, and the per-nucleus
visualisation cosmetics. Those values remain in the file and can be added later
if downstream needs change.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ChamberRecord:
    """One chamber and its single electrode, as represented in the session file.

    All angles are in degrees. All translations are in mm. The frame is
    Cicerone's stereoHf0 (ear bar zero origin, Horsley-Clarke alignment),
    expressed in `(ML, VD, AP)` order with `+x = Left`.
    """

    index: int
    visible: bool
    chamber_angle_deg: float
    chamber_type: str
    electrode_type: str
    translation_ml: float
    translation_vd: float
    translation_ap: float
    vertical_dial_deg: float
    horizontal_dial_deg: float
    skull_fit_dial_deg: float
    plane: int
    eltrans_ml: float
    eltrans_depth: float
    eltrans_ap: float
    calibration_mm: float


@dataclass
class StereotaxicLandmarks:
    """Stereotaxic-frame landmark coordinates as declared in the session file.

    These are scalar offsets in mm relative to Cicerone's stereoHf0 origin.
    Fields not present in the file remain ``None``.
    """

    pc_z_trans: float | None = None
    earbar_y_trans: float | None = None
    earbar_z_trans: float | None = None
    earbar_length: float | None = None
    orbitbar_x_trans: float | None = None
    orbitbar_y_trans: float | None = None
    orbitbar_z_trans: float | None = None
    orbitbar_distance: float | None = None


@dataclass
class CiceroneSession:
    """Top-level structured view of a parsed Cicerone session file."""

    monkey_name: str | None
    monkey_id: str | None
    current_system: str | None
    landmarks: StereotaxicLandmarks
    chambers: list[ChamberRecord] = field(default_factory=list)


_CHAMBER_INDEXED_FIELDS = {
    "chview": "visible",
    "changle": "chamber_angle_deg",
    "chtype": "chamber_type",
    "chelec": "electrode_type",
}

_CHTRANS_FIELDS = {
    "x": "translation_ml",
    "y": "translation_vd",
    "z": "translation_ap",
    "rx": "vertical_dial_deg",
    "ry": "horizontal_dial_deg",
    "rcy": "skull_fit_dial_deg",
    "plane": "plane",
}

_ELTRANS_FIELDS = {
    "x": "eltrans_ml",
    "y": "eltrans_depth",
    "z": "eltrans_ap",
}


def parse_session_file(file_path: str | Path) -> CiceroneSession:
    """Parse a Cicerone session file into a ``CiceroneSession`` dataclass.

    Parameters
    ----------
    file_path : str or Path
        Path to the Cicerone session text file (typically
        ``*_Configuration_*.txt``).

    Returns
    -------
    CiceroneSession
        Structured representation of the session.

    Notes
    -----
    The session file's ``eltrans z`` is documented as being clamped by Cicerone
    to the range ``[-10, 10]`` mm. Sessions sometimes carry out-of-range
    written values (the Orion fixture has ``eltrans z1 = 15``). The parser
    emits a ``UserWarning`` when it encounters such values and keeps the file
    value as written; the caller is responsible for deciding whether to clamp
    when composing the stereotaxic target.
    """
    path = Path(file_path)
    text = path.read_text()

    monkey_name: str | None = None
    monkey_id: str | None = None
    current_system: str | None = None
    landmarks = StereotaxicLandmarks()
    chambers: dict[int, dict] = {}

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        tokens = line.split()
        key = tokens[0]
        rest = tokens[1:]
        if not rest:
            continue

        if key == "MonkeyName":
            monkey_name = rest[0]
        elif key == "MonkeyID":
            monkey_id = rest[0]
        elif key == "current_system":
            current_system = rest[0]
        elif key == "landmarks":
            _apply_landmark(landmarks, rest)
        elif key == "chtrans":
            _apply_chtrans(chambers, rest)
        elif key == "eltrans":
            _apply_eltrans(chambers, rest)
        elif key == "calibration":
            _apply_calibration(chambers, rest)
        else:
            _maybe_apply_indexed(key, rest, chambers)

    chamber_records = [
        _build_chamber_record(index, fields, file_path=str(path)) for index, fields in sorted(chambers.items())
    ]

    return CiceroneSession(
        monkey_name=monkey_name,
        monkey_id=monkey_id,
        current_system=current_system,
        landmarks=landmarks,
        chambers=chamber_records,
    )


def _apply_landmark(landmarks: StereotaxicLandmarks, tokens: list[str]) -> None:
    name = tokens[0]
    value = float(tokens[1])
    if hasattr(landmarks, name):
        setattr(landmarks, name, value)


def _apply_chtrans(chambers: dict[int, dict], tokens: list[str]) -> None:
    component_with_index, value_str = tokens[0], tokens[1]
    component, index = _split_indexed(component_with_index)
    if component not in _CHTRANS_FIELDS:
        return
    field_name = _CHTRANS_FIELDS[component]
    chambers.setdefault(index, {})[field_name] = int(value_str) if component == "plane" else float(value_str)


def _apply_eltrans(chambers: dict[int, dict], tokens: list[str]) -> None:
    component_with_index, value_str = tokens[0], tokens[1]
    component, index = _split_indexed(component_with_index)
    if component not in _ELTRANS_FIELDS:
        return
    chambers.setdefault(index, {})[_ELTRANS_FIELDS[component]] = float(value_str)


def _apply_calibration(chambers: dict[int, dict], tokens: list[str]) -> None:
    component_with_index, value_str = tokens[0], tokens[1]
    component, index = _split_indexed(component_with_index)
    if component != "elec" or index is None:
        return
    chambers.setdefault(index, {})["calibration_mm"] = float(value_str)


def _maybe_apply_indexed(key: str, tokens: list[str], chambers: dict[int, dict]) -> None:
    base, index = _split_indexed(key)
    if index is None or base not in _CHAMBER_INDEXED_FIELDS:
        return
    field_name = _CHAMBER_INDEXED_FIELDS[base]
    value_str = tokens[0]
    if base == "chview":
        chambers.setdefault(index, {})[field_name] = bool(int(value_str))
    elif base == "changle":
        chambers.setdefault(index, {})[field_name] = float(value_str)
    else:
        chambers.setdefault(index, {})[field_name] = value_str


_INDEXED_TOKEN = re.compile(r"^([A-Za-z]+)(\d+)$")


def _split_indexed(token: str) -> tuple[str, int | None]:
    match = _INDEXED_TOKEN.match(token)
    if match is None:
        return token, None
    return match.group(1), int(match.group(2))


def _build_chamber_record(index: int, fields: dict, file_path: str) -> ChamberRecord:
    defaults = dict(
        visible=True,
        chamber_angle_deg=0.0,
        chamber_type="micro",
        electrode_type="micro",
        translation_ml=0.0,
        translation_vd=0.0,
        translation_ap=0.0,
        vertical_dial_deg=0.0,
        horizontal_dial_deg=0.0,
        skull_fit_dial_deg=0.0,
        plane=0,
        eltrans_ml=0.0,
        eltrans_depth=0.0,
        eltrans_ap=0.0,
        calibration_mm=0.0,
    )
    defaults.update(fields)

    eltrans_ap = defaults["eltrans_ap"]
    if abs(eltrans_ap) > 10:
        warnings.warn(
            f"Cicerone session at {file_path!r}: eltrans_ap for chamber {index} is "
            f"{eltrans_ap}, outside the documented range [-10, 10]. Cicerone's GUI "
            f"silently clamps to this range; the value as written is kept here for "
            f"fidelity.",
            UserWarning,
            stacklevel=2,
        )

    return ChamberRecord(index=index, **defaults)
