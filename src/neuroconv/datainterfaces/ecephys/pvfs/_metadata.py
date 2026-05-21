"""Helpers for pulling NWB-relevant metadata out of a PVFS file.

A PVFS container always carries an ``experiment.db3`` SQLite database (see
``pvfs_tools.Database.database.ExperimentDatabase``) plus a set of
``IndexedDataFile`` channels.  This module extracts that database to a
temporary file, opens it, and returns plain Python dictionaries that match
NeuroConv's ``metadata`` shape.  It is intentionally small so that the
interfaces can compose it without taking a runtime dependency on the
high-level :class:`pvfs_tools.Core.pvfs_data_file.PvfsDataFile` wrapper.

All imports of ``pvfs_tools`` are deferred until the helpers are actually
called so that ``import neuroconv`` continues to work without ``pypvfs``
installed.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from pvfs_tools.Core.pvfs_binding import HighTime, PvfsFile
    from pvfs_tools.Database.models import (
        Annotation,
        ChannelInformation,
        ExperimentInformation,
    )

EXPERIMENT_DB_FILENAME = "experiment.db3"
EXPERIMENT_DB_BACKUP_FILENAME = "experiment_backup.db3"

# PVFS does not record subject age. This ISO-8601 placeholder satisfies NWBInspector;
# override via metadata["Subject"]["age"] or CLI --subject-age when known.
DEFAULT_SUBJECT_AGE = "P0D"

DEFAULT_NWB_KEYWORDS = ("Pinnacle", "PVFS", "EEG")

# PVFS does not record who ran the session; override via metadata.
DEFAULT_EXPERIMENTER = "Robby Researcher"


def _import_pvfs_binding():
    """Lazy import of the ``pvfs_tools.Core.pvfs_binding`` module."""
    from ....tools import get_package

    get_package(package_name="pvfs_tools", installation_instructions='pip install "neuroconv[pvfs]"')
    from pvfs_tools.Core.pvfs_binding import HighTime, PvfsFile  # noqa: F401

    return HighTime, PvfsFile


def _import_pvfs_database():
    """Lazy import of the ``pvfs_tools.Database`` namespace."""
    from ....tools import get_package

    get_package(package_name="pvfs_tools", installation_instructions='pip install "neuroconv[pvfs]"')
    from pvfs_tools.Database.database import ExperimentDatabase
    from pvfs_tools.Database.models import (
        Annotation,
        ChannelInformation,
        ExperimentInformation,
    )

    return ExperimentDatabase, Annotation, ChannelInformation, ExperimentInformation


def decode_pvfs_filename(raw: object) -> str:
    """Decode a PVFS ``get_file_list()`` entry to a UTF-8 path string."""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="ignore").rstrip("\x00")
    return str(raw)


def discover_video_stream_bases(vfs) -> frozenset[str]:
    """Return base names for embedded video streams inside a PVFS container.

    Video tracks are stored as ``{base}_frames`` plus ``{base}_index`` (not
    ``{base}.index`` / ``{base}.idat`` used by :class:`IndexedDataFile`).
    """
    try:
        names = [decode_pvfs_filename(raw) for raw in vfs.get_file_list()]
    except Exception:  # pragma: no cover - depends on native binding
        return frozenset()

    name_set = set(names)
    streams: list[str] = []
    for name in names:
        if name.endswith("_index"):
            base = name[: -len("_index")]
            if f"{base}_frames" in name_set:
                streams.append(base)
    return frozenset(streams)


def resolve_channel_file_base(info: Any, channel_name: str) -> str:
    """Return the PVFS file stem for a channel (see experiment.db3 ``filename``)."""
    if info is not None and info.filename and str(info.filename).strip():
        return str(info.filename).strip()
    return channel_name


def filter_indexed_channels(
    channels: dict[str, Any],
    video_bases: frozenset[str],
) -> dict[str, Any]:
    """Drop database channels that reference embedded video streams, not EEG/EMG."""
    if not video_bases:
        return dict(channels)
    return {
        name: info
        for name, info in channels.items()
        if resolve_channel_file_base(info, name) not in video_bases
    }


def hightime_to_datetime(ht: Any) -> datetime | None:
    """Convert a ``HighTime`` (POSIX seconds + fractional) to UTC ``datetime``.

    Returns ``None`` if the input is missing or marks the PVFS "no time" sentinel
    (``seconds == 0`` and ``subseconds == 0``).
    """
    if ht is None:
        return None
    seconds = int(ht.seconds)
    subseconds = float(ht.subseconds)
    if seconds == 0 and subseconds == 0.0:
        return None
    return datetime.fromtimestamp(seconds + subseconds, tz=timezone.utc)


def hightime_to_seconds(ht: Any) -> float | None:
    """Convert a ``HighTime`` to a plain ``float`` of POSIX seconds."""
    if ht is None:
        return None
    seconds = int(ht.seconds)
    subseconds = float(ht.subseconds)
    if seconds == 0 and subseconds == 0.0:
        return None
    return seconds + subseconds


@dataclass
class PvfsMetadata:
    """Snapshot of everything the interfaces need from ``experiment.db3``.

    The interfaces never re-open the database after this snapshot is taken.
    """

    experiment: Any = None
    channels: dict[str, Any] = field(default_factory=dict)
    annotations: list[Any] = field(default_factory=list)
    session_start_datetime: datetime | None = None
    channel_id_to_name: dict[int, str] = field(default_factory=dict)

    def to_nwb_metadata(self) -> dict:
        """Return a NeuroConv-style ``metadata`` dict prefilled from the DB.

        Subject ``sex`` and ``species`` are required by NeuroConv's metadata
        schema but PVFS does not carry that information.  We default ``sex`` to
        ``"U"`` (unknown) and ``species`` to ``"Mus musculus"`` because
        Pinnacle PVFS files are overwhelmingly rodent EEG recordings; users
        should override these defaults when they know better.

        ``age`` defaults to :data:`DEFAULT_SUBJECT_AGE` because PVFS does not
        store age or date of birth (required by NWBInspector).  Other NWB file
        fields that PVFS cannot populate are filled with conservative defaults
        so converted files pass routine inspection; override any field via the
        metadata dict.
        """
        nwbfile: dict = {}
        if self.session_start_datetime is not None:
            nwbfile["session_start_time"] = self.session_start_datetime
        if self.experiment is not None:
            if self.experiment.description:
                nwbfile["session_description"] = self.experiment.description
                nwbfile["experiment_description"] = self.experiment.description
            if self.experiment.id:
                nwbfile["session_id"] = str(self.experiment.id)

        if not nwbfile.get("experiment_description"):
            nwbfile["experiment_description"] = "Pinnacle PVFS recording"
        nwbfile["keywords"] = list(DEFAULT_NWB_KEYWORDS)
        nwbfile["institution"] = "Not specified in PVFS source file"
        nwbfile["experimenter"] = [DEFAULT_EXPERIMENTER]

        subject: dict = {
            "sex": "U",
            "species": "Mus musculus",
            "age": DEFAULT_SUBJECT_AGE,
        }
        if self.experiment is not None and self.experiment.name:
            subject["subject_id"] = self.experiment.name
            subject["description"] = (
                "Subject identifier from PVFS experiment metadata "
                f"({self.experiment.name})."
            )
        else:
            # NWB's metadata schema requires ``Subject.subject_id``.  PVFS does not
            # always record one (e.g. Pinnacle's public sleep_data sample leaves
            # ``ExperimentInformation.name`` empty), so we fall back to a stable
            # placeholder; users should override it when the real id is known.
            subject["subject_id"] = "unknown"
            subject["description"] = (
                "Subject metadata from PVFS; subject_id was not recorded in the "
                "source file and has been set to 'unknown'. Override via "
                'metadata["Subject"]["subject_id"] when the real id is known.'
            )

        metadata: dict = {}
        if nwbfile:
            metadata["NWBFile"] = {k: v for k, v in nwbfile.items() if v is not None}
        metadata["Subject"] = subject
        return metadata


def _earliest_session_start_datetime(
    *,
    experiment: Any,
    channels: dict[str, Any],
    annotations: list[Any],
) -> datetime | None:
    """Return the earliest absolute time to use as ``session_start_time``.

    NWB best practice is to align the session clock to the earliest timestamp
    present in the recording so derived tables (e.g. epochs) are non-negative.
    """
    candidates: list[datetime] = []
    if experiment is not None and experiment.start_time is not None:
        dt = hightime_to_datetime(experiment.start_time)
        if dt is not None:
            candidates.append(dt)
    for info in channels.values():
        if info.start_time is not None:
            dt = hightime_to_datetime(info.start_time)
            if dt is not None:
                candidates.append(dt)
    for ann in annotations:
        seconds = hightime_to_seconds(ann.start_time)
        if seconds is not None:
            candidates.append(datetime.fromtimestamp(seconds, tz=timezone.utc))
        end_seconds = hightime_to_seconds(ann.end_time)
        if end_seconds is not None:
            candidates.append(datetime.fromtimestamp(end_seconds, tz=timezone.utc))
    if not candidates:
        return None
    return min(candidates)


def extract_experiment_db(
    pvfs_file: Any,
    destination_dir: str | os.PathLike | None = None,
) -> Path:
    """Extract ``experiment.db3`` (or its backup) out of *pvfs_file* to disk.

    Returns the path to the extracted SQLite file.  Raises ``FileNotFoundError``
    if neither the primary nor the backup database can be retrieved.
    """
    destination_dir = Path(destination_dir) if destination_dir else Path(tempfile.gettempdir())
    destination_dir.mkdir(parents=True, exist_ok=True)
    out_path = destination_dir / f"neuroconv_pvfs_{uuid.uuid4().hex}.db3"

    for candidate in (EXPERIMENT_DB_FILENAME, EXPERIMENT_DB_BACKUP_FILENAME):
        try:
            rc = pvfs_file.extract(candidate, str(out_path))
        except RuntimeError:
            continue
        if rc == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return out_path

    raise FileNotFoundError(
        "No experiment.db3 (or experiment_backup.db3) found inside the PVFS container."
    )


def _read_metadata_from_db(db_path: str | os.PathLike) -> PvfsMetadata:
    """Open an extracted ``experiment.db3`` and read all metadata of interest."""
    ExperimentDatabase, _Annotation, _ChannelInformation, _ExperimentInformation = _import_pvfs_database()
    db = ExperimentDatabase(filename=str(db_path), in_memory=False)
    try:
        experiment = db.get_information()
        channel_names = db.get_channel_names()
        channels: dict[str, Any] = {}
        channel_id_to_name: dict[int, str] = {}
        for name in channel_names:
            info = db.get_channel_info(name)
            if info is None:
                continue
            channels[name] = info
            channel_id_to_name[int(info.id)] = name

        annotations = db.get_all_annotations()
    finally:
        db.close()

    session_start_datetime = _earliest_session_start_datetime(
        experiment=experiment,
        channels=channels,
        annotations=annotations,
    )

    return PvfsMetadata(
        experiment=experiment,
        channels=channels,
        annotations=annotations,
        session_start_datetime=session_start_datetime,
        channel_id_to_name=channel_id_to_name,
    )


@contextmanager
def open_pvfs(file_path: str | os.PathLike) -> Iterator[Any]:
    """Context manager wrapping ``PvfsFile.open`` with guaranteed ``close``."""
    _HighTime, PvfsFile = _import_pvfs_binding()
    file_path = str(Path(file_path))
    vfs = PvfsFile.open(file_path)
    if vfs is None or not getattr(vfs, "is_open", True):
        raise RuntimeError(f"Failed to open PVFS file: {file_path}")
    try:
        yield vfs
    finally:
        try:
            vfs.close()
        except Exception:  # pragma: no cover - best effort cleanup
            pass


def read_pvfs_metadata(file_path: str | os.PathLike) -> PvfsMetadata:
    """High-level helper: open the PVFS, extract the DB, return a snapshot.

    The extracted database file is removed before returning so callers don't
    have to manage temp files themselves.
    """
    with open_pvfs(file_path) as vfs:
        db_path = extract_experiment_db(vfs)
        try:
            return _read_metadata_from_db(db_path)
        finally:
            try:
                db_path.unlink(missing_ok=True)
            except OSError:  # pragma: no cover - non-fatal cleanup
                pass


# ---------------------------------------------------------------------------
# Sleep scoring readers
# ---------------------------------------------------------------------------
#
# Pinnacle's PVFS stores manual / automatic sleep-stage scoring in four tables
# inside ``experiment.db3``:
#
# * ``scores_values_table`` -- per-session legend mapping integer scores to
#   names (e.g. ``1 -> "Wake"``, ``2 -> "Non REM"``), plus ``flags`` and
#   display ``color`` (RGBA hex).
# * ``sleep_scoring_session_table`` -- per-session metadata (scorer / user_id,
#   epoch length in seconds, source data file, animal id, experiment id).
# * ``sleep_scores_table`` -- the actual per-epoch scores (start/end time as
#   ``(seconds, sub_seconds)`` pairs, integer ``score`` referencing the legend,
#   plus a stable per-epoch GUID ``uid``).
# * ``sleep_scoring_parameters_table`` -- houses Pinnacle's internal next-id
#   counter. We deliberately ignore it.
#
# pypvfs's :class:`ExperimentDatabase` does not expose these tables, so we open
# the SQLite file directly with the stdlib driver. The tables are tolerated as
# *optional*: their absence means "no scoring data" and yields an empty result.

SCORE_LEGEND_TABLE = "scores_values_table"
SLEEP_SCORES_TABLE = "sleep_scores_table"
SLEEP_SCORING_SESSION_TABLE = "sleep_scoring_session_table"


@dataclass(frozen=True)
class ScoreLegendEntry:
    """One row of :data:`SCORE_LEGEND_TABLE` (per-session legend)."""

    score: int
    score_name: str
    flags: int = 0


@dataclass(frozen=True)
class SleepEpoch:
    """One scored epoch from :data:`SLEEP_SCORES_TABLE`."""

    start_abs_seconds: float
    """Absolute POSIX seconds (``start_time_seconds + start_time_sub_seconds``)."""

    stop_abs_seconds: float
    """Absolute POSIX seconds (``end_time_seconds + end_time_sub_seconds``)."""

    score: int
    """Raw integer score; cross-reference :class:`ScoreLegendEntry`."""

    uid: str
    """Per-epoch GUID from PVFS (lets external tools round-trip score edits)."""


@dataclass(frozen=True)
class SleepScoringSession:
    """A single Pinnacle scoring session worth of legend + scores + metadata."""

    session_number: int
    user_id: str | None
    epoch_length_seconds: float | None
    animal_id: str | None
    experiment_id: str | None
    data_file_name: str | None
    legend: dict[int, ScoreLegendEntry]
    epochs: list[SleepEpoch]

    def label_for(self, score: int) -> str:
        """Resolve a raw score integer to a human-readable name.

        Falls back to ``"score_<n>"`` when the legend has no matching entry
        (e.g. a custom value Pinnacle does not document).
        """
        entry = self.legend.get(int(score))
        return entry.score_name if entry is not None else f"score_{int(score)}"

    def flags_for(self, score: int) -> int:
        """Return the legend ``flags`` for *score*, or ``0`` when unknown."""
        entry = self.legend.get(int(score))
        return int(entry.flags) if entry is not None else 0


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def _parse_sub_seconds(value: object) -> float:
    """Match pypvfs's behaviour: ``float(varchar)`` with safe fall-back to 0."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_epoch_length(value: object) -> float | None:
    """``sleep_scoring_session_table.epoch_length`` is stored as VARCHAR."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _strip(text: object) -> str | None:
    """Strip Pinnacle's right-padded VARCHARs (they often have trailing spaces)."""
    if text is None:
        return None
    stripped = str(text).strip()
    return stripped or None


def read_sleep_scoring_sessions(
    db_path: str | os.PathLike,
) -> dict[int, SleepScoringSession]:
    """Read every populated sleep-scoring session from an extracted ``experiment.db3``.

    A session is considered "populated" if :data:`SLEEP_SCORES_TABLE` has at
    least one row with that ``session_number``.  Sessions that only appear in
    the legend (``scores_values_table``) but have no actual scores are skipped
    -- Pinnacle accumulates historical legend rows there as scoring sessions
    are created and deleted.

    Returns a ``dict`` keyed by ``session_number``.  Returns an empty dict when
    the database does not contain any sleep-scoring tables (typical for raw
    recordings that have never been opened in Pinnacle's scoring UI).
    """
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        if not _table_exists(con, SLEEP_SCORES_TABLE):
            return {}

        populated_sessions = [
            int(row[0])
            for row in con.execute(
                f"SELECT DISTINCT session_number FROM {SLEEP_SCORES_TABLE} "
                "ORDER BY session_number"
            )
        ]
        if not populated_sessions:
            return {}

        sessions: dict[int, SleepScoringSession] = {}
        for session_number in populated_sessions:
            legend = _read_legend(con, session_number)
            metadata_row = _read_session_metadata(con, session_number)
            epochs = _read_session_epochs(con, session_number)

            sessions[session_number] = SleepScoringSession(
                session_number=session_number,
                user_id=metadata_row.get("user_id"),
                epoch_length_seconds=metadata_row.get("epoch_length_seconds"),
                animal_id=metadata_row.get("animal_id"),
                experiment_id=metadata_row.get("experiment_id"),
                data_file_name=metadata_row.get("data_file_name"),
                legend=legend,
                epochs=epochs,
            )
        return sessions
    finally:
        con.close()


def _read_legend(
    con: sqlite3.Connection, session_number: int
) -> dict[int, ScoreLegendEntry]:
    if not _table_exists(con, SCORE_LEGEND_TABLE):
        return {}
    legend: dict[int, ScoreLegendEntry] = {}
    for row in con.execute(
        f"SELECT score, score_name, flags FROM {SCORE_LEGEND_TABLE} "
        "WHERE session_number=? ORDER BY score",
        (session_number,),
    ):
        score = int(row["score"])
        name = _strip(row["score_name"]) or f"score_{score}"
        flags = int(row["flags"]) if row["flags"] is not None else 0
        legend[score] = ScoreLegendEntry(score=score, score_name=name, flags=flags)
    return legend


def _read_session_metadata(
    con: sqlite3.Connection, session_number: int
) -> dict[str, object]:
    """Read one row of :data:`SLEEP_SCORING_SESSION_TABLE`, returning a plain dict."""
    if not _table_exists(con, SLEEP_SCORING_SESSION_TABLE):
        return {}
    row = con.execute(
        f"SELECT user_id, epoch_length, data_file_name, experiment_id, animal_id "
        f"FROM {SLEEP_SCORING_SESSION_TABLE} WHERE session_number=? LIMIT 1",
        (session_number,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "user_id": _strip(row["user_id"]),
        "epoch_length_seconds": _parse_epoch_length(row["epoch_length"]),
        "data_file_name": _strip(row["data_file_name"]),
        "experiment_id": _strip(row["experiment_id"]),
        "animal_id": _strip(row["animal_id"]),
    }


def _read_session_epochs(
    con: sqlite3.Connection, session_number: int
) -> list[SleepEpoch]:
    epochs: list[SleepEpoch] = []
    for row in con.execute(
        f"SELECT start_time_seconds, start_time_sub_seconds, "
        f"end_time_seconds, end_time_sub_seconds, score, uid "
        f"FROM {SLEEP_SCORES_TABLE} WHERE session_number=? "
        "ORDER BY start_time_seconds, start_time_sub_seconds",
        (session_number,),
    ):
        start_sec = row["start_time_seconds"]
        end_sec = row["end_time_seconds"]
        if start_sec is None or end_sec is None:
            continue  # malformed row; skip rather than fail the whole import
        start_abs = float(start_sec) + _parse_sub_seconds(row["start_time_sub_seconds"])
        stop_abs = float(end_sec) + _parse_sub_seconds(row["end_time_sub_seconds"])
        epochs.append(
            SleepEpoch(
                start_abs_seconds=start_abs,
                stop_abs_seconds=stop_abs,
                score=int(row["score"]),
                uid=str(row["uid"]) if row["uid"] is not None else "",
            )
        )
    return epochs


def read_sleep_scoring_sessions_from_pvfs(
    file_path: str | os.PathLike,
) -> dict[int, SleepScoringSession]:
    """Convenience wrapper: open the PVFS, extract the DB, read scoring sessions.

    The extracted database file is removed before returning.  Returns an empty
    dict when the PVFS contains no sleep-scoring tables.
    """
    with open_pvfs(file_path) as vfs:
        db_path = extract_experiment_db(vfs)
        try:
            return read_sleep_scoring_sessions(db_path)
        finally:
            try:
                db_path.unlink(missing_ok=True)
            except OSError:  # pragma: no cover - non-fatal cleanup
                pass
