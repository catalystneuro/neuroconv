import warnings
from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import TimeSeries
from pynwb.file import NWBFile

from ._abf_tag_reader import read_abf_tags
from ...events.baseeventsinterface import BaseEventsInterface, _EventsData


class AxonEventsInterface(BaseEventsInterface):
    """Read file-wide Axon tags as discrete events, including tags between sweeps."""

    display_name = "AxonEvents"
    info = "Interface for the tags in an Axon ABF file."
    keywords = ("events", "icephys", "Axon")
    associated_suffixes = (".abf",)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        event_extraction_configuration: dict | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Read tags from one file, optionally separating them by recorded payload fields.

        The default writes one event table for each tag type present in the file.

        Parameters
        ----------
        file_path : FilePath
            Axon Binary Format file containing the tags.
        event_extraction_configuration : dict, optional
            Named extraction entries. Each reads the file-wide source ``tags``, which may be omitted.
            Use ``separation.by_payload_fields`` to group rows by one or two fields and ``select`` to
            request particular values or pairs.
        metadata_key : str, optional
            Key for this file in the events metadata. Defaults to the file stem followed by ``_axon_events``.
        verbose : bool, default: False
            Display conversion progress.
        """
        self._abf_tags = read_abf_tags(file_path)
        self._configuration = event_extraction_configuration
        self._indices_by_type = {}
        self.metadata_key = metadata_key or f"{Path(file_path).stem}_axon_events"
        super().__init__(
            file_path=file_path,
            event_extraction_configuration=event_extraction_configuration,
            metadata_key=metadata_key,
            verbose=verbose,
        )

    @staticmethod
    def get_available_event_sources(file_path: str | Path) -> list[str]:
        """Return the file-wide source of Axon tags."""
        with open(file_path, "rb") as file:
            if file.read(4) not in (b"ABF ", b"ABF2"):
                raise ValueError(f"'{file_path}' does not start with an ABF signature.")
        return ["tags"]

    def _voice_series_name(self, index):
        prefix = self.metadata_key.replace("/", "_").replace(":", "_")
        return f"{prefix}_voice_tag_{index}"

    def _get_events_data_dict(self):
        if self._events_data_dict is not None:
            return self._events_data_dict
        tags = self._abf_tags.tags
        payload = {
            "tag_time": tags["time"],
            "tag_type": tags["type"],
            "comment": tags["comment"],
            "voice_tag_or_annotation_index": tags["voice_tag_or_annotation_index"],
            "annotation": tags["annotation"],
            "sweep_index": tags["sweep_index"],
            "voice_series_name": np.asarray(
                [self._voice_series_name(index) if tag["type"] == 3 else "" for index, tag in enumerate(tags)],
                dtype=str,
            ),
        }
        selection_fields = {**payload, "tag_type": tags["type_name"]}
        configuration = self._configuration
        if configuration is None:
            configuration = {"tags": {"separation": {"by_payload_fields": ["tag_type"]}}}
        if not isinstance(configuration, dict) or not configuration:
            raise ValueError("event_extraction_configuration must be a non-empty dictionary.")
        result, origins = {}, {}
        for name, entry in configuration.items():
            if not isinstance(name, str) or not name or not isinstance(entry, dict):
                raise ValueError("Each extraction entry must have a non-empty name and a dictionary value.")
            if set(entry) - {"source", "separation"}:
                raise ValueError(f"Unsupported keys in extraction entry '{name}'.")
            if entry.get("source", "tags") != "tags":
                raise ValueError(
                    f"Source {entry.get('source')!r} is unavailable; available sources: ['tags']. "
                    "Call get_available_event_sources() to list them."
                )
            fields, groups, missing_labels = self._group_tags(entry.get("separation"), selection_fields, tags)
            for values, indices in groups:
                identifier = "_".join(
                    [name]
                    + [
                        missing_labels[position] if value is None else str(value)
                        for position, value in enumerate(values)
                    ]
                )
                origin = (name, dict(zip(fields, values)))
                if identifier in result:
                    raise ValueError(
                        f"Event type identifier '{identifier}' collides between {origins[identifier]} and "
                        f"{origin}. Rename an entry, change the separation fields, or correct the source values."
                    )
                origins[identifier] = origin
                self._indices_by_type[identifier] = indices
                result[identifier] = _EventsData(
                    event_type_source_id=identifier,
                    timestamps=tags["time_in_seconds"][indices],
                    payload={field: values_array[indices] for field, values_array in payload.items()},
                )
        self._events_data_dict = result
        return result

    @staticmethod
    def _group_tags(separation, payload, tags):
        if separation is None:
            return [], [((), np.arange(len(tags)))], []
        if not isinstance(separation, dict) or set(separation) - {"by_payload_fields", "select"}:
            raise ValueError("Invalid separation in extraction entry.")
        fields = separation.get("by_payload_fields")
        if (
            not isinstance(fields, list)
            or len(fields) not in (1, 2)
            or any(not isinstance(field, str) for field in fields)
            or len(set(fields)) != len(fields)
        ):
            raise ValueError("by_payload_fields must contain one or two distinct field names.")
        if any(field not in payload for field in fields):
            raise ValueError(f"Unknown payload field; available fields: {list(payload)}.")
        indexed = {}
        for index in range(len(tags)):
            values = tuple(
                (
                    None
                    if (field == "comment" and tags["type"][index] == 0 and not payload[field][index])
                    or (field == "annotation" and tags["type"][index] != 5)
                    else _scalar(payload[field][index])
                )
                for field in fields
            )
            indexed.setdefault(values, []).append(index)
        selection = separation.get("select")
        if selection is None:
            values_list = list(indexed)
        else:
            if not isinstance(selection, list):
                raise ValueError("select must be a list.")
            values_list = []
            for item in selection:
                if len(fields) == 1:
                    if isinstance(item, (dict, list)):
                        raise ValueError("A one-field select contains scalar values.")
                    values = (_scalar(item),)
                else:
                    if not isinstance(item, dict) or set(item) != set(fields):
                        raise ValueError("A two-field select must give a value for each field.")
                    values = tuple(_scalar(item[field]) for field in fields)
                for field, requested in zip(fields, values):
                    field_type = int if payload[field].dtype.kind in "iu" else str
                    if requested is not None and type(requested) is not field_type:
                        raise ValueError(
                            f"Requested {field} value {requested!r} has type {type(requested).__name__}; "
                            f"recorded values have type {field_type.__name__}."
                        )
                if values not in values_list:
                    values_list.append(values)
        missing_labels = []
        for position, field in enumerate(fields):
            fallback = any(row[position] == "missing" for row in indexed) and any(
                row[position] is None for row in values_list
            )
            missing_labels.append("not_recorded" if fallback else "missing")
            if fallback:
                warnings.warn(
                    f"Field '{field}' contains the value 'missing'; missing values use 'not_recorded' "
                    "in event identifiers."
                )
        groups = [(values, np.asarray(indexed.get(values, []), dtype=int)) for values in values_list]
        return fields, groups, missing_labels

    def get_metadata(self):
        metadata = super().get_metadata()
        if self._abf_tags.session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = self._abf_tags.session_start_time
        descriptions = {
            "tag_type": "The Axon tag type: time, comment, external, voice, new_file, or annotation.",
            "comment": "The recorded tag comment.",
            "voice_tag_or_annotation_index": "The stored voice tag number or annotation index, interpreted according to tag_type.",
            "annotation": "The annotation text, empty for other tag types.",
            "sweep_index": "Index of the sweep containing the tag, or -1 outside recorded sweeps.",
            "voice_series_name": "Name of the acquisition time series containing the voice recording, empty for other tag types.",
        }
        tags = self._abf_tags.tags
        type_labels = {str(code): name for code, name in zip(tags["type"], tags["type_name"])}
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        for identifier in self.get_event_type_source_ids():
            columns = {field: {"column_name": field, "description": text} for field, text in descriptions.items()}
            columns["tag_type"]["column_categories"] = {"labels": type_labels.copy()}
            event_types[identifier] = {
                "event_name": f"{self.metadata_key}_{identifier}",
                "columns": columns,
            }
        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None) -> None:
        if metadata is None:
            metadata = self.get_metadata()
        selected_types = metadata.get("Events", {}).get(self.metadata_key, {}).get("event_types", {})
        voice_times = {}
        for identifier in selected_types:
            indices = self._indices_by_type[identifier]
            for index, time in zip(indices, self.get_event_times(identifier)):
                if self._abf_tags.tags[index]["type"] != 3:
                    continue
                if index in voice_times and voice_times[index] != time:
                    raise ValueError(f"Voice tag {index} is selected with conflicting aligned times.")
                voice_times[index] = time
        for index in voice_times:
            name = self._voice_series_name(index)
            if name in nwbfile.acquisition:
                raise ValueError(f"An acquisition named '{name}' already exists. Use a distinct metadata_key.")
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        for index, time in voice_times.items():
            voice_number = int(self._abf_tags.tags[index]["voice_tag_or_annotation_index"])
            voice = self._abf_tags.voice_tags[voice_number]
            conversion = 1 / 2 ** (voice.bits_per_sample - 1)
            offset = -1.0 if voice.samples.dtype.kind == "u" else 0.0
            nwbfile.add_acquisition(
                TimeSeries(
                    name=self._voice_series_name(index),
                    data=voice.samples,
                    unit="normalized intensity",
                    conversion=conversion,
                    offset=offset,
                    starting_time=float(time),
                    rate=voice.sampling_frequency,
                    description=f"Voice tag {voice_number} from {Path(self.source_data['file_path']).name}.",
                )
            )


def _scalar(value):
    return value.item() if isinstance(value, np.generic) else value
