from abc import abstractmethod
from typing import Literal

import numpy as np
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

    A manual scorer is also an events interface and supplies its scored occurrences through
    :meth:`_get_ethogram_events`. They are written as an ``EthogramEvents`` described by a typed ``EventTables``
    entry, and the bouts are derived from their closed states instead of from :meth:`_get_bouts`.
    """

    # Manual scorers write each closed state twice: as a row of the EthogramEvents record and as a bout of
    # an EthogramBouts table linked to that record through source_events. Downstream tools (pynapple, the
    # Neurosift ethogram widget) read bouts, so a manual scoring reaches them in the same shape as a
    # segmentation. The bouts are cheap to write and can always be recomputed from the record. And in
    # behavior the line between an event with a duration and an interval is not clear, and a format rarely
    # says which one it meant, so every scored interval also goes into EthogramBouts and a reader does not
    # have to guess. A reader counts one table or the other, never both.

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

    def _get_bouts(self) -> dict:
        """Return the bouts as ``start_times``, ``stop_times`` and ``labels``, one entry per bout.

        Required unless :meth:`_get_ethogram_events` returns events, whose closed states are the bouts.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement `_get_bouts` or `_get_ethogram_events`.")

    def _get_ethogram_events(self) -> dict | None:
        """Return the scored occurrences of a manual scorer, or ``None`` for a producer that has none.

        The ``_EventsData`` of each behavior keyed by its ``event_type_source_id``, with times on the current
        clock. A manual scorer, which is also an events interface, returns ``self._get_aligned_events_data_dict()``.
        """
        return None

    def _get_source(self, nwbfile: NWBFile, metadata: dict):
        """Return the object in the file the bouts were derived from, linked from them as ``source``.

        ``None`` by default, for a source with no such object.
        """
        return None

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
        """Write the catalogue, the scored events of a manual scorer, and the bouts.

        The catalogue and the bouts go to the file's behavior module. The events go to ``nwbfile.events`` as the
        ``EthogramEvents`` their ``EventTables`` entry describes, and the bouts are then their closed states,
        linked to them through ``source_events``.

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

        events_data = self._get_ethogram_events()
        source_events = None
        if events_data is None:
            bouts = self._get_bouts()
        else:
            from ...tools.events import _add_events_to_nwbfile

            _add_events_to_nwbfile(nwbfile, events_data=events_data, metadata=metadata, metadata_key=self.metadata_key)

            # The bouts are the closed states: a state behavior's occurrences that have a duration. A point
            # has no extent, and a state nobody closed has no stop time.
            event_types = metadata["Events"][self.metadata_key]["event_types"]
            behavior_types = {row["behavior"]: row.get("behavior_type") for row in self._get_behaviors()}
            start_times, stop_times, labels = [], [], []
            for event_type_source_id, events in events_data.items():
                event_name = event_types[event_type_source_id]["event_name"]
                if behavior_types.get(event_name) != "state" or events.durations is None:
                    continue
                closed = np.isfinite(events.durations)
                start_times.extend(events.timestamps[closed])
                stop_times.extend(events.timestamps[closed] + events.durations[closed])
                labels.extend([event_name] * int(closed.sum()))
            order = np.argsort(start_times, kind="stable")
            bouts = dict(
                start_times=[start_times[index] for index in order],
                stop_times=[stop_times[index] for index in order],
                labels=[labels[index] for index in order],
            )

            # The record the behaviors route to, when they all route to one.
            event_tables = metadata["Events"].get("EventTables", {})
            table_metadata_keys = {
                entry.get("table_metadata_key", event_type_source_id)
                for event_type_source_id, entry in event_types.items()
            }
            if len(table_metadata_keys) == 1:
                table_entry = event_tables.get(next(iter(table_metadata_keys)), {})
                if table_entry.get("type") == "EthogramEvents":
                    source_events = nwbfile.events[table_entry["table_name"]]

        entry_arguments = _resolve_ethogram_bouts_entry(nwbfile, metadata=metadata, metadata_key=self.metadata_key)
        _add_ethogram_bouts_to_nwbfile(
            nwbfile,
            **bouts,
            bouts_metadata=entry_arguments["ethogram_metadata"]["EthogramBouts"],
            labeling_method=entry_arguments.get("labeling_method", self.labeling_method),
            annotator=entry_arguments.get("annotator"),
            catalogue=catalogue,
            bout_concurrency=self.bout_concurrency,
            source_software=self.source_software,
            source=self._get_source(nwbfile, metadata),
            source_pose=entry_arguments["source_pose"],
            source_video=entry_arguments["source_video"],
            source_events=source_events,
        )
