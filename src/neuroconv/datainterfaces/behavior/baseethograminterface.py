from abc import abstractmethod
from typing import Literal

from pynwb.file import NWBFile

from ...basedatainterface import BaseDataInterface
from ...tools.nwb_helpers._metadata_and_file_helpers import _validate_metadata_key

__all__ = ["BaseEthogramInterface"]


class BaseEthogramInterface(BaseDataInterface):
    """Base class for interfaces writing an ``ndx-ethogram`` ``Ethogram`` catalogue and the ``EthogramBouts`` scored
    against it.

    The two objects are described by two metadata fields keyed by the interface's ``metadata_key``:
    ``metadata["Behavior"]["EthogramBouts"][metadata_key]`` for the bouts, whose ``ethogram_metadata_key`` names the
    catalogue's entry in ``metadata["Behavior"]["Ethograms"]``. A subclass supplies the catalogue rows and the bouts,
    sets ``metadata_key`` before calling ``__init__``, and fills the two entries in ``get_metadata``.
    """

    keywords = ("behavior", "ethogram")

    labeling_method: Literal["manual", "automated", "curated"]
    """How the labels were produced, used when the bouts entry does not say."""
    source_software: str | None = None
    """The tool that produced the labels, written on the bouts."""
    bout_concurrency: Literal["partition", "disjoint", "concurrent"] | None = None
    """How the bouts of one subject relate in time, written on the bouts. ``None`` when the source does not say."""

    @abstractmethod
    def _get_behaviors(self) -> list[dict]:
        """Return the catalogue rows, one per behavior: ``behavior`` and ``definition``, optionally
        ``behavior_type``, ``native_code`` and ``category``."""

    @abstractmethod
    def _get_bouts(self) -> dict:
        """Return the bouts as ``start_times``, ``stop_times`` and ``labels``, one entry per bout."""

    def get_metadata_schema(self) -> dict:
        from ...tools.behavior import _get_ethogram_metadata_schema
        from ...utils import get_base_schema

        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        # Left open so the metadata other interfaces write under Behavior survives validation in a converter.
        metadata_schema["properties"]["Behavior"]["additionalProperties"] = True
        metadata_schema["properties"]["Behavior"]["properties"] = _get_ethogram_metadata_schema()
        return metadata_schema

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None) -> None:
        """Write the catalogue and the bouts to the file's behavior module.

        The caller's metadata reaches the writers as they wrote it. It is not merged over this interface's
        defaults, so a key the caller removed stays removed: a bouts entry without ``ethogram_metadata_key``
        writes bouts with no catalogue. The pose estimation and the video the bouts entry's
        ``source_pose_metadata_key`` and ``source_video_metadata_key`` name must already be in the file.

        Parameters
        ----------
        nwbfile : NWBFile
            Target NWB file.
        metadata : dict, optional
            Metadata dictionary. Defaults to ``get_metadata()``.
        """
        from ...tools.behavior import (
            _add_ethogram_bouts_to_nwbfile,
            _add_ethogram_catalogue_to_nwbfile,
            _resolve_ethogram_bouts_entry,
        )

        metadata = metadata if metadata is not None else self.get_metadata()

        _validate_metadata_key(metadata, metadata_path=("Behavior", "EthogramBouts"), metadata_key=self.metadata_key)
        catalogue = None
        ethogram_metadata_key = metadata["Behavior"]["EthogramBouts"][self.metadata_key].get("ethogram_metadata_key")
        if ethogram_metadata_key is not None:
            _validate_metadata_key(
                metadata, metadata_path=("Behavior", "Ethograms"), metadata_key=ethogram_metadata_key
            )
            catalogue = _add_ethogram_catalogue_to_nwbfile(
                nwbfile,
                behaviors=self._get_behaviors(),
                catalogue_metadata=metadata["Behavior"]["Ethograms"][ethogram_metadata_key],
            )

        entry_arguments = _resolve_ethogram_bouts_entry(nwbfile, metadata=metadata, metadata_key=self.metadata_key)
        _add_ethogram_bouts_to_nwbfile(
            nwbfile,
            **self._get_bouts(),
            bouts_metadata=entry_arguments["ethogram_metadata"]["EthogramBouts"],
            labeling_method=entry_arguments.get("labeling_method", self.labeling_method),
            annotator=entry_arguments.get("annotator"),
            catalogue=catalogue,
            bout_concurrency=self.bout_concurrency,
            source_software=self.source_software,
            source_pose=entry_arguments["source_pose"],
            source_video=entry_arguments["source_video"],
        )
