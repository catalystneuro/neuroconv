"""NeuroConv interface that maps Pinnacle PVFS sleep scoring to NWB.

Pinnacle's PVFS stores manual / automatic sleep-stage scoring in four tables
inside ``experiment.db3`` (see :mod:`._metadata` for full schema notes).
Each populated scoring session is a dense, regular sequence of fixed-length
epochs (10 s by default) with an integer ``score`` indexed against a
per-session legend (``1 -> "Wake"``, ``2 -> "Non REM"``, ...).

Dense, regular state segmentation maps cleanly onto NWB's
:class:`pynwb.epoch.TimeIntervals` -- the same primitive that backs
:pyattr:`pynwb.NWBFile.epochs`, but registered as a *separate* table under
:pyattr:`pynwb.NWBFile.intervals`.  That keeps the sleep stages distinct from
the free-text PVFS annotations written by :class:`PvfsAnnotationsInterface`,
which target ``nwbfile.epochs`` directly.

We export **one TimeIntervals per populated scoring session**, named
``sleep_stages_session_<n>``, with columns:

* ``start_time``, ``stop_time`` -- seconds relative to ``session_start_time``;
* ``stage_label`` -- resolved name from the legend (``"Wake"``, ``"Non REM"``,
  ``"REM"``, ``"Artifact"``, ``"Unscored"``, custom labels, ...);
* ``stage_value`` -- the raw integer PVFS score code (preserved for
  round-tripping back into Pinnacle tooling);
* ``flags`` -- the legend's ``flags`` field (``0`` for wake/artifact/unscored,
  ``1`` for sleep stages, ``2`` for the ``X`` variants);
* ``epoch_uid`` -- the PVFS per-epoch GUID (lets external scoring tools update
  individual rows by id even after the NWB round-trip).

The table description carries the session-level context (scorer ``user_id``,
``epoch_length`` in seconds, source data file, animal id, experiment id).

The sleep-scoring tables are read with the stdlib ``sqlite3`` driver, so no
pypvfs / pvfs_tools install is required for the SQL portion.  Opening the
PVFS container itself (to extract ``experiment.db3``) still goes through
pypvfs and is lazily imported.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import FilePath
from pynwb import NWBFile

from ....basedatainterface import BaseDataInterface
from ....utils import DeepDict

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from ._metadata import PvfsMetadata, SleepScoringSession


# NWB requires stop_time > start_time. PVFS epochs always span >=1 s in
# practice, but we guard against zero-duration rows defensively.
MIN_EPOCH_DURATION_S = 1e-6


class PvfsSleepScoringInterface(BaseDataInterface):
    """Write Pinnacle PVFS sleep-stage scoring to ``nwbfile.intervals``.

    For each populated scoring session in the PVFS file, a single
    :class:`~pynwb.epoch.TimeIntervals` is added to the NWB file under
    ``nwbfile.intervals["sleep_stages_session_<n>"]``.
    """

    display_name = "PVFS Sleep Scoring"
    keywords = ("Pinnacle", "PVFS", "sleep", "scoring", "epochs", "stages")
    associated_suffixes = (".pvfs",)
    info = "Adds Pinnacle PVFS sleep-stage scoring as NWB TimeIntervals."

    @classmethod
    def get_source_schema(cls) -> dict:
        """Return the JSON schema for the source arguments of this interface."""
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = (
            "Path to the Pinnacle .pvfs container."
        )
        return source_schema

    def __init__(self, file_path: FilePath, verbose: bool = False) -> None:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"PVFS file not found: {file_path}")
        super().__init__(file_path=str(file_path), verbose=verbose)
        self.file_path = str(file_path)
        self._cached_metadata: "PvfsMetadata | None" = None
        self._cached_sessions: "dict[int, SleepScoringSession] | None" = None

    def _get_pvfs_metadata(self) -> "PvfsMetadata":
        from ._metadata import read_pvfs_metadata

        if self._cached_metadata is None:
            self._cached_metadata = read_pvfs_metadata(self.file_path)
        return self._cached_metadata

    def _get_sessions(self) -> "dict[int, SleepScoringSession]":
        from ._metadata import read_sleep_scoring_sessions_from_pvfs

        if self._cached_sessions is None:
            self._cached_sessions = read_sleep_scoring_sessions_from_pvfs(
                self.file_path
            )
        return self._cached_sessions

    def has_scoring(self) -> bool:
        """Return True iff the source PVFS contains at least one scored epoch.

        Cheap enough to call from :class:`PvfsConverter` to decide whether to
        attach the interface at all.
        """
        sessions = self._get_sessions()
        return any(session.epochs for session in sessions.values())

    def get_metadata(self) -> DeepDict:
        """Build the metadata dictionary, prefilled from ``experiment.db3``."""
        metadata = super().get_metadata()
        pvfs_meta = self._get_pvfs_metadata()
        nwb_meta = pvfs_meta.to_nwb_metadata()
        if "NWBFile" in nwb_meta:
            metadata["NWBFile"].update(nwb_meta["NWBFile"])
        if "Subject" in nwb_meta:
            metadata["Subject"].update(nwb_meta["Subject"])
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        session_start_time: datetime | None = None,
        **extra: Any,
    ) -> None:
        """Append one ``TimeIntervals`` per populated scoring session.

        The table(s) live in ``nwbfile.intervals`` and never modify
        ``nwbfile.epochs`` -- that slot belongs to
        :class:`PvfsAnnotationsInterface`.
        """
        del extra  # unused; declared so NWBConverter can pass extras safely

        sessions = self._get_sessions()
        if not sessions:
            return

        if session_start_time is None:
            session_start_time = self._resolve_session_start_time(nwbfile, metadata)
        if session_start_time is None:
            return  # cannot align relative times without a reference

        if session_start_time.tzinfo is None:
            session_start_time = session_start_time.replace(tzinfo=timezone.utc)
        session_start_seconds = session_start_time.timestamp()

        for session_number in sorted(sessions.keys()):
            session = sessions[session_number]
            if not session.epochs:
                continue
            time_intervals = self._build_time_intervals(
                session, session_start_seconds=session_start_seconds
            )
            nwbfile.add_time_intervals(time_intervals)

    def _resolve_session_start_time(
        self, nwbfile: NWBFile, metadata: dict | None
    ) -> datetime | None:
        if metadata and metadata.get("NWBFile", {}).get("session_start_time"):
            return metadata["NWBFile"]["session_start_time"]
        if nwbfile.session_start_time is not None:
            return nwbfile.session_start_time
        return self._get_pvfs_metadata().session_start_datetime

    def _build_time_intervals(
        self,
        session: "SleepScoringSession",
        *,
        session_start_seconds: float,
    ):
        from pynwb.epoch import TimeIntervals

        table_name = f"sleep_stages_session_{session.session_number}"
        description = self._build_description(session)

        time_intervals = TimeIntervals(name=table_name, description=description)
        time_intervals.add_column(
            name="stage_label",
            description=(
                "Resolved sleep-stage name from the PVFS scores_values_table "
                "legend (e.g. 'Wake', 'Non REM', 'REM', 'Artifact', 'Unscored')."
            ),
        )
        time_intervals.add_column(
            name="stage_value",
            description=(
                "Raw integer score code from PVFS sleep_scores_table.score "
                "(preserved verbatim for round-tripping into Pinnacle tooling)."
            ),
        )
        time_intervals.add_column(
            name="flags",
            description=(
                "Per-stage flags from PVFS scores_values_table.flags "
                "(0 = wake/artifact/unscored, 1 = sleep stage, 2 = 'X' variant)."
            ),
        )
        time_intervals.add_column(
            name="epoch_uid",
            description=(
                "Per-epoch GUID from PVFS sleep_scores_table.uid; lets external "
                "scoring tools round-trip individual score edits back into PVFS."
            ),
        )

        for epoch in session.epochs:
            start_rel = epoch.start_abs_seconds - session_start_seconds
            stop_rel = epoch.stop_abs_seconds - session_start_seconds
            if stop_rel <= start_rel:
                stop_rel = start_rel + MIN_EPOCH_DURATION_S

            time_intervals.add_row(
                start_time=float(start_rel),
                stop_time=float(stop_rel),
                stage_label=session.label_for(epoch.score),
                stage_value=int(epoch.score),
                flags=int(session.flags_for(epoch.score)),
                epoch_uid=str(epoch.uid),
            )

        return time_intervals

    @staticmethod
    def _build_description(session: "SleepScoringSession") -> str:
        parts = [
            "Sleep-stage scoring exported from Pinnacle PVFS "
            f"(session_number={session.session_number})."
        ]
        if session.user_id:
            parts.append(f"Scorer: {session.user_id}.")
        if session.epoch_length_seconds:
            parts.append(f"Epoch length: {session.epoch_length_seconds:g} s.")
        if session.animal_id:
            parts.append(f"Animal id: {session.animal_id}.")
        if session.experiment_id:
            parts.append(f"Experiment id: {session.experiment_id}.")
        if session.data_file_name:
            parts.append(f"Source: {session.data_file_name}.")
        parts.append(f"Number of scored epochs: {len(session.epochs)}.")
        return " ".join(parts)
