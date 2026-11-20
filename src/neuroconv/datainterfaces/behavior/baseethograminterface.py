from abc import abstractmethod
from typing import Literal

from pynwb.file import NWBFile

from ...basedatainterface import BaseDataInterface
from ...tools.nwb_helpers import get_module
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
        writes bouts with no catalogue.

        Parameters
        ----------
        nwbfile : NWBFile
            Target NWB file.
        metadata : dict, optional
            Metadata dictionary. Defaults to ``get_metadata()``.
        """
        metadata = metadata if metadata is not None else self.get_metadata()
        self.add_ethogram_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        self.add_bouts_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    def add_ethogram_to_nwbfile(self, nwbfile: NWBFile, metadata: dict) -> None:
        """Write the ``Ethogram`` catalogue, or extend the one of the same name already in the file.

        Writes nothing when the bouts entry has no ``ethogram_metadata_key``.

        Parameters
        ----------
        nwbfile : NWBFile
            Target NWB file.
        metadata : dict
            Metadata dictionary.
        """
        from ...tools.behavior import _add_ethogram_catalogue_to_nwbfile

        _validate_metadata_key(metadata, metadata_path=("Behavior", "EthogramBouts"), metadata_key=self.metadata_key)
        ethogram_metadata_key = metadata["Behavior"]["EthogramBouts"][self.metadata_key].get("ethogram_metadata_key")
        if ethogram_metadata_key is None:
            return
        _validate_metadata_key(metadata, metadata_path=("Behavior", "Ethograms"), metadata_key=ethogram_metadata_key)
        _add_ethogram_catalogue_to_nwbfile(
            nwbfile,
            behaviors=self._get_behaviors(),
            catalogue_metadata=metadata["Behavior"]["Ethograms"][ethogram_metadata_key],
        )

    def add_bouts_to_nwbfile(self, nwbfile: NWBFile, metadata: dict) -> None:
        """Write the ``EthogramBouts`` table, linked to the catalogue its entry names.

        That catalogue must already be in the file, written by ``add_ethogram_to_nwbfile``. So must the pose
        estimation and the video the entry's ``source_pose_metadata_key`` and ``source_video_metadata_key`` name.

        Parameters
        ----------
        nwbfile : NWBFile
            Target NWB file.
        metadata : dict
            Metadata dictionary.
        """
        from ...tools.behavior import _add_ethogram_bouts_to_nwbfile, _resolve_ethogram_bouts_entry

        entry_arguments = _resolve_ethogram_bouts_entry(nwbfile, metadata=metadata, metadata_key=self.metadata_key)
        catalogue = None
        catalogue_metadata = entry_arguments["ethogram_metadata"]["Ethogram"]
        if catalogue_metadata is not None:
            behavior_module = get_module(nwbfile=nwbfile, name="behavior")
            catalogue = behavior_module.data_interfaces.get(catalogue_metadata["name"])
            if catalogue is None:
                raise ValueError(
                    f"The bouts entry '{self.metadata_key}' names the catalogue '{catalogue_metadata['name']}', "
                    "which is not in the file. Call add_ethogram_to_nwbfile first."
                )

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
