from collections import defaultdict
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from pydantic import ConfigDict, Field, FilePath, StrictStr, validate_call
from typing_extensions import NotRequired, TypedDict

from ._edf_annotations_reader import _read_annotations
from ...events.baseeventsinterface import BaseEventsInterface, _EventsData
from ....utils import DeepDict


class _Separation(TypedDict):
    __pydantic_config__ = ConfigDict(extra="forbid")

    by_payload_fields: Annotated[list[Literal["annotation"]], Field(min_length=1, max_length=1)]
    select: NotRequired[list[StrictStr]]


class _ExtractionEntry(TypedDict, total=False):
    __pydantic_config__ = ConfigDict(extra="forbid")

    source: Literal["annotations"]
    separation: _Separation


class EDFEventsInterface(BaseEventsInterface):
    """Convert annotations in an EDF+ or BDF+ file to events.

    By default, the interface writes one ``EDFAnnotations`` table with the original text in
    ``annotation``. Timestamps are in seconds from the start of the first data record. The optional
    ``duration`` column holds supplied durations in seconds, with NaN where the file omitted a duration.
    """

    display_name = "EDF Events"
    keywords = ("events", "edf", "bdf", "annotations")
    associated_suffixes = (".edf", ".bdf")
    info = "Interface for converting pre-extracted annotations in EDF+ and BDF+ files."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        event_extraction_configuration: dict[str, _ExtractionEntry] | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the EDFEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the EDF+ or BDF+ file.
        event_extraction_configuration : dict, optional
            Entries keyed by the desired event type name. Each entry can name the ``"annotations"``
            source and specify ``separation={"by_payload_fields": ["annotation"]}`` to write one event
            type per distinct text. Add ``select`` inside ``separation`` to request specific texts,
            including types with no matches. With None, write one ``EDFAnnotations`` table.
        metadata_key : str, optional
            Key under ``metadata["Events"]``. Defaults to the file stem.
        verbose : bool, default: False
            Whether to print status messages.
        """
        self.metadata_key = metadata_key or Path(file_path).stem
        super().__init__(
            file_path=file_path,
            event_extraction_configuration=event_extraction_configuration,
            metadata_key=metadata_key,
            verbose=verbose,
        )

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        if self._events_data_dict is not None:
            return self._events_data_dict

        self._session_start_time, timestamps, durations, annotations = _read_annotations(self.source_data["file_path"])
        order = np.argsort(timestamps, kind="stable")
        timestamps, durations, annotations = timestamps[order], durations[order], annotations[order]
        configuration = self.source_data["event_extraction_configuration"]
        if configuration is None:
            configuration = {"EDFAnnotations": {}}

        indices_by_annotation = defaultdict(list)
        if any("separation" in entry for entry in configuration.values()):
            for index, annotation in enumerate(annotations):
                indices_by_annotation[annotation].append(index)

        events = {}
        entry_names = {}
        for entry_name, entry in configuration.items():
            separation = entry.get("separation")
            if separation is None:
                groups = {entry_name: slice(None)}
            else:
                selected = separation.get("select")
                if selected is None:
                    selected = indices_by_annotation
                groups = {f"{entry_name}_{text}": indices_by_annotation.get(text, []) for text in selected}

            for source_id, indices in groups.items():
                if source_id in events:
                    raise ValueError(
                        f"Extraction entries {entry_names[source_id]!r} and {entry_name!r} both produce "
                        f"event type {source_id!r}. Rename one of the entries to give each type a distinct identifier."
                    )
                event_durations = durations[indices]
                events[source_id] = _EventsData(
                    event_type_source_id=source_id,
                    timestamps=timestamps[indices],
                    durations=event_durations if not np.isnan(event_durations).all() else None,
                    payload={"annotation": annotations[indices]},
                )
                entry_names[source_id] = entry_name

        self._events_data_dict = events
        return events

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = self._session_start_time
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        for source_id in self.get_event_type_source_ids():
            event_types[source_id] = {"event_name": source_id, "columns": {"annotation": {"column_name": "annotation"}}}
        return metadata
