"""Decoding the store names a GuPPy NPM run wrote before it recorded what it demultiplexed.

Such a run names its stores positionally, and the ``ch<ev|od|pr>`` slot is ambiguous in that scheme:
a position in the cycle for a header-less file, an ordinal into the sorted LED states for one
carrying a state column. The file is opened to tell which. Decoding produces the record a run that
records its demultiplexing writes under ``stores`` in ``.npm_params.json``, so nothing downstream has
to know which kind of folder a store came from.

No GuPPy that records its stores writes these names. See
`LernerLab/GuPPy#507 <https://github.com/LernerLab/GuPPy/pull/507>`_.
"""

import re

from pydantic import DirectoryPath

from ._session_files import is_event_csv

# How a GuPPy run that predates the "stores" record names its NPM stores: a file index, one of
# three ordinal channel slots, and a positional column index, every part of which has to be
# reproduced to resolve. See decode_legacy_store_name.
_NPM_LEGACY_STORE_PATTERN = re.compile(r"^file(\d+)_ch(ev|od|pr)(\d+)$")
_NPM_SLOTS = ("ev", "od", "pr")
# The low three bits of an NPM state word are one flag per excitation LED; the higher bits are
# digital lines. A legacy run's slots are ordered by the whole word, so the wavelength a slot stands
# for is recovered from the bits.
_NPM_EXCITATION_CODE_TO_WAVELENGTH = {1: 415, 2: 470, 4: 560}
_NPM_EXCITATION_BITS = 0b111


def _parses_as_float(value) -> bool:
    """Return whether a column label is numeric, which is how GuPPy detects a header-less NPM file."""
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def npm_source_files(folder_path: DirectoryPath) -> list:
    """Return the folder's CSVs in the order GuPPy indexes them as ``file{N}``.

    GuPPy sorts the folder's CSVs by path and drops the files it derived itself, then indexes what
    remains. Event files are **not** dropped, so they occupy an index too and ``file{N}`` means "the
    Nth surviving CSV" rather than "the Nth data file" -- an event file that sorts early shifts every
    data file after it.
    """
    derived = set()
    for pattern in ("*chev*", "*chod*", "*chpr*", "event*"):
        derived.update(folder_path.glob(pattern))
    candidates = [path for path in sorted(folder_path.glob("*.csv")) if path not in derived]
    return [path for path in candidates if not is_event_csv(path)]


def decode_legacy_store_name(folder_path: DirectoryPath, store_id: str, timestamp_column_name) -> dict:
    """Decode what a store written before GuPPy recorded its demultiplexing was read from.

    Such a run names its stores ``file<N>_ch<ev|od|pr><column>``, where every part is positional:
    ``file<N>`` indexes :func:`npm_source_files`, ``ch<slot>`` is an ordinal into the LED states
    sorted ascending and sampled from rows 2-11 so the startup frame is skipped, and the trailing
    number indexes the columns left after GuPPy canonicalized the timestamps and dropped
    ``FrameCounter`` and the state column. The clock is positional too: the session-wide
    ``npm_timestamp_column_name`` where the run recorded one, and the file's first timestamp column
    otherwise.

    Returns the record a run that recorded its stores would have written for this one.
    """
    import numpy
    import pandas

    match = _NPM_LEGACY_STORE_PATTERN.match(store_id)
    assert match is not None, (
        f"'{store_id}' is not a GuPPy NPM store name. The run folder records no 'stores' mapping, so "
        f"its stores are expected in the older positional form 'file<N>_ch<ev|od|pr><column>'."
    )
    file_index, slot, column_position = int(match.group(1)), match.group(2), int(match.group(3))
    slot_ordinal = _NPM_SLOTS.index(slot)

    source_files = npm_source_files(folder_path)
    assert file_index < len(source_files), (
        f"Store '{store_id}' names file index {file_index}, but '{folder_path}' holds only "
        f"{len(source_files)} NPM source file(s): {[path.name for path in source_files]}."
    )
    file_path = source_files[file_index]

    dataframe = pandas.read_csv(file_path, index_col=False, nrows=12)
    headerless = any(_parses_as_float(column) for column in dataframe.columns)
    if headerless:
        return dict(
            file=file_path.name,
            excitation_wavelength_in_nm=None,
            interleave_position=slot_ordinal,
            data_column=column_position,
            # Nothing names these columns, so the timestamps are the leading one.
            timestamp_column=0,
        )

    column_by_lowercase_name = {str(column).lower(): column for column in dataframe.columns}
    state_column = column_by_lowercase_name.get("flags") or column_by_lowercase_name.get("ledstate")
    assert state_column is not None, (
        f"'{file_path}' has a header but no 'Flags' or 'LedState' column, so GuPPy could not have "
        f"demultiplexed it into '{store_id}'."
    )
    state = pandas.read_csv(file_path, index_col=False)[state_column].to_numpy().astype(int)
    unique_states = numpy.unique(state[2:12])
    assert slot_ordinal < len(unique_states), (
        f"Store '{store_id}' names channel slot '{slot}' (index {slot_ordinal}), but '{file_path}' "
        f"interleaves only {len(unique_states)} channel(s) (states {unique_states.tolist()})."
    )
    state_value = int(unique_states[slot_ordinal])
    excitation_code = state_value & _NPM_EXCITATION_BITS
    assert excitation_code in _NPM_EXCITATION_CODE_TO_WAVELENGTH, (
        f"Store '{store_id}' was demultiplexed from NPM state {state_value}, whose excitation bits "
        f"({excitation_code:#05b}) are not a single wavelength. GuPPy treated such a frame as its own "
        f"channel, but a fiber photometry series is written per excitation."
    )

    # Reproduce GuPPy's column trimming: the canonical timestamps column replaced the several it
    # found (only when there were several), then FrameCounter and the state column went.
    timestamp_columns = [column for column in dataframe.columns if "timestamp" in str(column).lower()]
    remaining = list(dataframe.columns)
    if len(timestamp_columns) > 1:
        remaining.insert(1, "Timestamp")
        remaining = [column for column in remaining if column not in timestamp_columns]
    remaining = [
        column for column in remaining if column not in (column_by_lowercase_name.get("framecounter"), state_column)
    ]
    assert column_position < len(remaining), (
        f"Store '{store_id}' names column position {column_position}, but '{file_path}' leaves only "
        f"{len(remaining)} column(s) after GuPPy's trimming: {remaining}."
    )
    return dict(
        file=file_path.name,
        excitation_wavelength_in_nm=_NPM_EXCITATION_CODE_TO_WAVELENGTH[excitation_code],
        interleave_position=None,
        data_column=remaining[column_position],
        timestamp_column=timestamp_column_name or (timestamp_columns[0] if timestamp_columns else None),
    )
