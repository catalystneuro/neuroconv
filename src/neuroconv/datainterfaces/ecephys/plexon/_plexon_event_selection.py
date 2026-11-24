"""Native event names and captured-word selection shared by the Plexon readers."""

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from functools import cache
from typing import Annotated, Literal, TypeVar

from pydantic import ConfigDict, Field, StrictInt, StrictStr
from typing_extensions import NotRequired, TypedDict

from ...events.baseeventsinterface import _EventsData

_STROBED_WORD = "strobed_word"


class _Separation(TypedDict):
    __pydantic_config__ = ConfigDict(extra="forbid")

    by_payload_fields: Annotated[list[Literal["strobed_word"]], Field(min_length=1, max_length=1)]
    select: NotRequired[list[StrictInt | None]]


class _ExtractionEntry(TypedDict):
    __pydantic_config__ = ConfigDict(extra="forbid")

    source: NotRequired[StrictStr]
    separation: NotRequired[_Separation]


_Channel = TypeVar("_Channel", int, tuple)


def _get_native_source_names(
    names_by_channel: dict[_Channel, str], fallback_by_channel: dict[_Channel, str]
) -> dict[str, _Channel]:
    counts = Counter(names_by_channel.values())
    reserved = {name for name, count in counts.items() if name.strip() and count == 1}
    sources = {}
    for channel, name in names_by_channel.items():
        if name in reserved:
            sources[name] = channel
            continue
        fallback = fallback_by_channel[channel]
        source = f"{name}_{fallback}" if name.strip() else fallback
        while source in reserved or source in sources:
            source = f"{source}_{fallback}"
        sources[source] = channel
    return sources


def _select_plexon_events(
    populated_sources: Iterable[str],
    resolved_configuration: dict[str, _ExtractionEntry] | None,
    read_source: Callable[[str], _EventsData],
) -> dict[str, _EventsData]:
    if resolved_configuration is None:
        return {source: read_source(source) for source in populated_sources}

    read_source = cache(read_source)
    events = {}
    entry_names = {}
    for entry_name, entry in resolved_configuration.items():
        native_events = read_source(entry["source"])
        separation = entry.get("separation")
        if separation is None:
            groups = {entry_name: slice(None)}
        else:
            words = native_events.payload[_STROBED_WORD]
            selected = separation.get("select")
            indices_by_word = defaultdict(list) if selected is None else {word: [] for word in selected}
            for index, word in enumerate(words):
                if selected is None or word in indices_by_word:
                    indices_by_word[word].append(index)
            groups = {
                f"{entry_name}_{'missing' if word is None else word}": indices
                for word, indices in indices_by_word.items()
            }

        for source_id, indices in groups.items():
            if source_id in events:
                raise ValueError(
                    f"Extraction entries {entry_names[source_id]!r} and {entry_name!r} both produce "
                    f"event type {source_id!r}. Rename one of the entries to give each type a distinct identifier."
                )
            events[source_id] = _EventsData(
                event_type_source_id=source_id,
                timestamps=native_events.timestamps[indices],
                payload={field: values[indices] for field, values in native_events.payload.items()},
            )
            entry_names[source_id] = entry_name
    return events
