"""Interfaces for raw Neurophotometrics (NPM) fiber photometry data.

NPM is a raw acquisition format that interleaves the excitation channels frame-by-frame down the
rows of a single CSV: an isosbestic channel and one or more signal channels are multiplexed, and
each remaining column (e.g. ``Region0G``) is a region of interest. The modern format labels each
row's channel with a ``Flags``/``LedState`` column; the older, header-less format cycles the
channels in a fixed row order with no label column.

De-interleaving one channel out of such a file is exactly what :class:`.CSVFiberPhotometryInterface`
does through its ``demux_config``, so these interfaces are thin wrappers: they translate NPM's shape
into a demux config (a :class:`.ColumnDemux` for the modern format, a :class:`.StrideDemux` for the
legacy one) and defer everything else -- reading, the response series, the device/table assembly --
to the CSV base. Each interface still writes exactly one ``FiberPhotometryResponseSeries``; compose
one per channel in a converter.
"""

from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import FilePath, validate_call

from ..csv.csvfiberphotometrydatainterface import CSVFiberPhotometryInterface


class NPMFiberPhotometryInterface(CSVFiberPhotometryInterface):
    """Interface for a modern (``Flags``/``LedState``-labeled) Neurophotometrics CSV file.

    The modern NPM file is a header-bearing CSV whose channel multiplexing is driven by a ``Flags``
    or ``LedState`` column: each row belongs to whichever excitation LED was on. This interface reads
    the one channel whose state equals ``led_state`` (auto-detecting which of ``Flags``/``LedState``
    the file uses) and writes the selected region column(s) as one ``FiberPhotometryResponseSeries``.

    Use :meth:`get_available_led_states` to discover the channels; the region column names come from
    the inherited :meth:`get_available_columns`. For the older header-less NPM format, use
    :class:`.NPMLegacyFiberPhotometryInterface`.
    """

    display_name = "NPMFiberPhotometry"
    info = "Interface for raw fiber photometry data from modern Neurophotometrics files."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        led_state: int,
        data_columns: str | list[str],
        timestamps_column: Literal["Timestamp", "SystemTimestamp", "ComputerTimestamp"] = "Timestamp",
        time_unit: Literal["seconds", "milliseconds", "microseconds"] = "seconds",
        metadata_key: str | None = None,
        read_kwargs: dict | None = None,
        verbose: bool = False,
    ):
        """Initialize the NPMFiberPhotometryInterface.

        Parameters
        ----------
        file_path : FilePath
            The raw modern NPM CSV file.
        led_state : int
            The value of the file's ``Flags``/``LedState`` column identifying the one channel this
            interface reads (see :meth:`get_available_led_states`).
        data_columns : str or list of str
            The region column name(s) whose samples are column-stacked into this interface's single
            ``FiberPhotometryResponseSeries`` (see :meth:`get_available_columns`).
        timestamps_column : {"Timestamp", "SystemTimestamp", "ComputerTimestamp"}, default: "Timestamp"
            The timestamps column to use for the series' time axis. Single-timestamp NPM files name it
            ``Timestamp`` (the default). A file with both ``SystemTimestamp`` and ``ComputerTimestamp``
            has no ``Timestamp`` column, so the default fails loudly there and you must pick one
            explicitly. For any other column name, use ``CSVFiberPhotometryInterface`` directly.
        time_unit : {"seconds", "milliseconds", "microseconds"}, optional
            The unit of the selected timestamp column, default = "seconds".
        metadata_key : str, optional
            Key under ``metadata["FiberPhotometry"]`` for this interface's response-series metadata.
            When None (default), a key distinct per ``(led_state, data_columns)`` is generated, so
            several interfaces reading the same file do not collide.
        read_kwargs : dict, optional
            Additional keyword arguments forwarded to ``pandas.read_csv`` to handle format quirks
            (e.g. ``sep``, ``encoding``, ``decimal``). Default is None.
        verbose : bool, default: False
            Whether to print status messages.
        """
        data_columns_list = [data_columns] if isinstance(data_columns, str) else list(data_columns)
        state_column = self._detect_state_column(file_path, read_kwargs)
        if metadata_key is None:
            metadata_key = self._default_metadata_key(file_path, led_state, data_columns_list)

        super().__init__(
            file_path=file_path,
            data_columns=data_columns_list,
            timestamps_column=timestamps_column,
            demux_config={"by": "column", "column": state_column, "value": led_state},
            time_unit=time_unit,
            metadata_key=metadata_key,
            read_kwargs=read_kwargs,
            verbose=verbose,
        )

    @classmethod
    def get_available_led_states(cls, file_path: FilePath, read_kwargs: dict | None = None) -> list[int]:
        """Return the sorted unique values of the file's ``Flags``/``LedState`` column.

        Each value is one interleaved channel to pass as ``led_state``. A startup/calibration frame
        (an all-LEDs-on first frame, e.g. ``Flags=16``/``LedState=7``) can appear here as an extra
        value that is not one of the recording channels.
        """
        state_column = cls._detect_state_column(file_path, read_kwargs)
        state = pd.read_csv(file_path, usecols=[state_column], **(read_kwargs or dict()))[state_column]
        return sorted(int(value) for value in pd.unique(state))

    @staticmethod
    def _detect_state_column(file_path: FilePath, read_kwargs: dict | None) -> str:
        """Return the file's channel-state column, i.e. its ``Flags`` or ``LedState`` column."""
        columns = CSVFiberPhotometryInterface.get_available_columns(file_path, read_kwargs=read_kwargs)
        lower_to_actual = {str(column).lower(): column for column in columns}
        for candidate in ("flags", "ledstate"):
            if candidate in lower_to_actual:
                return lower_to_actual[candidate]
        raise ValueError(
            f"Modern NPM files must contain a 'Flags' or 'LedState' column. Found columns: {columns}. "
            "For the older header-less NPM format, use NPMLegacyFiberPhotometryInterface instead."
        )

    @staticmethod
    def _default_metadata_key(file_path: FilePath, led_state: int, data_columns: list[str]) -> str:
        stem = Path(file_path).stem.replace(" ", "_").strip("_").lower()
        regions = "_".join(str(column).replace(" ", "_").lower() for column in data_columns)
        return f"fiber_photometry_{stem}_ledstate{led_state}_{regions}"


class NPMLegacyFiberPhotometryInterface(CSVFiberPhotometryInterface):
    """Interface for a legacy (header-less, row-cycling) Neurophotometrics CSV file.

    The legacy NPM file is a header-less CSV: the first column is the timestamp and the remaining
    columns are region-of-interest values, with the interleaved channels stored in a fixed
    row-cycling order (row ``i`` belongs to channel ``i % number_of_channels``). With no label
    column to key on, the user specifies how many channels were interleaved (``number_of_channels``)
    and which one this interface reads (``index``); columns are addressed by 0-based position.

    Legacy NPM timestamps are typically in milliseconds, so ``time_unit`` defaults to
    ``"milliseconds"``. For the modern header-bearing format, use :class:`.NPMFiberPhotometryInterface`.
    """

    display_name = "NPMLegacyFiberPhotometry"
    info = "Interface for raw fiber photometry data from legacy (header-less) Neurophotometrics files."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        number_of_channels: int,
        index: int,
        data_columns: int | list[int],
        timestamps_column: int = 0,
        skip_rows: int = 0,
        time_unit: Literal["seconds", "milliseconds", "microseconds"] = "milliseconds",
        metadata_key: str | None = None,
        read_kwargs: dict | None = None,
        verbose: bool = False,
    ):
        """Initialize the NPMLegacyFiberPhotometryInterface.

        Parameters
        ----------
        file_path : FilePath
            The raw legacy NPM CSV file.
        number_of_channels : int
            The number of interleaved channels (rows cycle through the channels in order).
        index : int
            The 0-based index of the cyclic channel this interface reads (must be < number_of_channels).
        data_columns : int or list of int
            The 0-based positional index(es) of the region column(s) whose samples are column-stacked
            into this interface's single ``FiberPhotometryResponseSeries``.
        timestamps_column : int, default: 0
            The 0-based positional index of the timestamps column.
        skip_rows : int, default: 0
            Number of leading rows to drop before the cyclic alignment (e.g. calibration frames).
        time_unit : {"seconds", "milliseconds", "microseconds"}, default: "milliseconds"
            The unit of the timestamps column.
        metadata_key : str, optional
            Key under ``metadata["FiberPhotometry"]`` for this interface's response-series metadata.
            When None (default), a key distinct per ``(index, data_columns)`` is generated, so several
            interfaces reading the same file do not collide.
        read_kwargs : dict, optional
            Additional keyword arguments forwarded to ``pandas.read_csv``. Default is None.
        verbose : bool, default: False
            Whether to print status messages.
        """
        data_columns_list = [data_columns] if isinstance(data_columns, int) else list(data_columns)
        if metadata_key is None:
            metadata_key = self._default_metadata_key(file_path, index, data_columns_list)

        super().__init__(
            file_path=file_path,
            data_columns=data_columns_list,
            timestamps_column=timestamps_column,
            demux_config={"by": "stride", "channels": number_of_channels, "index": index, "skip_rows": skip_rows},
            time_unit=time_unit,
            metadata_key=metadata_key,
            read_kwargs=read_kwargs,
            verbose=verbose,
        )

    @staticmethod
    def _default_metadata_key(file_path: FilePath, index: int, data_columns: list[int]) -> str:
        stem = Path(file_path).stem.replace(" ", "_").strip("_").lower()
        regions = "_".join(str(column) for column in data_columns)
        return f"fiber_photometry_{stem}_channel{index}_columns{regions}"
