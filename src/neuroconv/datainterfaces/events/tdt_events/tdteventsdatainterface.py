from datetime import datetime, timezone

import numpy as np
from pydantic import DirectoryPath, validate_call

from neuroconv.utils import DeepDict

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ...ophys.tdt_fp._tdt_mixin import TDTLoadMixin


def _offset_is_synthesized(onset: np.ndarray, offset: np.ndarray) -> bool:
    """Return whether the epoc's ``offset`` array is a synthesized fill rather than real falling edges.

    TDT fills onset-only epocs with ``offset = np.append(onset[1:], inf)`` (see ``tdt/TDTbin2py.py``,
    where ``header.stores[var_name].offset = np.append(ts[1:], np.inf)``). A genuine paired
    "buddy" offset store overwrites this with real falling-edge timestamps, which cannot reproduce
    ``offset[i] == onset[i + 1]`` for every ``i``. Detecting the fill is therefore an exact
    structural check, not a tolerance heuristic.
    """
    return len(offset) > 0 and np.isinf(offset[-1]) and np.array_equal(offset[:-1], onset[1:])


def _data_is_counter(data: np.ndarray) -> bool:
    """Return whether the epoc's ``data`` array is a meaningless incrementing index.

    Onset-only epocs store a sequential counter (``0..N-1`` or ``1..N``) as their ``data``; a real
    strobe carries meaningful codes (e.g. the ``[16, 2064, 0]`` cycle of the ``PAB_`` store) that do
    not form an arithmetic sequence.
    """
    n = len(data)
    return n > 0 and np.array_equal(data, np.arange(data[0], data[0] + n))


def _normalize_strobe_value(value: float) -> int | float:
    """Normalize a raw strobe value to a clean scalar for use as a label-map key.

    Strobe codes are integer-valued floats in the TDT data (e.g. ``16.0``); cast those to ``int`` so
    the seeded ``labels`` map reads as ``{16: "16"}`` rather than ``{16.0: "16.0"}``.
    """
    value = float(value)
    return int(value) if value.is_integer() else value


class TDTEventsInterface(TDTLoadMixin, BaseEventsInterface):
    """Data Interface for converting discrete events (epocs) from a TDT output folder.

    The TDT tank stores discrete events as epocs (e.g. camera TTL pulses, port entries, nose pokes).
    This interface reads those epocs via ``tdt.read_block`` and writes each selected epoc as one
    ``pynwb.event.EventsTable`` inside ``nwbfile.events``.

    Most epoc stores are onset-type epocs whose ``data`` array is a meaningless incrementing counter,
    so only the onsets are written (a timestamp-only table). A store whose ``data`` carries real
    strobe codes (e.g. the ``PAB_`` store's ``[16, 2064, 0]`` cycle) additionally gets a categorical
    ``strobe`` column, with the codes as per-event labels. The ``offset`` array of an onset-type epoc
    is a synthesized fill (``offset[i] == onset[i + 1]``, last value ``inf``) and is not written.
    Epocs that carry real offset (STROFF) durations are written as durative events, with each event's
    duration (``offset`` minus ``onset``) in the table's ``duration`` column.
    """

    keywords = ("events", "TDT")
    display_name = "TDTEvents"
    info = "Data Interface for converting discrete events (epocs) from TDT files."
    associated_suffixes = ("Tbk", "Tdx", "tev", "tin", "tsq")

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        exclude_events: list[str] | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the TDTEventsInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder containing the TDT data.
        exclude_events : list[str], optional
            The names of the TDT epocs to skip. If None (default), every epoc in the tank is stored.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata.
            If None (default), ``"tdt_events"`` is used.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            folder_path=folder_path,
            exclude_events=exclude_events,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "tdt_events"

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the TDTEventsInterface.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        tdt_photometry = self.load(evtype=["scalars"])  # This evtype quickly loads info without loading all the data.
        start_timestamp = tdt_photometry.info.start_date.timestamp()
        session_start_datetime = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
        metadata["NWBFile"]["session_start_time"] = session_start_datetime.isoformat()

        epocs = self.load(evtype=["epocs"]).epocs
        exclude_events = self.source_data["exclude_events"] or []
        included_events = [epoc_name for epoc_name in epocs.keys() if epoc_name not in exclude_events]
        for epoc_name in included_events:
            data = np.asarray(epocs[epoc_name].data)
            if len(data) == 0:
                continue  # an epoc with no events is not a writable event type; skip it entirely
            is_strobe = not _data_is_counter(data)

            # One EventsTable per epoc store; event_name defaults to the store name. A counter store is
            # timestamp-only (no columns); a real strobe gets one categorical 'strobe' column (keyed by
            # its payload field) with an editable code -> label map.
            event_description = f"Onset times of the TDT epoc '{epoc_name}'."
            entry = {"event_name": epoc_name, "event_description": event_description}
            if is_strobe:
                entry["event_description"] = f"Onset times of the TDT epoc '{epoc_name}', labeled by strobe value."
                entry["columns"] = {
                    "strobe": {
                        "column_name": "strobe",
                        "description": f"Strobe code for each '{epoc_name}' event.",
                        "column_categories": {
                            "labels": {
                                _normalize_strobe_value(value): str(_normalize_strobe_value(value))
                                for value in np.unique(data)
                            }
                        },
                    }
                }
            metadata["Events"][self.metadata_key]["event_types"][epoc_name] = entry
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation from the TDT epocs, cached after the first call.

        Each included epoc becomes one :class:`_EventsData`: a counter epoc yields onset timestamps only
        (a bare marker, empty payload), while a strobe epoc (real ``data`` codes) carries the per-event
        codes under the ``"strobe"`` payload field, normalized to match the ``column_categories["labels"]``
        keys seeded by :meth:`get_metadata`. An onset-only epoc is timestamp-only (``durations`` left
        ``None``); an epoc carrying real offset (STROFF) durations is written with per-event durations
        (``offset`` minus ``onset``).
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        tdt_photometry = self.load(evtype=["epocs"])
        exclude_events = self.source_data["exclude_events"] or []
        included_events = [epoc_name for epoc_name in tdt_photometry.epocs.keys() if epoc_name not in exclude_events]

        events_data_dict = {}
        for epoc_name in included_events:
            epoc = tdt_photometry.epocs[epoc_name]
            onset = np.asarray(epoc.onset)
            offset = np.asarray(epoc.offset)
            data = np.asarray(epoc.data)
            if len(onset) == 0:
                continue  # an epoc with no onsets is not a writable event type; skip it (matches get_metadata)

            # An onset-only epoc's offset is a synthesized fill carrying no information, so the type is
            # timestamp-only (durations left None). A durative (STROFF) epoc has real falling edges,
            # written as per-event durations (offset minus onset).
            if _offset_is_synthesized(onset, offset):
                durations = None
            else:
                durations = offset - onset

            # A counter ``data`` array is a meaningless index (a bare marker); a real strobe carries
            # per-event codes, kept under the 'strobe' payload field and normalized to the label keys.
            payload = {}
            if not _data_is_counter(data):
                payload = {"strobe": np.array([_normalize_strobe_value(value) for value in data])}
            events_data_dict[epoc_name] = _EventsData(
                event_type_source_id=epoc_name, timestamps=onset, durations=durations, payload=payload
            )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
