from datetime import datetime
from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import TimeSeries
from pynwb.behavior import SpatialSeries
from pynwb.file import NWBFile

from ._ethovision_reader import (
    get_available_tracks,
    read_scoring_events,
    read_track,
    select_track_source,
)
from ...events.baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools import get_module
from ....utils import DeepDict, calculate_regular_series_rate, to_camel_case, to_snake_case

X_COLUMN = "X center"
Y_COLUMN = "Y center"


class EthoVisionDataInterface(BaseEventsInterface):
    """Interface for one Track in a Noldus EthoVision XT export.

    Excel, CSV, and TXT are container variants of the same Track model. An Excel workbook
    can contain several Tracks; ``arena_name`` and ``subject_name`` select one. A matching
    Excel Manual Scoring sheet can contain several subjects, so only the selected subject's
    events are retained.

    The selected source content is mapped to NWB as follows:

    * ``X center`` and ``Y center`` -> one :class:`~pynwb.behavior.SpatialSeries`.
    * Every other Track channel -> one :class:`~pynwb.base.TimeSeries`.
    * Manual Scoring rows for the selected subject -> one :class:`~pynwb.event.EventsTable`.
    * Manual Scoring behavior labels -> one ``ndx-ethogram`` ``Ethogram``.
    * Matching ``state start`` and ``state stop`` rows -> one ``EthogramBouts`` table.

    These objects are written directly to the ``behavior`` processing module.
    """

    display_name = "EthoVision"
    keywords = ("EthoVision", "Noldus", "tracking", "behavior", "events", "ethogram")
    associated_suffixes = (".xlsx", ".csv", ".txt")
    info = "Interface for Noldus EthoVision XT Track exports."

    @staticmethod
    def get_available_tracks(file_path: FilePath) -> list[dict[str, str]]:
        """Return the complete selector arguments for every available Track."""
        return get_available_tracks(file_path=file_path)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        arena_name: str | None = None,
        subject_name: str | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize an interface for one EthoVision Track.

        Parameters
        ----------
        file_path : FilePath
            Path to an EthoVision ``.xlsx``, ``.csv``, or ``.txt`` Track export.
        arena_name : str, optional
            Arena to select. Inferred when the source contains only one matching arena.
        subject_name : str, optional
            Subject to select. Inferred when the source contains only one matching subject.
        metadata_key : str, optional
            The key for this track's metadata and events blocks. By default it is derived from
            the Track sheet's arena and subject so several interfaces can share an NWB file.
        verbose : bool, default: False
            Whether to print progress.
        """
        self.file_path = Path(file_path)
        self.track_source = select_track_source(
            file_path=file_path,
            arena_name=arena_name,
            subject_name=subject_name,
        )
        self.arena = self.track_source.arena
        self.subject = self.track_source.subject
        self.metadata_key = metadata_key or f"ethovision_{to_snake_case(f'{self.arena}_{self.subject}')}"
        self._manual_scoring_metadata_key = f"ethovision_{to_snake_case(self.arena)}_manual_scoring"
        self.verbose = verbose
        super().__init__(
            file_path=file_path,
            arena_name=self.arena,
            subject_name=self.subject,
            metadata_key=self.metadata_key,
            verbose=verbose,
        )

        self._track = read_track(file_path=self.file_path, source=self.track_source)
        self._time_series_metadata_keys = {
            channel_name: f"{self.metadata_key}_{to_snake_case(channel_name)}"
            for channel_name in self._track.channels
            if channel_name not in (X_COLUMN, Y_COLUMN)
        }
        if len(set(self._time_series_metadata_keys.values())) != len(self._time_series_metadata_keys):
            raise ValueError(
                "EthoVision channel names must remain distinct after conversion to metadata keys. "
                f"Derived keys: {self._time_series_metadata_keys}."
            )
        self.alignment._register_series(key=self.metadata_key, get_native_times=lambda: self._track.recording_time)

        scoring_events = read_scoring_events(file_path=self.file_path, arena_name=self.arena)
        self._scoring_occurrences = [(self.arena, event) for event in scoring_events if event.subject == self.subject]
        self._event_onsets_alignment_key = f"{self.metadata_key}_manual_scoring_onsets"
        self._event_offsets_alignment_key = f"{self.metadata_key}_manual_scoring_offsets"
        if self._scoring_occurrences:
            self.alignment._register_series(
                key=self._event_onsets_alignment_key,
                get_native_times=lambda: np.asarray(
                    [event.onset for _, event in self._scoring_occurrences], dtype=float
                ),
            )
            self.alignment._register_series(
                key=self._event_offsets_alignment_key,
                get_native_times=self._get_native_event_offsets,
            )

    def _get_native_event_offsets(self) -> np.ndarray:
        return np.asarray(
            [
                event.onset + event.duration if event.duration is not None and not np.isnan(event.duration) else np.nan
                for _, event in self._scoring_occurrences
            ],
            dtype=float,
        )

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        named_series_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "unit": {"type": "string"},
            },
            "required": ["name", "description", "unit"],
            "additionalProperties": True,
        }
        spatial_series_schema = {
            "type": "object",
            "properties": {
                **named_series_schema["properties"],
                "reference_frame": {"type": "string"},
            },
            "required": [*named_series_schema["required"], "reference_frame"],
            "additionalProperties": True,
        }
        metadata_schema["properties"]["SpatialSeries"] = {
            "type": "object",
            "additionalProperties": spatial_series_schema,
        }
        metadata_schema["properties"]["TimeSeries"] = {
            "type": "object",
            "additionalProperties": named_series_schema,
        }
        metadata_schema["properties"]["Behavior"] = {
            "type": "object",
            "properties": {
                "Ethograms": {"type": "object", "additionalProperties": {"type": "object"}},
            },
            "additionalProperties": True,
        }
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        start_time = self._track.header.get("Start time")
        if start_time:
            metadata["NWBFile"]["session_start_time"] = _parse_start_time(start_time=start_time)

        object_suffix = to_camel_case(to_snake_case(f"{self.arena} {self.subject}"))
        metadata["SpatialSeries"][self.metadata_key] = dict(
            name=f"EthoVisionPosition{object_suffix}",
            description=f"Center position for {self.subject} in {self.arena}, from EthoVision.",
            unit=self._track.units.get(X_COLUMN) or "n/a",
            reference_frame="Arena, as EthoVision's own calibration defines it.",
        )
        metadata["TimeSeries"] = {
            self._time_series_metadata_keys[channel_name]: dict(
                name=(f"EthoVision{to_camel_case(to_snake_case(channel_name))}{object_suffix}"),
                description=f"'{channel_name}' channel from an EthoVision Track sheet.",
                unit=self._track.units.get(channel_name) or "n/a",
            )
            for channel_name in self._track.channels
            if channel_name not in (X_COLUMN, Y_COLUMN)
        }

        if self._scoring_occurrences:
            arena_suffix = to_camel_case(to_snake_case(self.arena))
            metadata["Behavior"]["Ethograms"][self._manual_scoring_metadata_key] = {
                "Ethogram": {
                    "name": f"EthoVisionEthogram{arena_suffix}",
                    "description": "Behavior catalogue inferred from EthoVision manual-scoring rows.",
                },
                "EthogramBouts": {
                    "name": f"EthoVisionEthogramBouts{arena_suffix}",
                    "description": "Closed state bouts from EthoVision manual scoring.",
                },
            }
            metadata["Events"]["EventTables"][self._manual_scoring_metadata_key] = {
                "table_name": f"EthoVisionManualScoring{arena_suffix}",
                "description": "Manual-scoring events from an EthoVision export.",
            }
            event_types = metadata["Events"][self.metadata_key]["event_types"]
            for source_id, events_data in self._get_events_data_dict().items():
                event_types[source_id] = {
                    "event_name": source_id.split(":", maxsplit=1)[1],
                    "table_metadata_key": self._manual_scoring_metadata_key,
                    "columns": {
                        "subject": {
                            "column_name": "subject",
                            "description": "The subject the event was scored on.",
                        },
                        "arena": {
                            "column_name": "arena",
                            "description": "The EthoVision arena in which the event was scored.",
                        },
                    },
                }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        if not self._scoring_occurrences:
            return {}

        current_onsets = self.alignment[self._event_onsets_alignment_key].get_times() - self.alignment.offset
        current_offsets = self.alignment[self._event_offsets_alignment_key].get_times() - self.alignment.offset
        grouped_indices: dict[str, list[int]] = {}
        for index, (_, event) in enumerate(self._scoring_occurrences):
            event_kind = "point" if event.duration is None else "state"
            grouped_indices.setdefault(f"{event_kind}:{event.behavior}", []).append(index)

        events_data_dict = {}
        for source_id, indices in grouped_indices.items():
            is_point = source_id.startswith("point:")
            durations = None if is_point else current_offsets[indices] - current_onsets[indices]
            events_data_dict[source_id] = _EventsData(
                event_type_source_id=source_id,
                timestamps=current_onsets[indices],
                durations=durations,
                payload={
                    "subject": np.asarray(
                        [self._scoring_occurrences[index][1].subject for index in indices], dtype=object
                    ),
                    "arena": np.asarray([self._scoring_occurrences[index][0] for index in indices], dtype=object),
                },
            )
        return events_data_dict

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None) -> None:
        """Write one track and its subject-specific manual-scoring events."""
        resolved_metadata = DeepDict(self.get_metadata())
        if metadata is not None:
            resolved_metadata.deep_update(metadata)
        processing_module = get_module(nwbfile=nwbfile, name="behavior", description="Processed behavioral data.")

        timestamps = self.alignment[self.metadata_key].get_times()
        rate = calculate_regular_series_rate(series=timestamps)
        time_kwargs = dict(rate=rate, starting_time=timestamps[0]) if rate else dict(timestamps=timestamps)

        position_metadata = dict(resolved_metadata["SpatialSeries"][self.metadata_key])
        position_data = np.column_stack([self._track.channels[X_COLUMN], self._track.channels[Y_COLUMN]])
        spatial_series = SpatialSeries(
            data=position_data,
            unit=position_metadata.pop("unit"),
            reference_frame=position_metadata.pop("reference_frame"),
            description=position_metadata.pop("description", ""),
            **time_kwargs,
            **position_metadata,
        )
        processing_module.add(spatial_series)

        for source_channel_name, time_series_metadata_key in self._time_series_metadata_keys.items():
            series_metadata = resolved_metadata["TimeSeries"][time_series_metadata_key]
            time_series = TimeSeries(
                data=self._track.channels[source_channel_name],
                **series_metadata,
                **time_kwargs,
            )
            processing_module.add(time_series)

        if self._scoring_occurrences:
            super().add_to_nwbfile(nwbfile=nwbfile, metadata=resolved_metadata)
            self._add_ethogram_to_nwbfile(nwbfile=nwbfile, metadata=resolved_metadata)

    def _add_ethogram_to_nwbfile(self, *, nwbfile: NWBFile, metadata: dict) -> None:
        # TODO: Unify Ethogram/EthogramBouts construction with BORIS and the VAME/MoSeq label-based
        # helper once the shared API accepts already formed intervals, catalogue rows, and extra columns.
        from ndx_ethogram import Ethogram, EthogramBouts

        ethogram_metadata = metadata["Behavior"]["Ethograms"][self._manual_scoring_metadata_key]
        processing_module = get_module(nwbfile=nwbfile, name="behavior", description="Processed behavioral data.")
        catalogue_name = ethogram_metadata["Ethogram"]["name"]
        catalogue = processing_module.data_interfaces.get(catalogue_name)
        if catalogue is None:
            catalogue = Ethogram(**ethogram_metadata["Ethogram"], exclusive=False)
            processing_module.add(catalogue)
        elif not isinstance(catalogue, Ethogram):
            raise TypeError(f"Behavior object '{catalogue_name}' exists but is not an Ethogram.")

        behavior_types = {}
        for _, event in self._scoring_occurrences:
            behavior_type = "point" if event.duration is None else "state"
            previous = behavior_types.setdefault(event.behavior, behavior_type)
            if previous != behavior_type:
                raise ValueError(f"EthoVision behavior '{event.behavior}' appears as both a point and state behavior.")
        existing_behaviors = {row["behavior"]: row["behavior_type"] for _, row in catalogue.to_dataframe().iterrows()}
        for behavior, behavior_type in behavior_types.items():
            if behavior in existing_behaviors:
                if existing_behaviors[behavior] != behavior_type:
                    raise ValueError(
                        f"EthoVision behavior '{behavior}' is already catalogued as "
                        f"'{existing_behaviors[behavior]}', not '{behavior_type}'."
                    )
                continue
            catalogue.add_row(behavior=behavior, definition="", behavior_type=behavior_type, category="")

        current_onsets = self.alignment[self._event_onsets_alignment_key].get_times()
        current_offsets = self.alignment[self._event_offsets_alignment_key].get_times()
        closed_indices = [
            index
            for index, (_, event) in enumerate(self._scoring_occurrences)
            if event.duration is not None and not np.isnan(event.duration)
        ]
        if not closed_indices:
            return

        bouts_name = ethogram_metadata["EthogramBouts"]["name"]
        bouts = processing_module.data_interfaces.get(bouts_name)
        if bouts is None:
            bouts = EthogramBouts(
                **ethogram_metadata["EthogramBouts"],
                labeling_method="manual",
                source_software="Noldus EthoVision XT",
                ethogram=catalogue,
            )
            bouts.add_column(name="subject", description="The subject the bout was scored on.")
            bouts.add_column(name="arena", description="The EthoVision arena in which the bout was scored.")
            processing_module.add(bouts)
        elif not isinstance(bouts, EthogramBouts):
            raise TypeError(f"Behavior object '{bouts_name}' exists but is not an EthogramBouts table.")
        for index in closed_indices:
            arena, event = self._scoring_occurrences[index]
            bouts.add_interval(
                start_time=current_onsets[index],
                stop_time=current_offsets[index],
                label=event.behavior,
                subject=event.subject,
                arena=arena,
            )


def _parse_start_time(*, start_time: str) -> datetime:
    """Parse EthoVision timestamps, whose fractional separator can be a period or comma."""
    return datetime.strptime(start_time.replace(",", "."), "%m/%d/%Y %H:%M:%S.%f")
