import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from ._ethovision_reader import get_available_scorings, parse_start_time, select_scoring
from ...events.baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools import get_module
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
        self._event_onsets_alignment_key = f"{self.metadata_key}_manual_scoring_onsets"
        self._event_offsets_alignment_key = f"{self.metadata_key}_manual_scoring_offsets"
        self.alignment._register_series(
            key=self._event_onsets_alignment_key,
            get_native_times=lambda: np.asarray([event.onset for event in self._scoring_events], dtype=float),
        )
        self.alignment._register_series(
            key=self._event_offsets_alignment_key,
            get_native_times=self._get_native_event_offsets,
        )

    def _get_native_event_offsets(self) -> np.ndarray:
        return np.asarray(
            [
                event.onset + event.duration if event.duration is not None and not np.isnan(event.duration) else np.nan
                for event in self._scoring_events
            ],
            dtype=float,
        )

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
        current_onsets = self.alignment[self._event_onsets_alignment_key].get_times() - self.alignment.offset
        current_offsets = self.alignment[self._event_offsets_alignment_key].get_times() - self.alignment.offset
        grouped_indices: dict[str, list[int]] = {}
        for index, event in enumerate(self._scoring_events):
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
                    "subject": np.asarray([self._scoring_events[index].subject for index in indices], dtype=object),
                    "arena": np.asarray([self._arena] * len(indices), dtype=object),
                },
            )
        return events_data_dict

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None) -> None:
        """Write one subject's Manual Scoring events, Ethogram and closed state bouts."""
        resolved_metadata = DeepDict(self.get_metadata())
        if metadata is not None:
            resolved_metadata.deep_update(metadata)
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
        for event in self._scoring_events:
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
            for index, event in enumerate(self._scoring_events)
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
            event = self._scoring_events[index]
            bouts.add_interval(
                start_time=current_onsets[index],
                stop_time=current_offsets[index],
                label=event.behavior,
                subject=event.subject,
                arena=self._arena,
            )
