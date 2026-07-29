"""Interface for raw Neurophotometrics (NPM) fiber photometry data.

NPM is a raw acquisition format that interleaves the excitation channels frame-by-frame down the
rows of a single CSV: an isosbestic channel and one or more signal channels are multiplexed, and
each remaining column (e.g. ``Region0G``) is a region of interest. Each row is labelled by a
``Flags``/``LedState`` column, whose value is a packed word: the three lowest bits are one flag per
excitation LED (``001`` = 415 nm, ``010`` = 470 nm, ``100`` = 560 nm) and the higher bits are digital
TTL lines.

Two consequences follow, and a channel is selected by testing its own excitation bit rather than by
comparing the whole word or the whole masked word:

- Rows that share an excitation LED but differ in a TTL line carry different values (``17`` and
  ``273`` are both 415 nm), so matching the raw value returns only part of a channel.
- Several excitation bits can be set at once, because a rig can strobe two LEDs in the same frame
  (``6`` = 470 nm and 560 nm together, their emission bands landing in different region columns), so
  matching the masked word exactly misses those frames entirely.
"""

from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import FilePath, validate_call

from ..csv.csvfiberphotometrydatainterface import CSVFiberPhotometryInterface

# The three lowest bits of a Flags/LedState word are one flag per excitation LED; the higher bits are
# digital TTL lines. A wavelength's rows are those whose word has that wavelength's bit set, whatever
# else is set alongside it.
_EXCITATION_BITS = 0b111
_WAVELENGTH_TO_CODE = {415: 1, 470: 2, 560: 4}


class NPMFiberPhotometryInterface(CSVFiberPhotometryInterface):
    """Interface for a Neurophotometrics CSV file (a ``Flags``/``LedState``-labeled acquisition).

    The NPM file is a header-bearing CSV whose channel multiplexing is driven by a ``Flags`` or
    ``LedState`` column: each row records which excitation LEDs were on, one flag per LED in the three
    lowest bits of that column's packed word. This interface reads the one excitation channel given by
    ``excitation_wavelength_in_nm`` -- every row whose word has that wavelength's bit set -- and writes
    the selected region column(s) as one ``FiberPhotometryResponseSeries``.

    A frame that strobes two LEDs at once therefore belongs to both of their channels, and the caller
    picks the region columns carrying the emission band of interest: in a ``LedState`` 6 frame (470 nm
    and 560 nm together) the 470 nm measurement is in the green columns and the 560 nm measurement is
    in the red ones, sharing a timestamp.

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
        skip_rows, state_values = self._read_state_values(file_path, state_column, read_kwargs)
        # ``value & code`` keeps only the bits set in both, so ``value & code == code`` asks "is this
        # wavelength's bit set in the row's word?", ignoring whatever else is set alongside it. Traced
        # for 415 nm (code 1 = 0b001), over the words this format actually produces:
        #     2   = 0b000000010 -> 2 & 1 == 0, no match: 470 nm alone
        #     17  = 0b000010001 -> 17 & 1 == 1, matches: a TTL bit above the excitation changes nothing
        #     273 = 0b100010001 -> 273 & 1 == 1, matches: likewise, a different TTL line
        #     6   = 0b000000110 -> 6 & 1 == 0, no match: 470 nm and 560 nm strobed together, no 415 nm
        #     7   = 0b000000111 -> 7 & 1 == 1, matches: all three strobed, so 415 nm really is present
        # Testing the wavelength's bit alone, rather than the whole masked word, is what lets a compound
        # word reach every channel it belongs to: 6 is claimed by both 470 nm (6 & 2 == 2) and 560 nm
        # (6 & 4 == 4), where an exact match on the masked word would equal neither code and drop the
        # frame from both channels. The flip side is 7: it now matches every wavelength, so an all-LEDs
        # startup frame can no longer be excluded by its label and must be dropped by position instead
        # (``skip_rows``, see :meth:`_read_state_values`).
        matching_states = [value for value in state_values if value & code == code]
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
            demux_configuration={
                "by": "column",
                "column": state_column,
                "values": matching_states,
                "skip_rows": skip_rows,
            },
            time_unit=time_unit,
            metadata_key=metadata_key,
            read_kwargs=read_kwargs,
            verbose=verbose,
        )

    @classmethod
    def get_available_excitation_wavelengths(cls, file_path: FilePath, read_kwargs: dict | None = None) -> list[int]:
        """Return the excitation wavelengths (nm) present in the file, sorted.

        A wavelength is present when any frame has its excitation bit set, so a frame that strobes two
        LEDs at once (e.g. ``LedState`` 6) reports both of them. A leading startup frame is not a
        measurement and does not contribute; see :meth:`_read_state_values`.
        """
        state_column = cls._detect_state_column(file_path, read_kwargs)
        _, state_values = cls._read_state_values(file_path, state_column, read_kwargs)
        # ``value & code == code`` is the same bit test used to select a channel in __init__: the
        # wavelength is present when its bit is set in some row's word, alone or alongside others.
        return sorted(
            wavelength
            for wavelength, code in _WAVELENGTH_TO_CODE.items()
            if any(value & code == code for value in state_values)
        )

    @staticmethod
    def _read_state_values(file_path: FilePath, state_column: str, read_kwargs: dict | None) -> tuple[int, list[int]]:
        """Return the number of leading startup frames and the sorted unique state values after them.

        Some recordings open with an initialization frame that is not a measurement: it is written with
        every excitation bit set (``7``, or ``23`` when a digital output is high alongside) while the
        frame itself is dark. Treating it as a measurement would put the same dark sample at the head of
        all three wavelength channels at once, so it is dropped. It is identified by position -- the
        first row, with all three excitation bits set -- which leaves a genuine simultaneous-excitation
        frame later in the recording untouched.
        """
        state = pd.read_csv(file_path, usecols=[state_column], **(read_kwargs or dict()))[state_column]
        # ``& _EXCITATION_BITS`` masks off the TTL bits, leaving just the three excitation flags;
        # comparing that to _EXCITATION_BITS asks whether all three are set. So 7 (0b111) and 23
        # (0b10111, one TTL line high) both read as a startup frame, while 6 (0b110) -- a genuine
        # 470 nm + 560 nm frame -- does not, and is left in place for both of those channels.
        #
        # Only the first row is tested, so an all-three-strobe frame occurring later in the recording is
        # kept and reaches all three channels, which is what such a frame means. A startup frame coded 0
        # or 16 instead of 7 needs no test at all: with no excitation bit set it matches no wavelength's
        # bit and drops out of every channel on its own.
        skip_rows = 1 if int(state.iloc[0]) & _EXCITATION_BITS == _EXCITATION_BITS else 0
        return skip_rows, sorted(int(value) for value in pd.unique(state.iloc[skip_rows:]))

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
