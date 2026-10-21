import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from ._ethovision_reader import get_available_scorings, parse_start_time, select_scoring
from ...events.baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools import get_module
from ....tools.behavior import _add_ethogram_to_nwbfile
from ....utils import DeepDict, to_camel_case, to_snake_case


class EthoVisionManualScoringInterface(BaseEventsInterface):
    """Interface for one subject's Manual Scoring in a Noldus EthoVision XT Excel export.

    EthoVision writes an arena's Manual Scoring to its own ``Manual Scoring-<arena>`` sheet, with or
    without the Track sheets beside it. The sheet holds the rows of every subject scored in that arena;
    ``arena_name`` and ``subject_name`` select one subject, and only that subject's rows are retained.
    Use :class:`~neuroconv.datainterfaces.behavior.ethovision.ethovisiontrackinterface.EthoVisionTrackInterface`
    for the Tracks.

    Times come from the ``Trial time`` column, which counts from the start of the run, so they match the
    ``Start time`` of the sheet's header written to ``session_start_time`` and the Track timestamps.

    The selected rows are mapped to NWB as follows:

    * Every row -> one :class:`~pynwb.event.EventsTable`, pairing ``state start`` and ``state stop`` into
      one row with a duration. A state bout that never closes keeps a ``NaN`` duration.
    * The scored behavior labels -> one ``ndx-ethogram`` ``Ethogram``.
    * The closed state bouts -> one ``EthogramBouts`` table.

    The ``Ethogram`` and ``EthogramBouts`` are written to the ``behavior`` processing module.
    """

    display_name = "EthoVision Manual Scoring"
    keywords = ("EthoVision", "Noldus", "behavior", "events", "ethogram")
    associated_suffixes = (".xlsx",)
    info = "Interface for Noldus EthoVision XT Manual Scoring exports."

    @staticmethod
    def get_available_scorings(file_path: FilePath) -> list[dict[str, str]]:
        """Return the complete selector arguments for every arena and subject with Manual Scoring rows.

        The arena comes from each Manual Scoring sheet's ``Arena name`` header field and the subjects from
        its ``Subject`` column, so a sheet without rows lists nothing. Text exports raise, as in ``__init__``.
        """
        return get_available_scorings(file_path=file_path)

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
        """Initialize an interface for one subject's EthoVision Manual Scoring.

        Parameters
        ----------
        file_path : FilePath
            Path to an EthoVision ``.xlsx`` workbook holding a Manual Scoring sheet. Text Manual Scoring
            logs are not supported yet.
        arena_name : str, optional
            Arena to select. Inferred when the workbook scores only one arena.
        subject_name : str, optional
            Subject to select, matching the sheet's ``Subject`` column. Inferred when the selected arena
            scores only one subject.
        metadata_key : str, optional
            The key for this subject's events block. By default it is derived from the arena and subject
            so several interfaces can share an NWB file.
        verbose : bool, default: False
            Whether to print progress.
        """
        self._scoring_sheet, self._subject = select_scoring(
            file_path=file_path,
            arena_name=arena_name,
            subject_name=subject_name,
        )
        self._arena = self._scoring_sheet.arena
        self.metadata_key = metadata_key or f"ethovision_{to_snake_case(f'{self._arena}_{self._subject}')}"
        self._manual_scoring_metadata_key = f"ethovision_{to_snake_case(self._arena)}_manual_scoring"
        super().__init__(
            file_path=file_path,
            arena_name=self._arena,
            subject_name=self._subject,
            metadata_key=self.metadata_key,
            verbose=verbose,
        )

        self._scoring_events = [event for event in self._scoring_sheet.events if event.subject == self._subject]

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
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
        start_time = self._scoring_sheet.header.get("Start time")
        if start_time:
            metadata["NWBFile"]["session_start_time"] = parse_start_time(start_time=start_time)

        arena_suffix = to_camel_case(to_snake_case(self._arena))
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
        for source_id in self._get_events_data_dict():
            event_types[source_id] = {
                "event_name": source_id,
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
        if self._events_data_dict is not None:
            return self._events_data_dict

        events_by_behavior: dict[str, list] = {}
        for event in self._scoring_events:
            events_by_behavior.setdefault(event.behavior, []).append(event)

        events_data_dict = {}
        for behavior, events in events_by_behavior.items():
            is_point = [event.duration is None for event in events]
            if any(is_point) and not all(is_point):
                raise ValueError(f"EthoVision behavior '{behavior}' appears as both a point and state behavior.")
            events_data_dict[behavior] = _EventsData(
                event_type_source_id=behavior,
                timestamps=np.asarray([event.onset for event in events], dtype=float),
                durations=None if all(is_point) else np.asarray([event.duration for event in events], dtype=float),
                payload={
                    "subject": np.asarray([event.subject for event in events], dtype=object),
                    "arena": np.asarray([self._arena] * len(events), dtype=object),
                },
            )
        self._events_data_dict = events_data_dict
        return self._events_data_dict

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None) -> None:
        """Write one subject's Manual Scoring events, Ethogram and closed state bouts."""
        resolved_metadata = DeepDict(self.get_metadata())
        if metadata is not None:
            resolved_metadata.deep_update(metadata)
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=resolved_metadata)
        self._add_ethogram_to_nwbfile(nwbfile=nwbfile, metadata=resolved_metadata)

    def _add_ethogram_to_nwbfile(self, *, nwbfile: NWBFile, metadata: dict) -> None:
        ethogram_metadata = metadata["Behavior"]["Ethograms"][self._manual_scoring_metadata_key]
        # Created here if missing, so the module the ethogram writer adds to carries this description.
        get_module(nwbfile=nwbfile, name="behavior", description="Processed behavioral data.")

        events_data_dict = self._get_events_data_dict()
        behavior_types = {
            behavior: "point" if events_data.durations is None else "state"
            for behavior, events_data in events_data_dict.items()
        }

        # A bout follows its event as aligned, ending its aligned duration after its aligned onset, and the bouts
        # keep the order the events were scored in. An event's row in its behavior's arrays is its position among
        # the events scored against that behavior.
        aligned_times = {behavior: self.get_event_times(behavior) for behavior in events_data_dict}
        aligned_durations = {behavior: self._get_event_durations(behavior) for behavior in events_data_dict}
        closed_bouts = []
        rows_seen = {}
        for event in self._scoring_events:
            row = rows_seen.get(event.behavior, 0)
            rows_seen[event.behavior] = row + 1
            if event.duration is not None and not np.isnan(event.duration):
                closed_bouts.append((event, row))
        start_times = [aligned_times[event.behavior][row] for event, row in closed_bouts]
        stop_times = [
            start_time + aligned_durations[event.behavior][row]
            for start_time, (event, row) in zip(start_times, closed_bouts)
        ]
        _add_ethogram_to_nwbfile(
            nwbfile,
            start_times=start_times,
            stop_times=stop_times,
            labels=[event.behavior for event, _ in closed_bouts],
            behaviors=[
                dict(behavior=behavior, definition="", behavior_type=behavior_type, category="")
                for behavior, behavior_type in behavior_types.items()
            ],
            ethogram_metadata=ethogram_metadata,
            labeling_method="manual",
            exclusive=False,
            source_software="Noldus EthoVision XT",
            bout_columns={
                "subject": {
                    "description": "The subject the bout was scored on.",
                    "data": [event.subject for event, _ in closed_bouts],
                },
                "arena": {
                    "description": "The EthoVision arena in which the bout was scored.",
                    "data": [self._arena] * len(closed_bouts),
                },
            },
            # Every subject scored in this arena writes into one arena-level bouts table.
            extend_bouts=True,
        )
