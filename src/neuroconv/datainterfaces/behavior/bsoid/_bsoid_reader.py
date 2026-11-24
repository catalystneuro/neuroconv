"""Read the per-frame labels of a B-SOiD labels file (``labels_pose`` from the app, ``bsoid_labels`` from bsoid_umap)."""

import re
from pathlib import Path

import numpy as np
import pandas as pd

LABEL_COLUMN = "B-SOiD labels"

# The rate sits after the export name in every writer: `labels_pose_60Hz_20261116_1454_<pose file>.csv` (app 1.4),
# `<prefix>labels_pose_60Hz<pose file>.csv` (app 1.5 and later) and `bsoid_labels_60Hz_<timestamp><pose file>.csv`
# (bsoid_umap).
_SAMPLING_FREQUENCY_PATTERN = re.compile(r"(?:labels_pose|bsoid_labels)_(\d+(?:\.\d+)?)Hz")


def _get_sampling_frequency_from_file_name(file_path: Path) -> float | None:
    """Return the frame rate B-SOiD wrote into the file name, or ``None`` when the name does not carry it."""
    match = _SAMPLING_FREQUENCY_PATTERN.search(Path(file_path).name)
    return float(match.group(1)) if match else None


def _read_labels_and_frame_indices(file_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Return one label and one pose frame index per frame of a B-SOiD labels file.

    The file is the pose table B-SOiD read, with an unnamed index and the ``B-SOiD labels`` column prepended, so its
    layout follows the pose input:

    - A DeepLabCut CSV is read with its ``bodyparts`` and ``coords`` header rows as data rows, which stay in the
      file, and its ``scorer`` column holds the DeepLabCut frame index. bsoid_umap and the app of version 1.4 leave
      the label of the two header rows blank. The app of version 1.5 and later writes the labels from the first row,
      so the header rows carry the labels of the first two frames and every label sits two rows before its frame.
    - A DeepLabCut or SLEAP ``.h5`` is read as a table with no header rows, the labels line up with the frames, and
      the unnamed index holds the frame index.
    """
    table = pd.read_csv(file_path, usecols=[0, 1, 2], low_memory=False)
    index_column, label_column, first_pose_column = table.columns
    if label_column != LABEL_COLUMN:
        raise ValueError(
            f"'{file_path}' is not a B-SOiD labels file: its second column is '{label_column}', not '{LABEL_COLUMN}'. "
            "Point file_path at the `labels_pose` file of the app or the `bsoid_labels` file of bsoid_umap."
        )

    if first_pose_column != "scorer":
        return table[label_column].astype(int).to_numpy(), table[index_column].astype(int).to_numpy()

    header_rows = table[first_pose_column].iloc[:2].tolist()
    if header_rows != ["bodyparts", "coords"]:
        raise ValueError(
            f"'{file_path}' has a `scorer` column, so it was made from a DeepLabCut CSV, but its first two rows are "
            f"{header_rows}, not the `bodyparts` and `coords` header rows of a single-animal DeepLabCut CSV."
        )
    number_of_frames = len(table) - 2
    frame_indices = table[first_pose_column].iloc[2:].astype(int).to_numpy()
    header_row_labels = table[label_column].iloc[:2]
    if header_row_labels.isna().all():
        labels = table[label_column].iloc[2:]
    else:
        labels = table[label_column].iloc[:number_of_frames]
    return labels.astype(int).to_numpy(), frame_indices
