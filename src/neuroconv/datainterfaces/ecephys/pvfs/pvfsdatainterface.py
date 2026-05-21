"""NeuroConv interface that maps a PVFS recording to an ``ElectricalSeries``.

This module is intentionally thin: most of the heavy lifting is done by
:class:`~neuroconv.datainterfaces.ecephys.baserecordingextractorinterface.BaseRecordingExtractorInterface`
and the :class:`PvfsRecordingExtractor`.  The interface picks a single sampling
rate group (the most common rate in the PVFS by default) and exposes it as one
``ElectricalSeries``.  To convert multi-rate PVFS files, use
:class:`~neuroconv.datainterfaces.ecephys.pvfs.pvfsconverter.PvfsConverter`,
which builds one recording interface per rate group.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....tools import get_package
from ....utils import DeepDict


class PvfsRecordingInterface(BaseRecordingExtractorInterface):
    """Convert one sampling-rate group of a PVFS file to an ``ElectricalSeries``.

    Parameters
    ----------
    file_path : path-like
        Path to the ``.pvfs`` file.
    sampling_rate_hz : float, optional
        Restrict the interface to channels whose data rate matches this value.
        Defaults to the most common rate inside the PVFS container.
    channel_names : list of str, optional
        Restrict the interface to a specific set of channels (all of which
        must share the same sampling rate).
    verbose : bool, default: False
        Forwarded to :class:`BaseRecordingExtractorInterface`.
    es_key : str, default: "ElectricalSeries"
        Key under ``metadata['Ecephys']`` that controls the
        ``ElectricalSeries`` configuration.
    """

    display_name = "PVFS Recording"
    keywords = BaseRecordingExtractorInterface.keywords + (
        "Pinnacle",
        "PVFS",
        "EEG",
    )
    associated_suffixes = (".pvfs",)
    info = "Interface for Pinnacle Technology PVFS time-series recordings."

    @classmethod
    def get_extractor_class(cls):
        """Return :class:`PvfsRecordingExtractor` (imported lazily)."""
        get_package(
            package_name="pvfs_tools",
            installation_instructions='pip install "neuroconv[pvfs]"',
        )
        from .extractors.pvfs_recording_extractor import PvfsRecordingExtractor

        return PvfsRecordingExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        """Return the JSON schema for the source arguments of this interface."""
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the Pinnacle .pvfs container."
        return source_schema

    def __init__(
        self,
        file_path: FilePath,
        sampling_rate_hz: float | None = None,
        channel_names: list[str] | None = None,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ) -> None:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"PVFS file not found: {file_path}")
        super().__init__(
            file_path=str(file_path),
            sampling_rate_hz=sampling_rate_hz,
            channel_names=channel_names,
            verbose=verbose,
            es_key=es_key,
        )
        self.file_path = str(file_path)

    def get_metadata(self) -> DeepDict:
        """Build the metadata dictionary, prefilled from ``experiment.db3``."""
        from ._metadata import read_pvfs_metadata

        metadata = super().get_metadata()

        pvfs_meta = read_pvfs_metadata(self.file_path)
        nwb_meta = pvfs_meta.to_nwb_metadata()

        if "NWBFile" in nwb_meta:
            metadata["NWBFile"].update(nwb_meta["NWBFile"])
        if "Subject" in nwb_meta:
            metadata["Subject"].update(nwb_meta["Subject"])

        ecephys = metadata.setdefault("Ecephys", DeepDict())
        # ``manufacturer`` is deprecated on Device in newer pynwb; the
        # recommended path is to link to a DeviceModel.  We omit it here to
        # avoid the deprecation warning and leave the manufacturer information
        # to the description.
        ecephys["Device"] = [
            dict(
                name="DevicePVFS",
                description=(
                    "Pinnacle Technology data acquisition (PVFS source). " "Manufacturer: Pinnacle Technology, Inc."
                ),
            )
        ]
        ecephys["ElectrodeGroup"] = [
            dict(
                name="PVFSGroup",
                description=(
                    "Channels sourced from a Pinnacle PVFS recording. "
                    "PVFS does not record stereotaxic targets; ``location`` is "
                    "set to the Allen CCF root term for schema compliance."
                ),
                # Allen CCF acronym (required by NeuroConv); not a measured coordinate.
                location="root",
                device="DevicePVFS",
            )
        ]

        if self.es_key is not None:
            rate = self.recording_extractor.selected_sampling_rate
            rate_label = f"{rate:.0f}Hz" if rate == int(rate) else f"{rate:.3f}Hz"
            # Avoid double-decorating when PvfsConverter (which controls multi-rate
            # naming) already encoded "PVFS<rate>" into the es_key for us.
            if "PVFS" in self.es_key:
                es_name = self.es_key
            else:
                es_name = f"{self.es_key}PVFS{rate_label}"
            ecephys[self.es_key] = dict(
                name=es_name,
                description=("PVFS indexed time-series channels grouped by sampling rate " f"({rate_label})."),
            )

        self._apply_channel_properties()
        return metadata

    def _apply_channel_properties(self) -> None:
        """Push per-channel metadata onto the SpikeInterface recording.

        Sets ``group_name`` (always ``"PVFSGroup"``) so the
        ``add_recording_to_nwbfile`` helper places every channel under the
        ``PVFSGroup`` electrode group.  We deliberately leave SpikeInterface's
        ``location`` property unset because that property is interpreted as a
        Nx3 coordinate array (rel_x/rel_y/rel_z); PVFS has no positional
        information. Per-electrode ``location`` is unset; the group's Allen CCF
        ``location`` is the root term because PVFS does not record brain regions.
        """
        n = self.recording_extractor.get_num_channels()
        self.recording_extractor.set_property("group_name", ["PVFSGroup"] * n)
        # NeuroConv maps ``brain_area`` to the electrodes table ``location`` column.
        self.recording_extractor.set_property("brain_area", ["root"] * n)

    def add_to_nwbfile(
        self,
        nwbfile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        write_as: str = "raw",
        write_electrical_series: bool = True,
        iterator_type: str | None = "v2",
        iterator_options: dict | None = None,
        always_write_timestamps: bool = False,
        **extra: Any,
    ) -> None:
        """Append a PVFS ``ElectricalSeries`` (and the requisite Device/group) to ``nwbfile``."""
        if metadata is None:
            metadata = self.get_metadata()
        else:
            # Ensure channel properties are seeded even when the caller supplied
            # their own metadata dictionary (and thus skipped ``get_metadata``).
            self._apply_channel_properties()
        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            write_as=write_as,
            write_electrical_series=write_electrical_series,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
            always_write_timestamps=always_write_timestamps,
        )
