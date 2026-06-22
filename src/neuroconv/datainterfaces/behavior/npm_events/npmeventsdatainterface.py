from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import DirectoryPath, validate_call
from pynwb.file import NWBFile

from neuroconv.basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from neuroconv.tools import get_package, nwb_helpers
from neuroconv.utils import DeepDict

_TIME_UNIT_TO_DIVISOR = {"seconds": 1.0, "milliseconds": 1e3, "microseconds": 1e6}


class NPMEventsInterface(BaseTemporalAlignmentInterface):
    """Data Interface for converting discrete events from Neurophotometrics (NPM) files.

    NPM stores discrete events in a raw, two-column stimuli CSV: the first column holds the event
    onset time (in the recording's raw time base) and the second column holds the event type label
    (e.g. ``whitenoise``, ``pinknoise``). This interface reads that file, splits the rows by unique
    type label, and writes each label as its own ``ndx_events.Events`` object (onset timestamps
    only) into a behavior ProcessingModule.

    Notes
    -----
    The raw onset times are scaled to seconds by ``time_unit`` but are otherwise written as-is: they
    remain in the recording's raw time base. NPM recordings carry no embedded recording-start
    timestamp, so :meth:`get_metadata` does NOT populate ``NWBFile/session_start_time``. To express
    the events relative to the recording start, use :meth:`set_aligned_starting_time` (e.g. a
    converter can subtract the fiber-photometry reference timestamp); the user must supply
    ``session_start_time`` via editable metadata.
    """

    keywords = ("behavior", "events", "Neurophotometrics")
    display_name = "NPMEvents"
    info = "Data Interface for converting discrete events from Neurophotometrics files."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        event_file_name: str | None = None,
        time_unit: str = "seconds",
        verbose: bool = False,
    ):
        """Initialize the NPMEventsInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder containing the raw NPM event/stimuli CSV file(s).
        event_file_name : str, optional
            The file stem of the specific NPM event CSV to read. If None (default), every two-column
            NPM event CSV in the folder (timestamp column plus a non-numeric type-label column) is
            read.
        time_unit : {"seconds", "milliseconds", "microseconds"}, optional
            The unit of the raw onset-time column, default = "seconds". Onset times are divided by
            the corresponding factor to convert them to seconds.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        if time_unit not in _TIME_UNIT_TO_DIVISOR:
            raise ValueError(f"time_unit must be one of {list(_TIME_UNIT_TO_DIVISOR)}, got '{time_unit}'.")
        super().__init__(
            folder_path=folder_path,
            event_file_name=event_file_name,
            time_unit=time_unit,
            verbose=verbose,
        )
        self._value_to_timestamps = None
        # This import is to assure that ndx_events is in the global namespace when a pynwb.io object is created
        import ndx_events  # noqa: F401

    @staticmethod
    def _is_npm_event_file(path: Path) -> bool:
        """Return True if ``path`` is a two-column NPM event CSV (timestamp, label).

        NPM event files are header-less two-column CSVs. The label column may be a string
        (``whitenoise``), a boolean (``True``/``False``), or a numeric code (``1``/``3``) -- all are
        treated uniformly as labels. The two-column shape positively distinguishes them from the
        single-column CSV-format TTLs, the three-column CSV-format streams, and the multi-column NPM
        photometry files.
        """
        return pd.read_csv(path, header=None, nrows=5).shape[1] == 2

    def _event_file_paths(self) -> list[Path]:
        """Get the raw NPM event CSV path(s) to read."""
        folder_path = Path(self.source_data["folder_path"])
        event_file_name = self.source_data["event_file_name"]
        if event_file_name is not None:
            return [folder_path / f"{event_file_name}.csv"]
        return [path for path in sorted(folder_path.glob("*.csv")) if self._is_npm_event_file(path)]

    def _read_value_to_timestamps(self) -> dict[str, np.ndarray]:
        """Read the event CSV(s) and split onset times by unique type label (cached).

        Returns
        -------
        dict[str, np.ndarray]
            Maps each event type label (as a string) to its onset times, scaled to seconds by
            ``time_unit`` but otherwise in the recording's raw time base. Labels are ordered by first
            appearance.
        """
        if self._value_to_timestamps is not None:
            return self._value_to_timestamps

        divisor = _TIME_UNIT_TO_DIVISOR[self.source_data["time_unit"]]
        value_to_timestamps: dict[str, np.ndarray] = {}
        for path in self._event_file_paths():
            # float_precision="round_trip" uses an exact, platform-independent float parser; pandas's
            # default C parser rounds the final ULP differently across platforms.
            dataframe = pd.read_csv(path, header=None, float_precision="round_trip")
            timestamps = dataframe.iloc[:, 0].to_numpy(dtype=float) / divisor
            labels = dataframe.iloc[:, 1].to_numpy()
            for label in pd.unique(labels):
                label_timestamps = timestamps[labels == label]
                value = str(label)
                if value in value_to_timestamps:
                    value_to_timestamps[value] = np.concatenate([value_to_timestamps[value], label_timestamps])
                else:
                    value_to_timestamps[value] = label_timestamps

        self._value_to_timestamps = value_to_timestamps
        return value_to_timestamps

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the NPMEventsInterface.

        ``NWBFile/session_start_time`` is intentionally left unset: NPM recordings carry no embedded
        recording-start timestamp, so it must be supplied by the user via editable metadata.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        metadata["Behavior"]["NPMEvents"]["Events"] = [
            {
                "value": value,
                "name": value,
                "description": f"Onset times of the '{value}' events from the Neurophotometrics recording.",
            }
            for value in self._read_value_to_timestamps()
        ]
        return metadata

    def get_metadata_schema(self) -> dict:
        """
        Get the metadata schema for the NPMEventsInterface.

        Returns
        -------
        dict
            The metadata schema for this interface.
        """
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Behavior"] = {
            "type": "object",
            "properties": {
                "NPMEvents": {
                    "type": "object",
                    "properties": {
                        "module_name": {"type": "string"},
                        "module_description": {"type": "string"},
                        "Events": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["value", "name", "description"],
                                "properties": {
                                    "value": {"type": "string"},
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        }
        return metadata_schema

    def get_original_timestamps(self) -> dict[str, np.ndarray]:
        """
        Get the original onset timestamps, split by event type label.

        Returns
        -------
        dict[str, np.ndarray]
            Dictionary of event type label to onset times (scaled to seconds by ``time_unit``).
        """
        return {value: timestamps for value, timestamps in self._read_value_to_timestamps().items()}

    def get_timestamps(self) -> dict[str, np.ndarray]:
        """
        Get the (possibly aligned) onset timestamps, split by event type label.

        Returns
        -------
        dict[str, np.ndarray]
            Dictionary of event type label to onset times.
        """
        value_to_timestamps = getattr(self, "value_to_aligned_timestamps", None)
        if value_to_timestamps is None:
            value_to_timestamps = self.get_original_timestamps()
        return value_to_timestamps

    def set_aligned_timestamps(self, value_to_aligned_timestamps: dict[str, np.ndarray]) -> None:
        """
        Set the aligned onset timestamps.

        Parameters
        ----------
        value_to_aligned_timestamps : dict[str, np.ndarray]
            Dictionary of event type label to aligned onset times.
        """
        self.value_to_aligned_timestamps = value_to_aligned_timestamps

    def set_aligned_starting_time(self, aligned_starting_time: float) -> None:
        """
        Shift every event type's onset times by ``aligned_starting_time``.

        Parameters
        ----------
        aligned_starting_time : float
            The aligned starting time to add to all onset times.
        """
        value_to_timestamps = self.get_timestamps()
        value_to_aligned_timestamps = {
            value: timestamps + aligned_starting_time for value, timestamps in value_to_timestamps.items()
        }
        self.set_aligned_timestamps(value_to_aligned_timestamps)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict) -> None:
        """Add the NPM events to the NWBFile as one ``ndx_events.Events`` object per type label.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the events to.
        metadata : dict
            Metadata dictionary. Each entry in ``metadata["Behavior"]["NPMEvents"]["Events"]`` maps an
            event type label (``value``) to an ``Events`` object's ``name`` and ``description``.
        """
        ndx_events = get_package(package_name="ndx_events", installation_instructions="pip install ndx-events==0.2.2")

        events_metadata = metadata["Behavior"]["NPMEvents"]["Events"]
        event_object_names = [event_dict["name"] for event_dict in events_metadata]
        assert len(event_object_names) == len(set(event_object_names)), (
            f"Duplicate Events 'name' values found in metadata: {event_object_names}. "
            "Each Events object must have a unique name."
        )

        module_name = metadata["Behavior"]["NPMEvents"].get("module_name", "behavior")
        module_description = metadata["Behavior"]["NPMEvents"].get(
            "module_description", "Discrete events extracted from the Neurophotometrics recording."
        )
        behavior_module = nwb_helpers.get_module(
            nwbfile=nwbfile,
            name=module_name,
            description=module_description,
        )

        value_to_timestamps = self.get_timestamps()
        for event_dict in events_metadata:
            timestamps = value_to_timestamps[event_dict["value"]]
            if len(timestamps) == 0:
                continue
            events = ndx_events.Events(
                name=event_dict["name"],
                description=event_dict["description"],
                timestamps=np.asarray(timestamps),
            )
            behavior_module.add(events)
