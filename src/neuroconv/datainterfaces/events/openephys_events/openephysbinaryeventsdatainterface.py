"""Interface for the discrete events written by the Open Ephys GUI's binary format."""

import json
import re
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
from pydantic import DirectoryPath, validate_call

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools.events import _detect_on_line_changes, _separate_events
from ....utils import DeepDict


class OpenEphysBinaryEventsInterface(BaseEventsInterface):
    """Data interface for the discrete events of an Open Ephys binary recording.

    A Record Node writes one event record the moment a digital line changes state, into
    ``events/<stream>/TTL/`` as parallel ``.npy`` arrays: ``states.npy`` (the line number as the
    magnitude and the edge direction as the sign), ``timestamps.npy``, and ``full_words.npy`` (the
    state of the first 64 lines latched at that moment). Text annotations live beside them in a
    ``MessageCenter`` folder.

    By default a digital input stream becomes one ``pynwb.event.EventsTable`` in ``nwbfile.events``.
    Each row keeps the recorded signed ``open_ephys_state``, its ``line`` counted from 0 and ``onset``, and
    the recorded ``full_word`` when the recording supplies it. ``event_extraction_configuration`` can keep
    the edges of one line, pair them into pulses, or split them by payload.

    One interface reads one event stream of one experiment. Streams are named as SpikeInterface names
    the recording streams (``Record Node 104#NI-DAQmx-103.PXIe-6341``), so the events of a recording
    stream are addressed by the name that stream already has, and the recordings inside an experiment
    are read together because they share its clock. The session start time comes from the settings file
    the GUI wrote for that experiment, so an events-only conversion carries the same start time the
    recording interface would give it.
    """

    display_name = "OpenEphys Binary Events"
    keywords = ("events", "TTL", "OpenEphys")
    associated_suffixes = (".npy", ".oebin")
    info = "Interface for converting discrete events from OpenEphys binary recordings."

    @classmethod
    def get_stream_names(cls, folder_path: DirectoryPath, *, block_index: int | None = None) -> list[str]:
        """
        Get the names of the event streams available in an Open Ephys binary folder.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to a directory containing Open Ephys binary data.
        block_index : int, optional
            The index of the experiment to read, when the folder holds more than one.

        Returns
        -------
        list of str
            The names of the available event streams.
        """
        experiments = _discover_event_streams(folder_path=Path(folder_path))
        experiment_name = _select_experiment(experiments=experiments, block_index=block_index)
        return sorted(experiments[experiment_name])

    @classmethod
    def get_available_event_sources(
        cls, folder_path: DirectoryPath, *, stream_name: str | None = None, block_index: int | None = None
    ) -> list[str]:
        """
        Get the event source of an Open Ephys binary event stream, which is the stream itself.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to a directory containing Open Ephys binary data.
        stream_name : str, optional
            The name of the event stream; only required if the experiment has more than one.
        block_index : int, optional
            The index of the experiment to read, when the folder holds more than one.

        Returns
        -------
        list of str
            The name of the selected stream, the one source the entries of ``event_extraction_configuration``
            read.
        """
        experiments = _discover_event_streams(folder_path=Path(folder_path))
        experiment_name = _select_experiment(experiments=experiments, block_index=block_index)
        return [
            _select_stream(
                streams=experiments[experiment_name], stream_name=stream_name, experiment_name=experiment_name
            )
        ]

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        stream_name: str | None = None,
        block_index: int | None = None,
        event_extraction_configuration: dict | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize reading of the events of an Open Ephys binary recording.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to a directory containing Open Ephys binary data.
        stream_name : str, optional
            The name of the event stream to read; only required if the experiment has more than one.
            Call ``OpenEphysBinaryEventsInterface.get_stream_names(folder_path=...)`` to see what
            streams are available.
        block_index : int, optional
            The index of the experiment to read, following the order of the ``experiment<index>``
            folders; only required if the folder holds more than one experiment.
        event_extraction_configuration : dict, optional
            The event types to write, keyed by output name, each reading the stream as its source. On a digital
            input stream, ``detection`` with ``lines`` and ``on_change`` keeps the edges of one line in one
            direction, or with an ``end`` pairs them into pulses, and ``separation`` splits the edges by a
            payload field such as ``line``. If None (default), the stream is one table with a row per recorded
            edge or message.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata.
            If None (default), ``"open_ephys_events"`` is used.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        experiments = _discover_event_streams(folder_path=Path(folder_path))
        experiment_name = _select_experiment(experiments=experiments, block_index=block_index)
        streams = experiments[experiment_name]
        stream_name = _select_stream(streams=streams, stream_name=stream_name, experiment_name=experiment_name)

        self.metadata_key = metadata_key or "open_ephys_events"
        # The recordings of the selected experiment, in order. They share the experiment's clock, so their
        # arrays are concatenated rather than treated as separate sources.
        self._stream_sources = streams[stream_name]

        is_text = self._stream_sources[0]["kind"] == "text"
        available_sources = {
            stream_name: {"supported_operations": ["separation"] if is_text else ["detection", "separation"]}
        }
        resolved_configuration = self._resolve_event_sources(event_extraction_configuration, available_sources)
        if resolved_configuration is None:
            # One event type for the whole stream, with every recorded edge or message as an occurrence.
            default_name = "messages" if is_text else re.sub(r"[^a-zA-Z0-9]+", "_", stream_name).strip("_")
            resolved_configuration = {default_name: {"source": stream_name}}
        self._event_extraction_configuration = resolved_configuration

        # Last, because the base registers the event types with `temporal_alignment`, which reads the stream sources
        super().__init__(
            folder_path=folder_path,
            stream_name=stream_name,
            block_index=block_index,
            event_extraction_configuration=event_extraction_configuration,
            verbose=verbose,
        )

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the OpenEphysBinaryEventsInterface.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        session_start_time = _read_session_start_time(recording_folder=self._stream_sources[0]["recording_folder"])
        if session_start_time is not None:
            metadata["NWBFile"].update(session_start_time=session_start_time)

        for event_type_source_id, event in self._get_events_data_dict().items():
            # The columns are seeded from what the payload carries. What the file states about itself is
            # stated here (the sign of a state is the edge direction, a full word is the latched port);
            # what only the experimenter knows (which wire is the reward line) is left for the metadata.
            columns = {}
            if "open_ephys_state" in event.payload:
                columns["open_ephys_state"] = {
                    "column_name": "open_ephys_state",
                    "description": "The signed state stored in the recording: the line plus one, negative for a fall.",
                }
                columns["line"] = {
                    "column_name": "line",
                    "description": "The line that changed, counted from 0.",
                }
                columns["onset"] = {
                    "column_name": "onset",
                    "description": "The direction of the recorded change.",
                    "column_categories": {"labels": {"rising": "rising", "falling": "falling"}},
                }
            if "full_word" in event.payload:
                columns["full_word"] = {
                    "column_name": "full_word",
                    "description": "The state of the first 64 TTL lines at the moment of this event.",
                }
            if "full_word_at_onset" in event.payload:
                columns["full_word_at_onset"] = {
                    "column_name": "full_word_at_onset",
                    "description": "The state of the first 64 TTL lines at the onset of this event.",
                }
            if "full_word_pattern" in event.payload:
                columns["full_word_pattern"] = {
                    "column_name": "full_word_pattern",
                    "description": "The recorded port states in binary, highest line first.",
                }
            if "text" in event.payload:
                columns["text"] = {"column_name": "text", "description": "The text of this message."}
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = {
                "event_name": event_type_source_id,
                "columns": columns,
            }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation from the stream's ``.npy`` arrays, cached after the first call.

        Each entry of the configuration reads every record of the stream. An entry with ``detection`` keeps the
        edges of its line, or pairs them into pulses, and ``separation`` then splits an entry by payload.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        timestamps = np.concatenate([_read_timestamps(source=source) for source in self._stream_sources])
        if self._stream_sources[0]["kind"] == "text":
            text = np.concatenate(
                [np.char.decode(np.load(source["path"] / "text.npy")) for source in self._stream_sources]
            )
            payload = {"text": text}
        else:
            states = np.concatenate([_read_states(path=source["path"]) for source in self._stream_sources])
            full_words = [_read_full_words(path=source["path"]) for source in self._stream_sources]

            # A state stores line k as k + 1, so that line 0 can carry the sign of the direction.
            payload = {
                "open_ephys_state": states,
                "line": np.abs(states) - 1,
                "onset": np.where(states > 0, "rising", "falling"),
            }
            if all(word is not None for word in full_words):
                payload["full_word"] = np.concatenate(full_words)
                widths = {source["num_channels"] for source in self._stream_sources}
                if len(widths) == 1:
                    width = next(iter(widths))
                    if width and width <= 64 and np.all(payload["full_word"] < 1 << width):
                        payload["full_word_pattern"] = np.asarray(
                            [format(int(word), f"0{width}b") for word in payload["full_word"]], dtype=str
                        )

        events_by_entry = {}
        for entry_name, entry in self._event_extraction_configuration.items():
            records = _EventsData(event_type_source_id=entry_name, timestamps=timestamps, payload=payload)
            if "detection" in entry:
                onset_indices, end_indices = _detect_on_line_changes(entry=entry, edges=records)
                durations = None
                detected_payload = {}
                if end_indices is None:
                    if "full_word" in payload:
                        detected_payload["full_word"] = payload["full_word"][onset_indices]
                else:
                    durations = np.full(len(onset_indices), np.nan)
                    closed = end_indices >= 0
                    durations[closed] = timestamps[end_indices[closed]] - timestamps[onset_indices[closed]]
                    if "full_word" in payload:
                        detected_payload["full_word_at_onset"] = payload["full_word"][onset_indices]
                records = _EventsData(
                    event_type_source_id=entry_name,
                    timestamps=timestamps[onset_indices],
                    durations=durations,
                    payload=detected_payload,
                )
            events_by_entry[entry_name] = records

        self._events_data_dict = _separate_events(self._event_extraction_configuration, events_by_entry)
        return self._events_data_dict


def _discover_event_streams(folder_path: Path) -> dict[str, dict[str, list[dict]]]:
    """Map each experiment to its event streams, and each stream to its per-recording sources.

    Walks to every ``structure.oebin`` under ``folder_path`` (one per recording) and takes its
    ``events`` list as the catalogue of that recording's event streams. A stream the catalogue lists
    but the Record Node never wrote is skipped, since the folder is simply absent on disk.
    """
    # Sorted so that the recordings of an experiment are concatenated in the order they were recorded,
    # which is their index order rather than their lexicographic one (recording10 follows recording9).
    recording_folders = sorted(
        (path.parent for path in folder_path.rglob("structure.oebin")),
        key=lambda folder: (
            str(folder.parent.parent),
            _folder_sort_key(folder.parent.name),
            _folder_sort_key(folder.name),
        ),
    )
    if not recording_folders:
        raise ValueError(
            f"No Open Ephys binary recording was found in '{folder_path}'. Please check that the folder "
            "contains sub-folders of the following form: 'experiment<index>' -> 'recording<index>', each "
            "holding a 'structure.oebin' file."
        )

    experiments = {}
    for recording_folder in recording_folders:
        experiment_name = recording_folder.parent.name
        record_node_name = _get_record_node_name(recording_folder=recording_folder)
        structure = json.loads((recording_folder / "structure.oebin").read_text(encoding="utf-8"))
        for entry in structure.get("events", []):
            folder_name = entry["folder_name"].rstrip("/")
            path = recording_folder / "events" / folder_name
            if not path.is_dir():
                continue
            kind = _get_stream_kind(path=path)
            if kind is None:
                continue  # a tracking (BINARY) stream, whose structured payload this reader does not read
            stream_name = _get_stream_name(folder_name=folder_name, record_node_name=record_node_name)
            sources = experiments.setdefault(experiment_name, {}).setdefault(stream_name, [])
            sources.append(
                dict(
                    path=path,
                    recording_folder=recording_folder,
                    sample_rate=entry["sample_rate"],
                    kind=kind,
                    num_channels=entry.get("num_channels"),
                )
            )
    return experiments


def _select_experiment(experiments: dict[str, dict], block_index: int | None) -> str:
    """Return the name of the experiment ``block_index`` selects, in ``experiment<index>`` order."""
    experiment_names = sorted(experiments, key=_folder_sort_key)
    if not experiment_names:
        raise ValueError("No event streams were found: this recording holds no events folder to read.")

    if block_index is None:
        if len(experiment_names) > 1:
            raise ValueError(
                "More than one experiment is detected! Please specify which one you wish to read with the "
                f"`block_index` argument, indexing {experiment_names} in that order."
            )
        return experiment_names[0]

    if not 0 <= block_index < len(experiment_names):
        raise ValueError(
            f"The selected block_index {block_index} is out of range for the {len(experiment_names)} "
            f"experiments found: {experiment_names}."
        )
    return experiment_names[block_index]


def _select_stream(streams: dict[str, list[dict]], stream_name: str | None, experiment_name: str) -> str:
    """Return the name of the stream to read, which ``stream_name`` names when the experiment has several."""
    available_streams = sorted(streams)
    if stream_name is None:
        if len(available_streams) > 1:
            raise ValueError(
                f"More than one event stream is detected in '{experiment_name}'! Please specify which "
                "stream you wish to read with the `stream_name` argument. To see what streams are "
                "available, call `OpenEphysBinaryEventsInterface.get_stream_names(folder_path=...)`. "
                f"The available streams are {available_streams}."
            )
        return available_streams[0]
    if stream_name not in available_streams:
        raise ValueError(f"The selected stream '{stream_name}' is not in the available streams {available_streams}!")
    return stream_name


def _folder_sort_key(folder_name: str) -> tuple[int, str]:
    """Order the ``experiment<index>`` and ``recording<index>`` folders by their index, so 10 follows 9."""
    match = re.search(r"(\d+)$", folder_name)
    return (int(match.group()) if match else 0, folder_name)


def _get_record_node_name(recording_folder: Path) -> str | None:
    """Return the name of the Record Node folder holding this recording, when the layout has one.

    A Record Node folder is the grandparent of a recording folder
    (``Record Node 104/experiment1/recording1``); the format wrote no such folder before the GUI
    supported several nodes, and there the grandparent is just the session folder. The GUI has
    spelled the folder ``Record Node 104``, ``RecordNode103`` and ``Record_Node_107`` across
    versions, so the comparison ignores what separates the two words.
    """
    candidate = recording_folder.parent.parent
    is_record_node = candidate.name.lower().replace(" ", "").replace("_", "").startswith("recordnode")
    return candidate.name if is_record_node else None


def _get_stream_name(*, folder_name: str, record_node_name: str | None) -> str:
    """Name an event stream after the folder that holds it, prefixed by its Record Node.

    The ``TTL`` leaf that v0.6 and later write is dropped, which leaves the stream's own name
    (``NI-DAQmx-103.PXIe-6341``), the one SpikeInterface gives the matching recording stream. Older
    versions number their event groups instead (``Rhythm_FPGA-100.0/TTL_1``), and there the leaf is
    what tells one group of a processor from another, so it is kept.
    """
    stream_name = folder_name[: -len("/TTL")] if folder_name.endswith("/TTL") else folder_name
    return f"{record_node_name}#{stream_name}" if record_node_name is not None else stream_name


def _get_stream_kind(path: Path) -> str | None:
    """Classify an event stream by the arrays it holds, or return None for one this reader does not read."""
    if (path / "states.npy").exists() or (path / "channel_states.npy").exists():
        return "ttl"
    if (path / "text.npy").exists():
        return "text"
    return None


def _read_timestamps(source: dict) -> np.ndarray:
    """Read one source's event times, in seconds.

    From v0.6 on, ``timestamps.npy`` holds seconds and the sample count moved to ``sample_numbers.npy``;
    before that there was no ``sample_numbers.npy`` and ``timestamps.npy`` held the sample count itself,
    which the stream's sampling rate turns into seconds.
    """
    path = source["path"]
    timestamps = np.load(path / "timestamps.npy")
    if (path / "sample_numbers.npy").exists():
        return timestamps.astype(float)
    return timestamps / source["sample_rate"]


def _read_session_start_time(recording_folder: Path) -> datetime | None:
    """Read the start time of this recording's experiment from the Record Node's settings file.

    The GUI writes one settings file per experiment, next to the ``experiment<index>`` folders, named
    ``settings.xml`` for the first and ``settings_<index>.xml`` for the rest, so the file is the one
    naming the selected experiment rather than whichever the folder happens to hold. It is parsed with
    the standard library instead of ``neuroconv.datainterfaces.ecephys.openephys._openephys_utils``'s
    reader, which searches the whole tree (there is more than one file to find here) and needs ``lxml``,
    a dependency the events of a recording do not otherwise carry. Returns None when no settings file
    was written, which happens.
    """
    experiment_index = _folder_sort_key(recording_folder.parent.name)[0]
    settings_name = "settings.xml" if experiment_index <= 1 else f"settings_{experiment_index}.xml"
    settings_path = recording_folder.parent.parent / settings_name
    if not settings_path.is_file():
        return None

    from ...ecephys.openephys._openephys_utils import _get_session_start_time

    return _get_session_start_time(element=ElementTree.parse(settings_path).getroot())


def _read_states(path: Path) -> np.ndarray:
    """Read one source's signed line states (``channel_states.npy`` before v0.6, ``states.npy`` after)."""
    states_path = path / "states.npy"
    if not states_path.exists():
        states_path = path / "channel_states.npy"
    return np.load(states_path)


def _read_full_words(path: Path) -> np.ndarray | None:
    """Read one source's latched TTL words, or None when the stream carries none."""
    full_words_path = path / "full_words.npy"
    return np.load(full_words_path) if full_words_path.exists() else None
