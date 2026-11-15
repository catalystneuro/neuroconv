"""Interface for the events of a Neuralynx event file (``.nev``)."""

import numpy as np
from pydantic import FilePath, validate_call

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ...ecephys.neuralynx._neuralynx_events_reader import read_event_file
from ....utils import DeepDict

_EVENT_TYPE_SOURCE_ID = "event_records"

_COLUMNS = {
    "event_id": {
        "column_name": "event_id",
        "description": "The event id Cheetah or Pegasus wrote for the record, naming the kind of event.",
    },
    "ttl_value": {
        "column_name": "ttl_value",
        "description": "The value of the 16-bit TTL port written with the record, one bit per line.",
    },
    "text": {
        "column_name": "text",
        "description": "The event string of the record.",
    },
}


class NeuralynxEventsInterface(BaseEventsInterface):
    """Data interface for the events of a Neuralynx event file (``.nev``).

    Every record of the file is written, in file order, as one row of a single ``pynwb.event.EventsTable`` in
    ``nwbfile.events``, with the record's ``event_id``, ``ttl_value`` and event string (``text``) as columns.

    One table holds every record because the kinds of record cannot be told apart reliably. A TTL record names its
    port only in its text, and Cheetah replaces that text with a name the user gave the TTL value (for example
    ``"stimulation"``), so a TTL record can look like a typed comment. Recording starts and stops, typed comments,
    NeuraView sleep scores and Pegasus stimulation messages share the same records.

    The times are the record timestamps, which count microseconds, in seconds.
    """

    display_name = "Neuralynx Events"
    keywords = ("events", "Neuralynx", "TTL")
    associated_suffixes = (".nev",)
    info = "Interface for converting the events of Neuralynx event files."

    @validate_call
    def __init__(self, file_path: FilePath, *, metadata_key: str | None = None, verbose: bool = False):
        """Initialize reading of the events of a Neuralynx event file.

        Parameters
        ----------
        file_path : FilePath
            Path to the Neuralynx event file (``.nev``).
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata.
            If None (default), ``"neuralynx_events"`` is used.
        verbose : bool, default: False
            Whether to output verbose text.
        """
        self.metadata_key = metadata_key or "neuralynx_events"
        self._event_file = read_event_file(file_path)
        if len(self._event_file.records) == 0:
            raise ValueError(f"'{self._event_file.file_path.name}' holds no event records.")
        super().__init__(file_path=file_path, verbose=verbose)

    def get_event_type_source_ids(self) -> list[str]:
        """The single event type of the file, which holds every record."""
        return [_EVENT_TYPE_SOURCE_ID]

    def get_metadata(self) -> DeepDict:
        """Get the metadata, with the session start time from the time the file was opened.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        if self._event_file.time_opened is not None:
            metadata["NWBFile"]["session_start_time"] = self._event_file.time_opened.isoformat()
        metadata["Events"][self.metadata_key]["event_types"][_EVENT_TYPE_SOURCE_ID] = {
            "event_name": _EVENT_TYPE_SOURCE_ID,
            "columns": {field_source_id: dict(column) for field_source_id, column in _COLUMNS.items()},
        }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the single entry holding every record, cached after the first call."""
        if self._events_data_dict is not None:
            return self._events_data_dict

        records = self._event_file.records
        self._events_data_dict = {
            _EVENT_TYPE_SOURCE_ID: _EventsData(
                event_type_source_id=_EVENT_TYPE_SOURCE_ID,
                timestamps=records["timestamp"].astype("float64") / 1e6,
                payload=dict(
                    event_id=records["event_id"],
                    ttl_value=records["ttl_value"],
                    text=np.array(records["event_string"].tolist()),
                ),
            )
        }
        return self._events_data_dict
