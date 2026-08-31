"""Reader for BORIS project files, independent of NWB.

A ``.boris`` file is one JSON document holding the whole record: the coding scheme in ``behaviors_conf``,
the subjects, and every observation with its events. This module turns that document into the dataclasses
below and does the one thing the file leaves to the reader, which is pairing a state behavior's start row
with its stop row. Nothing here knows about NWB, so the same reader serves whatever the events land in.
"""

import json
import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path

# What a behavior's `type` reads in the file. BORIS writes the prose form, not a flag.
_POINT_EVENT = "Point event"
_STATE_EVENT = "State event"

# The placeholder BORIS writes in an event's subject position when nothing is focal. It is not a subject:
# it never appears in `subjects_conf`, and the empty string means the same thing.
_NO_FOCAL_SUBJECT = "No focal subject"

# Slot indices into an event row: [time, subject, behavior code, modifiers, comment].
_TIME, _SUBJECT, _CODE, _MODIFIERS, _COMMENT = range(5)

# `modifiers` on a behavior became a dict of slot objects in this project format version; before it, and
# in every file older than it, it is one flat comma-separated string of the declared values.
_SLOT_DICT_FROM_VERSION = 7.0


@dataclass
class BorisModifierSlot:
    """One declared modifier dimension of a behavior.

    Attributes
    ----------
    name : str
        The slot's label, as typed by whoever built the ethogram, whitespace included.
    slot_type : int
        0 is a single selection from ``values``, 1 a multiple selection from it, 2 a free numeric value,
        which declares no values at all.
    values : list of str
        The declared menu entries, each possibly carrying a trailing ``" (key)"`` that the recorded value
        does not.
    """

    name: str
    slot_type: int
    values: list[str] = field(default_factory=list)


@dataclass
class BorisBehavior:
    """One entry of the coding scheme.

    Attributes
    ----------
    code : str
        The behavior's name, and the handle every event row uses.
    behavior_type : str
        ``"point"`` or ``"state"``, declared in the scheme rather than marked on the rows.
    description : str
        The operational definition, where the scheme's author wrote one.
    category : str
        The behavioral category this behavior belongs to; empty where the project declares none, and
        always empty in format 1.6, which has no category field.
    native_code : int
        The behavior's integer key in ``behaviors_conf``.
    excluded : list of str
        The codes that starting this behavior terminates.
    modifier_slots : list of BorisModifierSlot
        The declared modifier dimensions, empty where the behavior has none.
    """

    code: str
    behavior_type: str
    description: str
    category: str
    native_code: int
    excluded: list[str] = field(default_factory=list)
    modifier_slots: list[BorisModifierSlot] = field(default_factory=list)


@dataclass
class BorisOccurrence:
    """One thing that happened, after the start and stop rows of a state bout have been paired.

    Attributes
    ----------
    onset : float
        The time of the event, or of the bout's start, in seconds on the observation's own clock. The
        observation's ``time offset`` is not applied here; it is a rigid shift and belongs to alignment.
    subject : str
        The subject the event was attributed to, or the empty string for nobody.
    code : str
        The behavior code, joining this occurrence to its entry in the coding scheme.
    modifiers : str
        The recorded modifier string, exactly as written.
    comment : str
        The coder's free-text comment, from the row that opened the occurrence.
    stop_comment : str
        The comment on the row that closed a state bout, empty where there was none and on a point
        behavior, which has no closing row. A bout is two rows and both carry a comment field, so a coder
        can say one thing at the start and another at the end, and the second is usually how it ended.
    stop_modifiers : str
        The modifier string on the row that closed a state bout. Almost always the same string as
        ``modifiers``, since BORIS carries the value forward, so it says something new only where the
        coder changed the answer while the bout ran.
    duration : float or None
        ``None`` for a point behavior, which has no extent. For a state behavior, the length of the bout,
        or ``nan`` where the bout opened and never closed.
    """

    onset: float
    subject: str
    code: str
    modifiers: str
    comment: str
    duration: float | None
    stop_comment: str = ""
    stop_modifiers: str = ""


@dataclass
class BorisObservation:
    """One scoring session and its events.

    Attributes
    ----------
    name : str
        The observation's key in the project's ``observations`` block.
    observation_type : str
        ``"MEDIA"`` for an observation scored against recorded files, ``"LIVE"`` for one scored against a
        clock started when the coder began.
    time_offset : float
        The rigid shift the observation declares, in seconds.
    media_files : list of str
        The media this observation was scored against, in player order. Empty for a ``LIVE`` observation.
    frame_rate : float or None
        The frame rate of the first medium, where the observation has one. ``None`` for ``LIVE``, which has
        no frame rate anywhere.
    occurrences : list of BorisOccurrence
        The events, in the order their first row appears in the file.
    """

    name: str
    observation_type: str
    time_offset: float
    media_files: list[str]
    frame_rate: float | None
    occurrences: list[BorisOccurrence]


@dataclass
class BorisProject:
    """A parsed ``.boris`` document.

    Attributes
    ----------
    format_version : float
        The project format version the file declares, which is the first branch a reader takes.
    behaviors : dict of str to BorisBehavior
        The complete coding scheme, keyed by behavior code, including behaviors nothing was ever scored
        against.
    subject_names : list of str
        The subjects the project declares. An event may name one of these or nobody, and the two need not
        agree, so this is the declared roster rather than an inventory of what occurs.
    observation_names : list of str
        The observations the project holds, in file order.
    """

    format_version: float
    behaviors: dict[str, BorisBehavior]
    subject_names: list[str]
    observation_names: list[str]


def read_boris_project(file_path: str | Path) -> BorisProject:
    """Read a ``.boris`` file's coding scheme, subjects and observation names.

    Parameters
    ----------
    file_path : str or pathlib.Path
        Path to the ``.boris`` JSON document.

    Returns
    -------
    BorisProject
        The parsed project. The observations themselves are read separately, one at a time, by
        :func:`read_boris_observation`.
    """
    document = _read_document(file_path=file_path)
    format_version = _format_version(document=document)
    return BorisProject(
        format_version=format_version,
        behaviors=_read_behaviors(document=document, format_version=format_version),
        subject_names=[entry["name"] for entry in document.get("subjects_conf", {}).values()],
        observation_names=list(document.get("observations", {})),
    )


def get_observation_names(file_path: str | Path) -> list[str]:
    """Return the names of the observations a ``.boris`` file holds, in file order.

    Parameters
    ----------
    file_path : str or pathlib.Path
        Path to the ``.boris`` JSON document.

    Returns
    -------
    list of str
        The observation names, which are the handles an interface takes to select one. Empty where the
        project declares a coding scheme and was never coded against, which is a legal file.
    """
    return list(_read_document(file_path=file_path).get("observations", {}))


def read_boris_observation(file_path: str | Path, observation_name: str) -> BorisObservation:
    """Read one named observation, pairing its state behaviors into occurrences.

    Parameters
    ----------
    file_path : str or pathlib.Path
        Path to the ``.boris`` JSON document.
    observation_name : str
        The observation to read, as :func:`get_observation_names` lists them.

    Returns
    -------
    BorisObservation
        The observation, its events paired into occurrences.

    Raises
    ------
    KeyError
        If the file holds no observation of that name, naming the ones it does.
    """
    document = _read_document(file_path=file_path)
    observations = document.get("observations", {})
    if observation_name not in observations:
        raise KeyError(
            f"No observation '{observation_name}' in '{file_path}'. This project holds "
            f"{sorted(observations)}, which get_observation_names lists."
        )

    observation = observations[observation_name]
    behaviors = _read_behaviors(document=document, format_version=_format_version(document=document))
    _warn_about_undeclared_codes(
        events=observation.get("events", []), behaviors=behaviors, observation_name=observation_name
    )
    media_files = _media_files(observation=observation)
    return BorisObservation(
        name=observation_name,
        observation_type=observation.get("type", ""),
        time_offset=float(observation.get("time offset", 0.0)),
        media_files=media_files,
        frame_rate=_frame_rate(observation=observation, media_files=media_files),
        occurrences=_pair_events(events=observation.get("events", []), behaviors=behaviors),
    )


def _warn_about_undeclared_codes(events: list, behaviors: dict[str, BorisBehavior], observation_name: str) -> None:
    """Warn where an event names a behavior the coding scheme does not declare.

    BORIS does not rewrite rows already scored when a behavior is renamed or removed from the ethogram, so
    a project can hold events whose code is nowhere in `behaviors_conf`. The scheme is the only place a
    behavior's point-or-state kind is recorded, so such a code has no kind and its rows cannot be paired.
    They are kept and written without durations, which is the loss this announces: a state behavior read
    this way loses every bout it ever had, and nothing in the written file would say so.
    """
    counts = {}
    for row in events:
        code = row[_CODE]
        if code not in behaviors:
            counts[code] = counts.get(code, 0) + 1
    for code, count in counts.items():
        warnings.warn(
            f"Observation '{observation_name}' has {count} events naming '{code}', which this project's "
            "ethogram does not declare. BORIS does not rewrite existing rows when a behavior is renamed or "
            "removed, so these are usually the old name of a behavior that is still in the scheme under a "
            "new one. They are read without durations, since only the ethogram says whether a behavior is "
            f"durative. If '{code}' was a state behavior, its bouts are not in this file. Declare it in the "
            "project in BORIS and re-save to recover them.",
            UserWarning,
            stacklevel=3,
        )


def _read_document(file_path: str | Path) -> dict:
    """Load the JSON document."""
    return json.loads(Path(file_path).read_text(encoding="utf-8"))


def _format_version(document: dict) -> float:
    """Return the declared project format version as a number, so versions can be compared."""
    return float(document.get("project_format_version", 0.0))


def _read_behaviors(document: dict, format_version: float) -> dict[str, BorisBehavior]:
    """Build the coding scheme, keyed by behavior code."""
    behaviors = {}
    for native_code, entry in document.get("behaviors_conf", {}).items():
        declared_type = entry.get("type", "")
        excluded = entry.get("excluded", "")
        behaviors[entry["code"]] = BorisBehavior(
            code=entry["code"],
            behavior_type="point" if declared_type == _POINT_EVENT else "state",
            description=entry.get("description", ""),
            # 1.6 has no category field at all, so an absent key is the version showing through rather
            # than a behavior nobody assigned.
            category=entry.get("category", ""),
            native_code=int(native_code),
            excluded=[code for code in excluded.split(",") if code],
            modifier_slots=_read_modifier_slots(declared=entry.get("modifiers", ""), format_version=format_version),
        )
    return behaviors


def _read_modifier_slots(declared: dict | str, format_version: float) -> list[BorisModifierSlot]:
    """Read a behavior's declared modifier slots.

    The key is a dict of slot objects from format 7.0 on and one flat comma-separated string of values
    before it, and it is the empty string in either version when the behavior declares no modifiers. The
    older form declares no slot name and no type, so it reads as a single selection from its values, which
    is what it was.
    """
    if not declared:
        return []
    if format_version >= _SLOT_DICT_FROM_VERSION and isinstance(declared, dict):
        return [
            BorisModifierSlot(
                name=slot.get("name", ""),
                slot_type=int(slot.get("type", 0)),
                values=list(slot.get("values", [])),
            )
            for slot in declared.values()
        ]
    return [BorisModifierSlot(name="", slot_type=0, values=[value for value in declared.split(",") if value])]


def _media_files(observation: dict) -> list[str]:
    """Return the media an observation was scored against, in player order.

    Read off `file`, not off `media_info`, which accumulates entries from other observations and so is not
    an inventory of the one it sits in. A single player's list holds clips played back to back.
    """
    files = observation.get("file") or {}
    if not isinstance(files, dict):
        return []
    return [medium for player in sorted(files) for medium in files[player]]


def _frame_rate(observation: dict, media_files: list[str]) -> float | None:
    """Return the frame rate of the observation's first medium, where it has one.

    A `LIVE` observation has no media and no frame rate anywhere, so this is `None` for it rather than a
    default. `media_info` is keyed by media name and lists media used by other observations too, which is
    why the lookup goes through this observation's own `file` entry.
    """
    frame_rates = (observation.get("media_info") or {}).get("fps") or {}
    for medium in media_files:
        if medium in frame_rates:
            return float(frame_rates[medium])
    return None


def _pair_events(events: list, behaviors: dict[str, BorisBehavior]) -> list[BorisOccurrence]:
    """Turn event rows into occurrences, pairing each state behavior's start row with its stop row.

    Nothing in a row says whether it opens or closes anything, so the pairing runs off the declared type:
    a point behavior is one row, and a state behavior's rows alternate start, stop, start, stop for a given
    subject and code. Pairing ignores the modifier string, since a bout can open with one modifier and
    close with another, and it ignores the comment for the same reason. Both rows' comments are kept,
    since a coder writes one thing when a bout starts and another when it ends.

    A bout that opens and never closes is legal and gets a `nan` duration. It happens whenever a coder
    misses a stop in a live session, which cannot be repaired afterwards, so dropping the event or
    refusing the file would both be wrong.
    """
    occurrences = []
    open_bouts = {}  # (subject, code) -> the index in `occurrences` of the bout waiting for its stop
    for row in events:
        subject = "" if row[_SUBJECT] == _NO_FOCAL_SUBJECT else row[_SUBJECT]
        code = row[_CODE]
        onset = float(row[_TIME])
        behavior = behaviors.get(code)

        # A code no behavior declares cannot be typed, and treating it as a point event is the reading that
        # keeps the row rather than guessing at an extent it may not have.
        if behavior is None or behavior.behavior_type == "point":
            occurrences.append(
                BorisOccurrence(
                    onset=onset,
                    subject=subject,
                    code=code,
                    modifiers=row[_MODIFIERS],
                    comment=row[_COMMENT],
                    duration=None,
                )
            )
            continue

        key = (subject, code)
        if key in open_bouts:
            opening = occurrences[open_bouts.pop(key)]
            opening.duration = onset - opening.onset
            # The closing row carries its own comment, and it is the one saying how the bout ended, so it
            # is kept beside the opening row's rather than dropped when the two rows become one.
            opening.stop_comment = row[_COMMENT]
            opening.stop_modifiers = row[_MODIFIERS]
            continue
        open_bouts[key] = len(occurrences)
        occurrences.append(
            BorisOccurrence(
                onset=onset,
                subject=subject,
                code=code,
                modifiers=row[_MODIFIERS],
                comment=row[_COMMENT],
                duration=math.nan,
            )
        )
    return occurrences
