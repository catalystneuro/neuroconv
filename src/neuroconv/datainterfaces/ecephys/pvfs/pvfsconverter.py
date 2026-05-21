"""High-level NWB converter for Pinnacle PVFS recordings.

The converter introspects the PVFS file once at construction time and builds a
matching set of NeuroConv data interfaces:

* one :class:`PvfsRecordingInterface` for **each** sampling-rate group of
  indexed channels (e.g. an EEG channel set at 400 Hz and an EMG channel set
  at 2000 Hz become two interfaces);
* one :class:`PvfsAnnotationsInterface` when the experiment database contains
  annotations and ``include_annotations`` is ``True``;
* one :class:`PvfsSleepScoringInterface` when the experiment database
  contains sleep-stage scoring and ``include_sleep_scoring`` is ``True`` (one
  NWB ``TimeIntervals`` table per populated scoring session);
* one :class:`PvfsVideoInterface` when the PVFS contains embedded video and
  ``include_video`` is ``True``.

The converter inherits from :class:`~neuroconv.ConverterPipe`, which is the
standard NeuroConv pattern for converters built from pre-instantiated
interfaces.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import FilePath
from pynwb import NWBFile

from .pvfsannotationsinterface import PvfsAnnotationsInterface
from .pvfsdatainterface import PvfsRecordingInterface
from .pvfssleepscoringinterface import PvfsSleepScoringInterface
from .pvfsvideointerface import PvfsVideoInterface
from ....nwbconverter import ConverterPipe


def _rate_label(rate: float) -> str:
    """Build a short human-readable label for a sampling rate (e.g. ``400Hz``)."""
    if rate == int(rate):
        return f"{int(rate)}Hz"
    return f"{rate:.3f}Hz".rstrip("0").rstrip(".")


class PvfsConverter(ConverterPipe):
    """Top-level converter that wires every PVFS data type into one NWBFile."""

    display_name = "Pinnacle PVFS"
    keywords = ("Pinnacle", "PVFS", "EEG", "NWB")
    associated_suffixes = (".pvfs",)
    info = "Converter for Pinnacle Technology PVFS recordings."

    def __init__(
        self,
        file_path: FilePath,
        include_annotations: bool = True,
        include_sleep_scoring: bool = True,
        include_video: bool = True,
        video_output_dir: str | Path | None = None,
        embed_frames: bool = False,
        verbose: bool = False,
    ) -> None:
        """Build one interface per sampling-rate group + optional annotations/scoring/video."""
        from ._metadata import (
            discover_video_stream_bases,
            filter_indexed_channels,
            open_pvfs,
            read_pvfs_metadata,
            read_sleep_scoring_sessions_from_pvfs,
        )
        from .extractors.pvfs_recording_extractor import _channel_sampling_rate

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PVFS file not found: {file_path}")

        self.file_path = str(file_path)
        self.include_annotations = bool(include_annotations)
        self.include_sleep_scoring = bool(include_sleep_scoring)
        self.include_video = bool(include_video)
        self.video_output_dir = Path(video_output_dir) if video_output_dir else None
        self.embed_frames = bool(embed_frames)

        pvfs_meta = read_pvfs_metadata(file_path)
        with open_pvfs(file_path) as vfs:
            video_bases = discover_video_stream_bases(vfs)
        indexed_channels = filter_indexed_channels(pvfs_meta.channels, video_bases)

        rate_groups: dict[float, list[str]] = defaultdict(list)
        for name, info in indexed_channels.items():
            rate = _channel_sampling_rate(info)
            if rate is not None and rate > 0:
                rate_groups[rate].append(name)

        if not rate_groups:
            raise ValueError(
                f"No indexed channels with a usable sampling rate were found in {file_path}."
            )

        interfaces: dict[str, object] = {}
        sorted_rates = sorted(rate_groups.keys())
        for rate in sorted_rates:
            label = _rate_label(rate)
            es_key = f"ElectricalSeriesPVFS{label}"
            interface_name = f"Recording{label}" if len(sorted_rates) > 1 else "Recording"
            interfaces[interface_name] = PvfsRecordingInterface(
                file_path=str(file_path),
                sampling_rate_hz=rate,
                es_key=es_key,
                verbose=verbose,
            )

        if self.include_annotations and pvfs_meta.annotations:
            interfaces["Annotations"] = PvfsAnnotationsInterface(
                file_path=str(file_path), verbose=verbose
            )

        if self.include_sleep_scoring:
            # Cheap pre-check (one SQLite query) so we only spin up the
            # interface when actual scored epochs exist.
            scoring_sessions = read_sleep_scoring_sessions_from_pvfs(file_path)
            if any(session.epochs for session in scoring_sessions.values()):
                interfaces["SleepScoring"] = PvfsSleepScoringInterface(
                    file_path=str(file_path), verbose=verbose
                )

        if self.include_video:
            video_interface = PvfsVideoInterface(
                file_path=str(file_path),
                video_output_dir=str(self.video_output_dir) if self.video_output_dir else None,
                embed_frames=self.embed_frames,
                verbose=verbose,
            )
            if video_interface.has_video():
                interfaces["Video"] = video_interface

        super().__init__(data_interfaces=interfaces, verbose=verbose)

    def run_conversion(
        self,
        nwbfile_path: FilePath,
        nwbfile: NWBFile | None = None,
        metadata: dict | None = None,
        overwrite: bool = False,
        backend: Literal["hdf5", "zarr"] | None = None,
        backend_configuration=None,
        conversion_options: dict | None = None,
        append_on_disk_nwbfile: bool = False,
    ) -> None:
        """Resolve the video output directory and delegate to :class:`ConverterPipe`."""
        # Resolve the WebM output directory from the NWB output location so the
        # external video lives next to the .nwb file by default.  Users can
        # override this by passing ``video_output_dir`` at construction time.
        for iface in self.data_interface_objects.values():
            if isinstance(iface, PvfsVideoInterface) and iface.video_output_dir is None:
                iface.video_output_dir = Path(nwbfile_path).resolve().parent

        super().run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            backend=backend,
            backend_configuration=backend_configuration,
            conversion_options=conversion_options,
            append_on_disk_nwbfile=append_on_disk_nwbfile,
        )
