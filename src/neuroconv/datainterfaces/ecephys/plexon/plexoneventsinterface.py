from pydantic import FilePath, StrictStr, validate_call

from ._plexon_event_selection import _STROBED_WORD, _ExtractionEntry, _select_plexon_events
from ._plx_events_reader import _DEFERRED_CHANNELS, _STROBED_CHANNELS, _read_plx_event_sources, _read_plx_events
from ...events.baseeventsinterface import BaseEventsInterface, _EventsData
from ....utils import DeepDict, to_snake_case


class PlexonEventsInterface(BaseEventsInterface):
    """Convert individual-input events and strobed words from a Plexon PLX recording.

    Each populated event channel becomes one table by default. Individual inputs supply
    timestamps. Strobed channels also supply the complete unsigned word in ``strobed_word``.
    """

    display_name = "Plexon Events"
    _supports_event_extraction_configuration = True
    keywords = ("events", "Plexon")
    associated_suffixes = (".plx",)
    info = "Interface for converting discrete events from Plexon PLX files."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        event_extraction_configuration: dict[StrictStr, _ExtractionEntry] | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the PlexonEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the Plexon PLX file.
        event_extraction_configuration : dict, optional
            Entries keyed by the desired event type identifier. Each entry names a native channel
            with ``source``, which can be omitted if the file declares just one channel. For a strobed channel, add
            ``separation={"by_payload_fields": ["strobed_word"]}`` to create one type per distinct word.
            Add ``select`` to that block to request particular integer words, including words with
            no matches. A supported source explicitly requested with no occurrences yields an empty
            table. By default, convert all populated experimental event channels.
        metadata_key : str, optional
            Namespace under ``metadata["Events"]``. Defaults to the file stem in snake_case.
        verbose : bool, default: False
            Whether to print status messages.
        """
        self.metadata_key = metadata_key or to_snake_case(file_path.stem)
        super().__init__(
            file_path=file_path,
            event_extraction_configuration=event_extraction_configuration,
            metadata_key=metadata_key,
            verbose=verbose,
        )

    @classmethod
    @validate_call
    def get_available_event_sources(cls, file_path: FilePath) -> list[str]:
        """List the event channel names in header order.

        Parameters
        ----------
        file_path : FilePath
            Path to the Plexon PLX file.

        Returns
        -------
        list of str
            Recorded channel names or their numerical fallbacks. Includes
            channels without occurrences as well as deferred keyboard and recording-control channels.
        """
        return list(_read_plx_event_sources(file_path))

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        if self._events_data_dict is not None:
            return self._events_data_dict

        sources, native_events, self._session_start_time = _read_plx_events(self.source_data["file_path"])
        configuration = self._resolve_event_sources(
            self.source_data["event_extraction_configuration"], _describe_sources(sources)
        )

        def read_source(source: str) -> _EventsData:
            timestamps, words = native_events[source]
            payload = {} if words is None else {_STROBED_WORD: words}
            return _EventsData(event_type_source_id=source, timestamps=timestamps, payload=payload)

        populated_sources = (source for source, (timestamps, _) in native_events.items() if timestamps.size)
        self._events_data_dict = _select_plexon_events(populated_sources, configuration, read_source)
        return self._events_data_dict

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        if self._session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = self._session_start_time
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        for source_id, event in self._get_events_data_dict().items():
            entry = {"event_name": source_id}
            if event.payload:
                entry["columns"] = {_STROBED_WORD: {"column_name": _STROBED_WORD}}
            event_types[source_id] = entry
        return metadata


def _describe_sources(sources: dict[str, int]) -> dict[str, dict]:
    descriptors = {}
    for source, channel in sources.items():
        descriptor = {
            "supported_operations": ["separation"] if channel in _STROBED_CHANNELS else [],
        }
        if channel in _DEFERRED_CHANNELS:
            descriptor["unsupported_reason"] = "Keyboard and recording-control events are not supported."
        descriptors[source] = descriptor
    return descriptors
