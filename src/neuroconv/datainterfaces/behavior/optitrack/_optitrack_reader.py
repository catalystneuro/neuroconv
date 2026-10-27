"""Read the header and the columns of an OptiTrack Motive CSV export."""

from pathlib import Path

import numpy as np
import pandas as pd

# Rows 3 to 7 of a Motive CSV export, after the export settings line and a blank line
# (Motive docs, "CSV Header"). Format version 1.25 adds a `Parent` row after `ID`.
_MOTIVE_HEADER_LEVELS = ("marker_type", "label", "id", "measurement_type", "axis")
_MOTIVE_HEADER_LEVELS_WITH_PARENT = ("marker_type", "label", "id", "parent", "measurement_type", "axis")


def read_header(file_path: Path) -> dict[str, str]:
    """Read the header line from a Motive CSV export.

    The first row of the file contains general information about the export, including the format version of the CSV
    export, name of the Take file, the captured frame rate, export frame rate, capture start time, capture start frame,
    number of total frames, total exported frames, rotation type, length units, and coordinate space type.

    When the header is disabled during export, this information is excluded from the CSV files. Instead, the file
    will have frame IDs in the first column, time data on the second column, and the corresponding motion capture
    data in the remaining columns.
    """
    first_line = pd.read_csv(file_path, nrows=1, header=None, dtype=str, keep_default_na=False).iloc[0].tolist()
    if first_line[0] == "comment":
        raise ValueError(
            f"'{file_path}' is in the row-typed layout of early Motive and Arena exports (one row per asset "
            "per frame, introduced by 'comment' rows), which is not supported yet. Export the take again from a "
            "current Motive version."
        )
    if "Format Version" not in first_line:
        raise ValueError(
            f"'{file_path}' does not start with the header information ('Format Version, ...'), it is either"
            f" not a Motive CSV export or it was exported with 'Header information' turned off. "
            f"Export the take again from Motive with 'Header information' enabled."
        )
    header = dict(zip(first_line[0::2], first_line[1::2]))

    return header


def read_motion_capture_data(file_path: Path) -> pd.DataFrame:
    """Read the data from a Motive CSV export.

    The second row of the file is blank, and the next five rows contain the asset header, which has five rows of information for each
    asset in the export. The five rows are: ``Type``, ``Name``, ``ID``, measurement_type, and axis. The measurement_type row
    contains the type of measurement_type for each column (e.g., position, rotation, marker), and the axis row begins with
    ``Frame``and contains the axis for each column (e.g., X, Y, Z). Format version 1.25 adds a sixth row, ``Parent``,
    after ``ID``.
    """
    with open(file_path, encoding="utf-8") as file:
        next(file)  # the export settings line
        num_header_rows = 0
        for line in file:
            if line.strip():
                num_header_rows += 1
            if line.startswith("Frame,"):
                break
    header_levels = (
        _MOTIVE_HEADER_LEVELS_WITH_PARENT
        if num_header_rows == len(_MOTIVE_HEADER_LEVELS_WITH_PARENT)
        else _MOTIVE_HEADER_LEVELS
    )
    motion_capture_data = pd.read_csv(file_path, skiprows=1, header=list(range(len(header_levels))), index_col=[0, 1])
    motion_capture_data.columns.names = header_levels
    motion_capture_data.index.names = ["frame", "time"]
    return motion_capture_data


def get_assets(motion_capture_data: pd.DataFrame) -> dict[tuple[str, str], dict[str, dict[str, np.ndarray]]]:
    """Every column of the export, as ``{(marker_type, label): {measurement_type: {axis: values}}}``, in file order.

    For example ``assets[("Rigid Body", "RigidBody")]["Position"]["X"]``.
    """
    assets = {}
    for column, values in motion_capture_data.items():
        levels = dict(zip(motion_capture_data.columns.names, column))
        asset = assets.setdefault((levels["marker_type"], levels["label"]), {})
        asset.setdefault(levels["measurement_type"], {})[levels["axis"]] = values.to_numpy(dtype=np.float64)
    return assets
