"""Reading the results tables a GuPPy run wrote before it wrote them as CSV.

Such a run writes each results table as a PyTables ``.h5`` file, and keeps trial bins in the same table
as the trials: ``bin_(a-b)``/``bin_err_(a-b)`` columns beside the trial columns of a PSTH or
cross-correlation table, and ``<session>_bin_(a-b)`` rows beside the ``<session>_<onset>`` and
``<session>_mean`` rows of a peak/AUC table. Splitting produces the tables a CSV run writes, so nothing
downstream has to know which kind of folder a table came from.

No GuPPy that writes CSV results writes these tables. See
`LernerLab/GuPPy#547 <https://github.com/LernerLab/GuPPy/pull/547>`_.
"""

import re
from pathlib import Path

import pandas

LEGACY_TABLE_SUFFIX = ".h5"
# A trial-bin label at the end of a legacy peak/AUC row label, e.g. 'guppy_example_1_bin_(0.0-1.0)'.
_LEGACY_BIN_ROW_PATTERN = re.compile(r"bin_\(\d+(?:\.\d+)?-\d+(?:\.\d+)?\)$")


def is_legacy_results_folder(folder_path: Path) -> bool:
    """Whether a GuPPy output folder holds its results tables as ``.h5`` files, which only a pre-CSV run writes."""
    return any(folder_path.glob(f"*{LEGACY_TABLE_SUFFIX}"))


def split_legacy_event_matrix(dataframe: pandas.DataFrame) -> tuple[pandas.DataFrame, pandas.DataFrame | None]:
    """Split a legacy PSTH or cross-correlation table into the table and the ``binned_`` table a CSV run writes.

    Returns the table without its bin columns, and ``timestamps`` with the ``bin_(a-b)``/``bin_err_(a-b)``
    columns, or None when GuPPy did not bin the trials.
    """
    bin_columns = [column for column in dataframe.columns if str(column).startswith("bin_")]
    event_matrix = dataframe.drop(columns=bin_columns)
    if not bin_columns:
        return event_matrix, None
    return event_matrix, dataframe[["timestamps", *bin_columns]]


def split_legacy_peak_auc(dataframe: pandas.DataFrame) -> tuple[pandas.DataFrame, pandas.DataFrame | None]:
    """Split a legacy peak/AUC table into the per-trial and per-bin tables a CSV run writes.

    A legacy row is labeled by its index: the session name joined by ``_`` to the trial's onset, to
    ``mean``, or to the bin label. The per-trial table gets ``session`` and ``trial`` columns and the
    per-bin table ``session`` and ``bin`` columns, ahead of the metric columns. The per-bin table is
    None when GuPPy did not bin the trials.
    """
    trial_rows = []
    bin_rows = []
    for label, metrics in zip(dataframe.index.astype(str), dataframe.to_dict("records")):
        bin_match = _LEGACY_BIN_ROW_PATTERN.search(label)
        if bin_match is not None:
            bin_rows.append(dict(session=label[: bin_match.start() - 1], bin=bin_match.group(0), **metrics))
        else:
            session, trial = label.rsplit("_", 1)
            trial_rows.append(dict(session=session, trial=trial, **metrics))
    binned = pandas.DataFrame(bin_rows) if bin_rows else None
    return pandas.DataFrame(trial_rows), binned
