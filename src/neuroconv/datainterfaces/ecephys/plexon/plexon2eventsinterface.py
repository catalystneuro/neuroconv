from pydantic import FilePath, StrictStr, validate_call

from ._plexon2_events_reader import _Plexon2EventsReader
from ._plexon_event_selection import _STROBED_WORD, _ExtractionEntry, _select_plexon_events
from ...events.baseeventsinterface import BaseEventsInterface, _EventsData
from ....utils import DeepDict, to_snake_case


class Plexon2EventsInterface(BaseEventsInterface):
    """Convert Plexon PL2 individual digital inputs and strobed words to NWB."""

    _supports_event_extraction_configuration = True

    display_name = "Plexon2 Events"
    keywords = ("events", "Plexon")
    associated_suffixes = (".pl2",)
    info = "Interface for digital events recorded in Plexon PL2 files."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        event_extraction_configuration: dict[StrictStr, _ExtractionEntry] | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the Plexon PL2 file.
        event_extraction_configuration : dict, optional
            Map an event type name to an entry with a native channel name under source.
            For a strobed-word channel, separation can split by ["strobed_word"] in
            by_payload_fields. An optional integer list under select limits the resulting
            types to those words, including zero-row types for requested words with no matches.
            With no configuration, each supported channel containing occurrences is converted.
        metadata_key : str, optional
            Key for this interface's Events metadata. Defaults to the file stem in snake case.
        verbose : bool, default: False
            Whether to print status messages.
        """
        self.metadata_key = metadata_key or to_snake_case(file_path.stem)
        with file_path.open("rb") as stream:
            reader = _Plexon2EventsReader(stream)
            self._session_start_time = reader.session_start_time
            configuration = self._resolve_event_sources(event_extraction_configuration, reader.source_info)
            self._plexon_events = _select_plexon_events(
                reader.populated_sources if configuration is None else (),
                configuration,
                reader.read_source,
            )
        super().__init__(
            file_path=file_path,
            metadata_key=metadata_key,
            event_extraction_configuration=event_extraction_configuration,
            verbose=verbose,
        )

    @classmethod
    @validate_call
    def get_available_event_sources(cls, file_path: FilePath) -> dict[str, dict]:
        """List header-declared event channels, including silent and unsupported channels."""
        with file_path.open("rb") as stream:
            return _Plexon2EventsReader(stream).source_info

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        return self._plexon_events

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        if self._session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = self._session_start_time
        event_types = metadata["Events"][self.metadata_key]["event_types"] = {}
        for name, events in self._get_events_data_dict().items():
            event_types[name] = {"event_name": name}
            if _STROBED_WORD in events.payload:
                event_types[name]["columns"] = {
                    _STROBED_WORD: {
                        "column_name": _STROBED_WORD,
                        "description": "Complete unsigned 16-bit word captured by the strobed input.",
                    }
                }
        return metadata
