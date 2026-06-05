"""NeuroConv interface that maps PVFS annotations to an NWB ``epochs`` table.

Annotations stored in ``experiment.db3`` (see
:class:`pvfs_tools.Database.models.Annotation`) carry a start time and,
optionally, an end time plus a free-form comment and a type label.  We write
them as rows in :pyattr:`pynwb.NWBFile.epochs`, augmented with two custom
columns:

* ``label`` -- the annotation comment + type (or ``""`` if both are empty).
* ``channel`` -- the human-readable channel name (or ``""`` when the annotation
  is session-wide).

When an annotation lacks an end time we store a point event with
``stop_time = start_time + POINT_EVENT_MIN_DURATION_S`` so epoch intervals
satisfy NWB best practices (``stop_time`` must be strictly greater than
``start_time``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import FilePath
from pynwb import NWBFile

from ....basedatainterface import BaseDataInterface
from ....utils import DeepDict

if TYPE_CHECKING:  # pragma: no cover
    from ._metadata import PvfsMetadata

# NWBInspector requires stop_time > start_time; use a minimal duration for point events.
POINT_EVENT_MIN_DURATION_S = 1e-6


class PvfsAnnotationsInterface(BaseDataInterface):
    """Write PVFS per-channel annotations as NWB epochs."""

    display_name = "PVFS Annotations"
    keywords = ("Pinnacle", "PVFS", "annotations", "epochs")
    associated_suffixes = (".pvfs",)
    info = "Adds Pinnacle PVFS annotations as NWB epochs."

    @classmethod
    def get_source_schema(cls) -> dict:
        """Return the JSON schema for the source arguments of this interface."""
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the Pinnacle .pvfs container."
        return source_schema

    def __init__(self, file_path: FilePath, verbose: bool = False) -> None:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"PVFS file not found: {file_path}")
        super().__init__(file_path=str(file_path), verbose=verbose)
        self.file_path = str(file_path)
        self._cached_metadata: "PvfsMetadata | None" = None

    def _get_pvfs_metadata(self) -> "PvfsMetadata":
        from ._metadata import read_pvfs_metadata

        if self._cached_metadata is None:
            self._cached_metadata = read_pvfs_metadata(self.file_path)
        return self._cached_metadata

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
        """Append annotations from the PVFS file to ``nwbfile.epochs``."""
        from ._metadata import hightime_to_seconds

        del extra
        pvfs_meta = self._get_pvfs_metadata()
        annotations = pvfs_meta.annotations
        if not annotations:
            return

        # Resolve the session start time so we can convert HighTime to seconds-since-start.
        if session_start_time is None:
            if metadata and metadata.get("NWBFile", {}).get("session_start_time"):
                session_start_time = metadata["NWBFile"]["session_start_time"]
            elif nwbfile.session_start_time is not None:
                session_start_time = nwbfile.session_start_time
            else:
                session_start_time = pvfs_meta.session_start_datetime

        if session_start_time is None:
            return  # cannot compute relative times without a reference

        if session_start_time.tzinfo is None:
            session_start_time = session_start_time.replace(tzinfo=timezone.utc)
        session_start_seconds = session_start_time.timestamp()

        # Ensure the custom columns exist before we add rows.
        existing_column_names = {col.name for col in nwbfile.epochs.columns} if nwbfile.epochs is not None else set()
        if "label" not in existing_column_names:
            nwbfile.add_epoch_column(name="label", description="PVFS annotation text")
        if "channel" not in existing_column_names:
            nwbfile.add_epoch_column(
                name="channel",
                description="Channel name the annotation applies to ('' if session-wide).",
            )

        for ann in annotations:
            start_abs = hightime_to_seconds(ann.start_time)
            if start_abs is None:
                continue
            end_abs = hightime_to_seconds(ann.end_time)
            is_point_event = end_abs is None or end_abs < start_abs
            if is_point_event:
                end_abs = start_abs + POINT_EVENT_MIN_DURATION_S

            start_rel = start_abs - session_start_seconds
            stop_rel = end_abs - session_start_seconds
            if stop_rel <= start_rel:
                stop_rel = start_rel + POINT_EVENT_MIN_DURATION_S

            text_parts = []
            if ann.comment:
                text_parts.append(ann.comment)
            if ann.type:
                text_parts.append(f"[{ann.type}]")
            label = " ".join(text_parts).strip()

            channel_name = pvfs_meta.channel_id_to_name.get(int(ann.channel_id), "")

            nwbfile.add_epoch(
                start_time=float(start_rel),
                stop_time=float(stop_rel),
                label=label,
                channel=channel_name,
            )
