from datetime import datetime, timezone

import numpy as np
from pydantic import DirectoryPath, validate_call
from pynwb.file import NWBFile

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools import get_package, nwb_helpers
from neuroconv.utils import DeepDict

from ...ophys.tdt_fp._tdt_mixin import TDTLoadMixin

_NEW_ISSUE_URL = "https://github.com/catalystneuro/neuroconv/issues/new"


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


class TDTEventsInterface(TDTLoadMixin, BaseDataInterface):
    """Data Interface for converting discrete events (epocs) from a TDT output folder.

    The TDT tank stores discrete events as epocs (e.g. camera TTL pulses, port entries, nose pokes).
    This interface reads those epocs via ``tdt.read_block`` and writes each selected epoc as an
    ``ndx_events.Events`` object (onset timestamps only) into a behavior ProcessingModule.

    Every epoc store in all available TDT data is an onset-type epoc: its ``offset`` array is a
    synthesized fill (``offset[i] == onset[i + 1]``, last value ``inf``) and its ``data`` array is a
    meaningless incrementing counter, so the onsets are the only informative content. Epocs that
    instead carry real offset (STROFF) durations or meaningful strobe values are not supported yet;
    the interface detects them and raises ``NotImplementedError`` pointing to a feature request.
    """

    keywords = ("behavior", "events", "TDT")
    display_name = "TDTEvents"
    info = "Data Interface for converting discrete events (epocs) from TDT files."
    associated_suffixes = ("Tbk", "Tdx", "tev", "tin", "tsq")

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        event_names: list[str] | None = None,
        metadata_key: str = "TDTEvents",
        verbose: bool = False,
    ):
        """Initialize the TDTEventsInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder containing the TDT data.
        event_names : list[str], optional
            The names of the TDT epocs to store as events. If None (default), every epoc in the
            tank is stored.
        metadata_key : str, default: "TDTEvents"
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata.
            Override it when multiple TDT events interfaces are used in the same conversion so their
            metadata does not collide.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            folder_path=folder_path,
            event_names=event_names,
            verbose=verbose,
        )
        self.metadata_key = metadata_key
        # This import is to assure that ndx_events is in the global namespace when a pynwb.io object is created
        import ndx_events  # noqa: F401

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

        event_names = self.source_data["event_names"]
        if event_names is None:
            event_names = list(self.load(evtype=["epocs"]).epocs.keys())
        for epoc_name in event_names:
            metadata["Events"][self.metadata_key][epoc_name] = {
                "name": epoc_name,
                "description": f"Onset times of the TDT epoc '{epoc_name}'.",
            }
        return metadata

    def get_metadata_schema(self) -> dict:
        """
        Get the metadata schema for the TDTEventsInterface.

        Returns
        -------
        dict
            The metadata schema for this interface.
        """
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Events"] = {
            "type": "object",
            "additionalProperties": {  # keyed by metadata_key
                "type": "object",
                "additionalProperties": {  # keyed by epoc store name (event_type_id)
                    "type": "object",
                    "required": ["name", "description"],
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            },
        }
        return metadata_schema

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict) -> None:
        """Add the selected TDT epocs to the NWBFile as ``ndx_events.Events`` objects.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the events to.
        metadata : dict
            Metadata dictionary. Each entry in ``metadata["Events"][metadata_key]`` is keyed by the
            TDT epoc store name (``event_type_id``) and maps to an ``Events`` object's ``name`` and
            ``description``.
        """
        ndx_events = get_package(package_name="ndx_events", installation_instructions="pip install ndx-events==0.2.2")

        events_metadata = metadata["Events"][self.metadata_key]
        event_object_names = [event_dict["name"] for event_dict in events_metadata.values()]
        assert len(event_object_names) == len(set(event_object_names)), (
            f"Duplicate Events 'name' values found in metadata: {event_object_names}. "
            "Each Events object must have a unique name."
        )

        behavior_module = nwb_helpers.get_module(
            nwbfile=nwbfile,
            name="behavior",
            description="Discrete events extracted from TDT epocs.",
        )

        tdt_photometry = self.load(evtype=["epocs"])
        available_epocs = list(tdt_photometry.epocs.keys())
        for epoc_name, event_dict in events_metadata.items():
            assert (
                epoc_name in available_epocs
            ), f"Epoc '{epoc_name}' not found in the TDT tank. Available epocs: {available_epocs}."
            epoc = tdt_photometry.epocs[epoc_name]
            onset = np.asarray(epoc.onset)
            offset = np.asarray(epoc.offset)
            data = np.asarray(epoc.data)
            if len(onset) == 0:
                continue

            if not _offset_is_synthesized(onset, offset):
                raise NotImplementedError(
                    f"The TDT epoc '{epoc_name}' carries real offset (STROFF) durations, which "
                    "TDTEventsInterface does not support yet (only onset timestamps are written). "
                    f"Please request support by opening an issue: {_NEW_ISSUE_URL}?title="
                    "TDTEventsInterface:+support+epocs+with+real+offset+(STROFF)+durations"
                )
            if not _data_is_counter(data):
                raise NotImplementedError(
                    f"The TDT epoc '{epoc_name}' carries meaningful strobe values, which "
                    "TDTEventsInterface does not support yet (only onset timestamps are written). "
                    f"Please request support by opening an issue: {_NEW_ISSUE_URL}?title="
                    "TDTEventsInterface:+support+epocs+with+strobe+values"
                )

            events = ndx_events.Events(
                name=event_dict["name"],
                description=event_dict["description"],
                timestamps=onset,
            )
            behavior_module.add(events)
