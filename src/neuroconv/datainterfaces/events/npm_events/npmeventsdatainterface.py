from typing import Literal

import pandas as pd
from pydantic import FilePath, validate_call

from ..csv_events.csveventsdatainterface import CSVEventsInterface


class NPMEventsInterface(CSVEventsInterface):
    """Data Interface for converting discrete events from Neurophotometrics (NPM) files.

    NPM stores discrete events in a raw, headerless two-column stimuli CSV: the first column holds the
    event onset time (in the recording's raw time base) and the second column holds the event type
    label (e.g. ``whitenoise``, ``pinknoise``, a boolean ``True``/``False`` annotation, or a numeric
    code). This is exactly a headerless CSV with a timestamp column and an event-type column, so this
    interface is a thin :class:`.CSVEventsInterface` that fixes those two columns. Each distinct label
    becomes its own ``pynwb.event.EventsTable`` (onset timestamps only) in ``nwbfile.events``.

    Notes
    -----
    Note that we *assume* the second column is the event **type**. Each distinct value becomes its own
    event type/table rather than a per-event value/payload column.

    The raw onset times are scaled to seconds by ``time_unit`` (see :class:`.CSVEventsInterface`) but
    are otherwise written as-is: they remain in the recording's raw time base. NPM recordings carry no
    embedded recording-start timestamp, so :meth:`get_metadata` does NOT populate
    ``NWBFile/session_start_time``; the user must supply it via editable metadata.

    This interface targets the standalone Bonsai stimuli CSV *only*. NPM can also embed discrete events
    directly in the photometry/signal CSV, alongside the fluorescence columns: older firmware writes each
    digital I/O line (e.g. ``Stimulation``, ``Output0``/``Output1``, ``Input0``/``Input1``) as its own
    0/1-per-frame column, while newer firmware bit-packs those same lines into the ``Flags``/``LedState``
    column. This interface's fixed headerless two-column layout does not fit that photometry CSV; use
    :class:`.CSVEventsInterface` directly to select the relevant columns from it.
    """

    keywords = ("events", "Neurophotometrics")
    display_name = "NPMEvents"
    info = "Data Interface for converting discrete events from Neurophotometrics files."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        time_unit: Literal["seconds", "milliseconds", "microseconds"] = "seconds",
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the NPMEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            The path to the raw NPM event/stimuli CSV file: a headerless two-column CSV whose first
            column is the event onset time and whose second column is the event type label.
        time_unit : {"seconds", "milliseconds", "microseconds"}, optional
            The unit of the raw onset-time column, default = "seconds". Onset times are divided by the
            corresponding factor to convert them to seconds.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata.
            If None (default), the file stem is used (inherited from :class:`.CSVEventsInterface`).
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        # We assume column 1 is the event *type* (one table per distinct value), not a per-event value/
        # payload column. Every NPM stimuli file we have seen behaves this way, but the vendor manual
        # never pins the two-column format down -- it documents a KeyDown time/label example and a
        # separate 5-column Digital IOs log, without specifying that the second column is the type, not a
        # value. This is a convention matched to our examples, not a documented guarantee; do not treat
        # it as gospel.
        number_of_columns = pd.read_csv(file_path, header=None, nrows=1).shape[1]
        if number_of_columns > 2:
            raise ValueError(
                f"NPMEventsInterface expects a headerless two-column CSV (onset time, event type), but "
                f"this file has {number_of_columns} columns. Neurophotometrics also produces richer event "
                f"files (e.g. the 5-column Digital IOs log), which this interface does not support. Please "
                f"open an issue at https://github.com/catalystneuro/neuroconv/issues if you need it."
            )
        super().__init__(
            file_path=file_path,
            timestamps_column=0,
            event_type_column=1,
            time_unit=time_unit,
            metadata_key=metadata_key,
            verbose=verbose,
        )
