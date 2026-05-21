"""NeuroConv interface that maps embedded PVFS video tracks to ``ImageSeries``.

A PVFS file can hold one or more VP8/VP9-encoded video tracks (see
:class:`pvfs_tools.Core.video_data_file.VideoDataFile`).  Each stream is stored
as a pair of internal files ``{stream}_frames`` and ``{stream}_index`` inside
the PVFS container.

The default conversion path repackages each track into an external WebM file
(produced by :class:`pvfs_tools.Core.webm_helpers.WebMWriter`) and attaches a
single ``ImageSeries`` whose ``external_file`` points at it.  That mirrors how
NWB recommends storing large video assets and keeps the resulting NWB file
small.  Use ``embed_frames=True`` to inline a uint8 frames array instead --
useful only for short clips.

Video processing depends on PyAV; the import is deferred until conversion time
so users that never touch video do not need the ``[pvfs_video]`` extra.
"""

from __future__ import annotations

import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import FilePath
from pynwb import NWBFile
from pynwb.image import ImageSeries

from ....basedatainterface import BaseDataInterface
from ....utils import DeepDict

if TYPE_CHECKING:  # pragma: no cover
    from ._metadata import PvfsMetadata


class PvfsVideoInterface(BaseDataInterface):
    """Export embedded PVFS video tracks and attach them as ``ImageSeries``."""

    display_name = "PVFS Video"
    keywords = ("Pinnacle", "PVFS", "video", "webm", "vp8")
    associated_suffixes = (".pvfs",)
    info = "Adds Pinnacle PVFS video tracks as NWB ImageSeries."

    @classmethod
    def get_source_schema(cls) -> dict:
        """Return the JSON schema for the source arguments of this interface."""
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the Pinnacle .pvfs container."
        return source_schema

    def __init__(
        self,
        file_path: FilePath,
        video_output_dir: str | Path | None = None,
        embed_frames: bool = False,
        verbose: bool = False,
    ) -> None:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"PVFS file not found: {file_path}")
        super().__init__(
            file_path=str(file_path),
            video_output_dir=(str(video_output_dir) if video_output_dir else None),
            embed_frames=embed_frames,
            verbose=verbose,
        )
        self.file_path = str(file_path)
        self.video_output_dir = Path(video_output_dir) if video_output_dir is not None else None
        self.embed_frames = bool(embed_frames)
        self._cached_metadata: "PvfsMetadata | None" = None

    def _get_pvfs_metadata(self) -> "PvfsMetadata":
        from ._metadata import read_pvfs_metadata

        if self._cached_metadata is None:
            self._cached_metadata = read_pvfs_metadata(self.file_path)
        return self._cached_metadata

    def has_video(self) -> bool:
        """Return ``True`` if the PVFS file contains at least one video stream."""
        from ._metadata import discover_video_stream_bases, open_pvfs

        with open_pvfs(self.file_path) as vfs:
            return bool(discover_video_stream_bases(vfs))

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
        nwbfile_path: str | Path | None = None,
        **extra: Any,
    ) -> None:
        """Append every PVFS video track as an ``ImageSeries`` in ``nwbfile``."""
        from ._metadata import discover_video_stream_bases, open_pvfs

        del extra
        pvfs_meta = self._get_pvfs_metadata()

        if session_start_time is None:
            if metadata and metadata.get("NWBFile", {}).get("session_start_time"):
                session_start_time = metadata["NWBFile"]["session_start_time"]
            elif nwbfile.session_start_time is not None:
                session_start_time = nwbfile.session_start_time
            else:
                session_start_time = pvfs_meta.session_start_datetime

        if session_start_time is None:
            warnings.warn(
                "PvfsVideoInterface could not determine session_start_time; " "skipping video export.",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        if session_start_time.tzinfo is None:
            session_start_time = session_start_time.replace(tzinfo=timezone.utc)
        session_start_seconds = session_start_time.timestamp()

        with open_pvfs(self.file_path) as vfs:
            streams = sorted(discover_video_stream_bases(vfs))
            if not streams:
                return

            output_dir = self._resolve_output_dir(nwbfile_path)
            output_dir.mkdir(parents=True, exist_ok=True)

            for stream_name in streams:
                self._add_one_stream(
                    nwbfile=nwbfile,
                    vfs=vfs,
                    stream_name=stream_name,
                    output_dir=output_dir,
                    session_start_seconds=session_start_seconds,
                )

    def _resolve_output_dir(self, nwbfile_path: str | Path | None) -> Path:
        if self.video_output_dir is not None:
            return self.video_output_dir
        if nwbfile_path is not None:
            return Path(nwbfile_path).resolve().parent
        return Path(self.file_path).resolve().parent

    def _add_one_stream(
        self,
        nwbfile: NWBFile,
        vfs,
        stream_name: str,
        output_dir: Path,
        session_start_seconds: float,
    ) -> None:
        from pvfs_tools.Core.video_data_file import VideoDataFile

        from ._metadata import hightime_to_seconds

        video = VideoDataFile(vfs, stream_name)
        try:
            frame_rate = float(video.get_frame_rate() or 0.0)
            frame_count = int(video.get_frame_count() or 0)
            width, height = video.get_frame_size()
            start_ht = video.get_start_time()
            start_abs = hightime_to_seconds(start_ht)
            starting_time = float(start_abs - session_start_seconds) if start_abs is not None else 0.0

            if frame_count <= 0 or frame_rate <= 0:
                warnings.warn(
                    f"PVFS video stream '{stream_name}' has no usable frames; skipping.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                return

            if self.embed_frames:
                image_series = self._build_inline_image_series(
                    video=video,
                    name=f"ImageSeriesPVFS_{stream_name}",
                    stream_name=stream_name,
                    starting_time=starting_time,
                    frame_rate=frame_rate,
                    frame_count=frame_count,
                )
            else:
                webm_path = self._export_webm(
                    video=video,
                    stream_name=stream_name,
                    output_dir=output_dir,
                    frame_rate=frame_rate,
                    width=width,
                    height=height,
                    frame_count=frame_count,
                )
                image_series = ImageSeries(
                    name=f"ImageSeriesPVFS_{stream_name}",
                    description=(
                        f"PVFS embedded video stream '{stream_name}' " f"({width}x{height}, {frame_rate:.3f} fps)."
                    ),
                    unit="n.a.",
                    format="external",
                    external_file=[str(webm_path)],
                    starting_frame=[0],
                    starting_time=starting_time,
                    rate=frame_rate,
                )
            nwbfile.add_acquisition(image_series)
        finally:
            video.close()

    def _export_webm(
        self,
        video,
        stream_name: str,
        output_dir: Path,
        frame_rate: float,
        width: int,
        height: int,
        frame_count: int,
    ) -> Path:
        try:
            from pvfs_tools.Core.webm_helpers import WebMWriter
        except ImportError as exc:  # pragma: no cover - exercised when av is missing
            raise ImportError(
                "PvfsVideoInterface requires PyAV. Install with " '`pip install "neuroconv[pvfs_video]"`.'
            ) from exc

        pvfs_stem = Path(self.file_path).stem
        out_path = output_dir / f"{pvfs_stem}_{stream_name}.webm"

        with WebMWriter(str(out_path), frame_rate=frame_rate, width=width, height=height) as writer:
            for frame_index in range(frame_count):
                _, frame_location = video._read_frame_header(frame_index)
                if frame_location < 0:
                    continue
                frame_bytes = video._read_frame_data(frame_location)
                if not frame_bytes:
                    continue
                is_keyframe = (frame_bytes[0] & 0x01) == 0 if frame_bytes else False
                writer.write_frame(
                    frame_bytes=frame_bytes,
                    is_keyframe=is_keyframe,
                    frame_index=frame_index,
                    frame_rate=frame_rate,
                )
        return out_path

    def _build_inline_image_series(
        self,
        video,
        name: str,
        stream_name: str,
        starting_time: float,
        frame_rate: float,
        frame_count: int,
    ) -> ImageSeries:
        try:
            import av  # noqa: F401
            import numpy as np
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "Inline video embedding requires PyAV + numpy. Install with " '`pip install "neuroconv[pvfs_video]"`.'
            ) from exc

        decoded = []
        codec = av.CodecContext.create("vp8", "r")
        for frame_index in range(frame_count):
            _, frame_location = video._read_frame_header(frame_index)
            if frame_location < 0:
                continue
            frame_bytes = video._read_frame_data(frame_location)
            if not frame_bytes:
                continue
            packet = av.packet.Packet(frame_bytes)
            for av_frame in codec.decode(packet):
                decoded.append(av_frame.to_ndarray(format="rgb24"))

        if not decoded:
            warnings.warn(
                f"PVFS video stream '{stream_name}' produced 0 decoded frames; " "skipping inline embedding.",
                RuntimeWarning,
                stacklevel=2,
            )
            return ImageSeries(
                name=name,
                description=(f"PVFS embedded video stream '{stream_name}' (no frames decoded)."),
                unit="n.a.",
                data=np.zeros((0, 1, 1, 3), dtype=np.uint8),
                starting_time=starting_time,
                rate=frame_rate,
            )

        data = np.stack(decoded, axis=0).astype(np.uint8)
        return ImageSeries(
            name=name,
            description=(
                f"PVFS embedded video stream '{stream_name}' "
                f"({data.shape[2]}x{data.shape[1]}, {frame_rate:.3f} fps)."
            ),
            unit="n.a.",
            data=data,
            starting_time=starting_time,
            rate=frame_rate,
        )
