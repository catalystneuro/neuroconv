"""Interface for raw Neurophotometrics (NPM) fiber photometry data.

NPM is a raw acquisition format that interleaves the excitation channels frame-by-frame down the
rows of a single CSV: an isosbestic channel and one or more signal channels are multiplexed, and
each remaining column (e.g. ``Region0G``) is a region of interest. Each row is labelled by a
``Flags``/``LedState`` column, whose value is a packed word: the three lowest bits encode which
excitation LED was on (``001`` = 415 nm, ``010`` = 470 nm, ``100`` = 560 nm) and the higher bits are
digital TTL lines. Two rows that share an excitation LED but differ in a TTL line therefore carry
different ``LedState`` values (e.g. ``17`` and ``273`` are both 415 nm), so a channel is selected by
masking the three lowest bits rather than by matching the raw value.
"""

from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import FilePath, validate_call

from ..csv.csvfiberphotometrydatainterface import CSVFiberPhotometryInterface

# The three lowest bits of a Flags/LedState word encode the excitation LED; the higher bits are
# digital TTL lines. Mask to these bits to recover the wavelength regardless of the TTL state.
_EXCITATION_BITS = 0b111
_WAVELENGTH_TO_CODE = {415: 1, 470: 2, 560: 4}
_CODE_TO_WAVELENGTH = {code: wavelength for wavelength, code in _WAVELENGTH_TO_CODE.items()}


class NPMFiberPhotometryInterface(CSVFiberPhotometryInterface):
    """Interface for a Neurophotometrics CSV file (a ``Flags``/``LedState``-labeled acquisition).

    The NPM file is a header-bearing CSV whose channel multiplexing is driven by a ``Flags`` or
    ``LedState`` column: each row belongs to whichever excitation LED was on, encoded in the three
    lowest bits of that column's packed word. This interface reads the one excitation channel given
    by ``excitation_wavelength_in_nm`` and writes the selected region column(s) as one
    ``FiberPhotometryResponseSeries``.

    Use :meth:`get_available_excitation_wavelengths` to discover the channels; the region column
    names come from the inherited :meth:`get_available_columns`.

    Header-less Neurophotometrics output has no NPM-specific structure and
    should be read with :class:`.CSVFiberPhotometryInterface` directly.
    """

    display_name = "NPMFiberPhotometry"
    info = "Interface for raw fiber photometry data from Neurophotometrics files."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        excitation_wavelength_in_nm: Literal[415, 470, 560],
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
            The raw NPM CSV file.
        excitation_wavelength_in_nm : {415, 470, 560}
            The excitation LED identifying the one channel this interface reads.
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
            When None (default), a key distinct per ``(excitation_wavelength_in_nm, data_columns)`` is
            generated, so several interfaces reading the same file do not collide.
        read_kwargs : dict, optional
            Additional keyword arguments forwarded to ``pandas.read_csv`` to handle format quirks
            (e.g. ``sep``, ``encoding``, ``decimal``). Default is None.
        verbose : bool, default: False
            Whether to print status messages.
        """
        data_columns_list = [data_columns] if isinstance(data_columns, str) else list(data_columns)
        state_column = self._detect_state_column(file_path, read_kwargs)

        code = _WAVELENGTH_TO_CODE[excitation_wavelength_in_nm]
        state_values = self._read_state_values(file_path, state_column, read_kwargs)
        matching_states = [value for value in state_values if value & _EXCITATION_BITS == code]
        assert matching_states, (
            f"No rows with excitation wavelength {excitation_wavelength_in_nm} nm in '{file_path}'. "
            f"Available wavelengths: {self.get_available_excitation_wavelengths(file_path, read_kwargs)}."
        )

        if metadata_key is None:
            metadata_key = self._default_metadata_key(file_path, excitation_wavelength_in_nm, data_columns_list)

        super().__init__(
            file_path=file_path,
            data_columns=data_columns_list,
            timestamps_column=timestamps_column,
            demux_config={"by": "column", "column": state_column, "value": matching_states},
            time_unit=time_unit,
            metadata_key=metadata_key,
            read_kwargs=read_kwargs,
            verbose=verbose,
        )

    @classmethod
    def get_available_excitation_wavelengths(cls, file_path: FilePath, read_kwargs: dict | None = None) -> list[int]:
        """Return the excitation wavelengths (nm) present in the file, sorted.

        Each row's ``Flags``/``LedState`` word is masked to its three lowest bits to recover the
        excitation LED; the single-LED codes (``001``/``010``/``100``) map to 415/470/560 nm. Codes
        that are not a single excitation LED -- no LED on (a startup/initialization frame) or several
        LEDs on together -- are not fiber photometry channels and are left out.
        """
        state_column = cls._detect_state_column(file_path, read_kwargs)
        codes = {value & _EXCITATION_BITS for value in cls._read_state_values(file_path, state_column, read_kwargs)}
        return sorted(_CODE_TO_WAVELENGTH[code] for code in codes if code in _CODE_TO_WAVELENGTH)

    @staticmethod
    def _read_state_values(file_path: FilePath, state_column: str, read_kwargs: dict | None) -> list[int]:
        """Return the sorted unique values of the file's ``Flags``/``LedState`` column."""
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
            f"NPM files must contain a 'Flags' or 'LedState' column. Found columns: {columns}. "
            "Header-less Neurophotometrics output should be read with CSVFiberPhotometryInterface instead."
        )

    @staticmethod
    def _default_metadata_key(file_path: FilePath, excitation_wavelength_in_nm: int, data_columns: list[str]) -> str:
        stem = Path(file_path).stem.replace(" ", "_").strip("_").lower()
        regions = "_".join(str(column).replace(" ", "_").lower() for column in data_columns)
        return f"fiber_photometry_{stem}_{excitation_wavelength_in_nm}nm_{regions}"
