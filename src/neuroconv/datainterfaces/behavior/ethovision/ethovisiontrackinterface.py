import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import TimeSeries
from pynwb.behavior import SpatialSeries
from pynwb.file import NWBFile

from ._ethovision_reader import (
    X_COLUMN,
    Y_COLUMN,
    get_available_tracks,
    read_track,
    select_track_source,
)
from ...._temporal_alignment import _TemporalAlignment
from ....basedatainterface import BaseDataInterface
from ....tools import get_module
from ....utils import DeepDict, calculate_regular_series_rate, to_camel_case, to_snake_case


class EthoVisionTrackInterface(BaseDataInterface):
    """Interface for one Track in a Noldus EthoVision XT export.

    A Track is one subject's sampled data in one arena during one EthoVision recording run
    (what EthoVision calls a trial). Excel workbooks and text exports are container variants of
    the same Track model. An Excel workbook holds every Track of a run; ``arena_name`` and
    ``subject_name`` select one. Manual Scoring sheets are not converted.

    Timestamps come from the ``Trial time`` column, which counts from the start of the run and
    is shared by every Track of that run, so it matches the ``Start time`` written to
    ``session_start_time``. ``Recording time``, which counts from each Track's own acquisition
    start, is not used.

    The selected source content is mapped to NWB as follows:

    * ``X center`` and ``Y center`` -> one :class:`~pynwb.behavior.SpatialSeries`.
    * Every other Track channel -> one :class:`~pynwb.base.TimeSeries`.

    These objects are written directly to the ``behavior`` processing module.
    """

    display_name = "EthoVision"
    keywords = ("EthoVision", "Noldus", "tracking", "behavior")
    associated_suffixes = (".xlsx", ".txt")
    info = "Interface for Noldus EthoVision XT Track exports."

    @staticmethod
    def get_available_tracks(file_path: FilePath, delimiter: str | None = None) -> list[dict[str, str]]:
        """Return the complete selector arguments for every available Track.

        Tracks are listed as the export declares them, without reading their samples. A Track
        whose acquisition never started is declared like any other, and EthoVision writes
        ``No samples logged for this track!`` in place of its rows; selecting it raises.
        ``delimiter`` is passed for a text export whose delimiter is not detected, as in
        ``__init__``.
        """
        return get_available_tracks(file_path=file_path, delimiter=delimiter)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        arena_name: str | None = None,
        subject_name: str | None = None,
        missing_value_representation: str = "-",
        delimiter: str | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize an interface for one EthoVision Track.

        Parameters
        ----------
        file_path : FilePath
            Path to an EthoVision ``.xlsx`` workbook or text (``.txt``) Track export.
        arena_name : str, optional
            Arena to select. Inferred when the source contains only one matching arena.
        subject_name : str, optional
            Subject to select, matching the export's ``Subject name``. Inferred when the source
            contains only one matching subject. EthoVision subject names are role labels defined
            once per experiment and reused in every arena and run, so they identify a Track and
            not an animal.
        missing_value_representation : str, default: "-"
            The marker the export uses for a missing sample, set by EthoVision's "Missing Value
            Representation" export option. Cells holding it become ``NaN``.
        delimiter : str, optional
            The character a text export separates columns with, set by EthoVision's "Delimiter"
            export option. Detected when not passed; raises for an Excel workbook.
        metadata_key : str, optional
            The key for this track's metadata blocks. By default it is derived from the Track
            sheet's arena and subject so several interfaces can share an NWB file.
        verbose : bool, default: False
            Whether to print progress.
        """
        self.file_path = Path(file_path)
        self.track_source = select_track_source(
            file_path=file_path,
            arena_name=arena_name,
            subject_name=subject_name,
            delimiter=delimiter,
        )
        self.arena = self.track_source.arena
        self.subject = self.track_source.subject
        self.metadata_key = metadata_key or f"ethovision_{to_snake_case(f'{self.arena}_{self.subject}')}"
        self.verbose = verbose
        super().__init__(
            file_path=file_path,
            arena_name=self.arena,
            subject_name=self.subject,
            missing_value_representation=missing_value_representation,
            delimiter=delimiter,
            metadata_key=self.metadata_key,
            verbose=verbose,
        )

        self._track = read_track(
            file_path=self.file_path,
            source=self.track_source,
            missing_value_representation=missing_value_representation,
            delimiter=delimiter,
        )
        self._channel_snake_names = _number_clashing_snake_names(
            channel_names=[name for name in self._track.channels if name not in (X_COLUMN, Y_COLUMN)]
        )
        self._time_series_metadata_keys = {
            channel_name: f"{self.metadata_key}_{snake_name}"
            for channel_name, snake_name in self._channel_snake_names.items()
        }
        # Alignment by composition, the component the events interfaces hold; see neuroconv/_temporal_alignment.py.
        self.alignment = _TemporalAlignment()
        self.alignment._register_series(key=self.metadata_key, get_native_times=lambda: self._track.trial_time)

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        named_series_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "unit": {"type": "string"},
            },
            "required": ["name", "description", "unit"],
            "additionalProperties": True,
        }
        spatial_series_schema = {
            "type": "object",
            "properties": {
                **named_series_schema["properties"],
                "reference_frame": {"type": "string"},
            },
            "required": [*named_series_schema["required"], "reference_frame"],
            "additionalProperties": True,
        }
        metadata_schema["properties"]["SpatialSeries"] = {
            "type": "object",
            "additionalProperties": spatial_series_schema,
        }
        metadata_schema["properties"]["TimeSeries"] = {
            "type": "object",
            "additionalProperties": named_series_schema,
        }
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        start_time = self._track.header.get("Start time")
        if start_time:
            metadata["NWBFile"]["session_start_time"] = _parse_start_time(start_time=start_time)

        object_suffix = to_camel_case(to_snake_case(f"{self.arena} {self.subject}"))
        position_description = f"Center position for {self.subject} in {self.arena}, from EthoVision."
        # The export does not mark which samples were missed, not found or interpolated, so these
        # header percentages are the only record of the Track's quality; they are kept as written.
        quality_fields = [
            f"{field} {self._track.header[field]}"
            for field in ("Missed samples", "Subject not found", "Interpolated samples")
            if self._track.header.get(field)
        ]
        if quality_fields:
            position_description += f" EthoVision header: {', '.join(quality_fields)}."
        metadata["SpatialSeries"][self.metadata_key] = dict(
            name=f"EthoVisionPosition{object_suffix}",
            description=position_description,
            unit=self._track.units.get(X_COLUMN) or "n/a",
            reference_frame="Arena, as EthoVision's own calibration defines it.",
        )
        metadata["TimeSeries"] = {
            self._time_series_metadata_keys[channel_name]: dict(
                name=(f"EthoVision{to_camel_case(self._channel_snake_names[channel_name])}{object_suffix}"),
                description=f"'{channel_name}' channel from an EthoVision Track sheet.",
                unit=self._track.units.get(channel_name) or "n/a",
            )
            for channel_name in self._track.channels
            if channel_name not in (X_COLUMN, Y_COLUMN)
        }
        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None) -> None:
        """Write one Track's position and channels to the ``behavior`` processing module."""
        resolved_metadata = DeepDict(self.get_metadata())
        if metadata is not None:
            resolved_metadata.deep_update(metadata)
        processing_module = get_module(nwbfile=nwbfile, name="behavior", description="Processed behavioral data.")

        timestamps = self.alignment[self.metadata_key].get_times()
        rate = calculate_regular_series_rate(series=timestamps)
        time_kwargs = dict(rate=rate, starting_time=timestamps[0]) if rate else dict(timestamps=timestamps)

        position_metadata = dict(resolved_metadata["SpatialSeries"][self.metadata_key])
        position_data = np.column_stack([self._track.channels[X_COLUMN], self._track.channels[Y_COLUMN]])
        spatial_series = SpatialSeries(
            data=position_data,
            unit=position_metadata.pop("unit"),
            reference_frame=position_metadata.pop("reference_frame"),
            description=position_metadata.pop("description", ""),
            **time_kwargs,
            **position_metadata,
        )
        processing_module.add(spatial_series)

        for source_channel_name, time_series_metadata_key in self._time_series_metadata_keys.items():
            series_metadata = resolved_metadata["TimeSeries"][time_series_metadata_key]
            time_series = TimeSeries(
                data=self._track.channels[source_channel_name],
                **series_metadata,
                **time_kwargs,
            )
            processing_module.add(time_series)


def _number_clashing_snake_names(*, channel_names: list[str]) -> dict[str, str]:
    """Map channel names to snake-case names, numbering later ones that clash with an earlier one.

    EthoVision labels can differ only by punctuation, such as ``Zone1(Zone 1 / Center-point)`` and
    ``Zone1(Zone-1 / Center-point)``, which snake-case to the same name. The first keeps the name and
    later ones get ``_2``, ``_3`` in column order, with a warning naming the source columns.
    """
    snake_names = {}
    channels_by_base_name = {}
    for channel_name in channel_names:
        base_name = to_snake_case(channel_name)
        clashing_channels = channels_by_base_name.setdefault(base_name, [])
        clashing_channels.append(channel_name)
        number = len(clashing_channels)
        snake_names[channel_name] = base_name if number == 1 else f"{base_name}_{number}"

    for base_name, clashing_channels in channels_by_base_name.items():
        if len(clashing_channels) > 1:
            numbered = ", ".join(f"'{name}' -> '{snake_names[name]}'" for name in clashing_channels)
            warnings.warn(
                f"EthoVision channels {clashing_channels} all convert to the name '{base_name}', so they are "
                f"numbered in column order: {numbered}.",
                UserWarning,
                stacklevel=3,
            )
    return snake_names


def _parse_start_time(*, start_time: str) -> datetime:
    """Parse an EthoVision timestamp, whose date order and fractional separator follow the writer's locale.

    The export declares no locale, so the two are read together: a file that writes the seconds
    fraction with a comma also writes the date day first, and one that writes a period writes it
    month first. A component above 12 settles the order on its own.
    """
    date_part, _, time_part = start_time.partition(" ")
    first, second, year = date_part.split("/")
    day_first = "," in time_part
    if int(first) > 12:
        day_first = True
    elif int(second) > 12:
        day_first = False
    day, month = (first, second) if day_first else (second, first)
    time_part = time_part.replace(",", ".")
    if "." not in time_part:
        time_part = f"{time_part}.0"
    return datetime.strptime(f"{month}/{day}/{year} {time_part}", "%m/%d/%Y %H:%M:%S.%f")
