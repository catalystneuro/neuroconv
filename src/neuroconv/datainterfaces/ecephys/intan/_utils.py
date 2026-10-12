"""Internal utilities shared by the Intan interfaces."""

from __future__ import annotations

import warnings
from pathlib import Path


def _warn_if_split_siblings_detected(file_path: Path, interface_name: str) -> None:
    """
    Warn the user if ``file_path`` appears to be one chunk of a rotated session.

    Intan RHX's "Create new save file every N minutes" option produces multiple
    ``.rhd`` / ``.rhs`` files in a single session folder. Users who point a neuroconv
    Intan interface at one chunk without setting ``saved_files_are_split=True`` will
    silently convert only that chunk. This helper emits a non-fatal warning in that
    case so they can opt into concatenation.
    """
    parent = file_path.parent
    if not parent.is_dir():
        return

    suffix = file_path.suffix.lower()
    if suffix not in (".rhd", ".rhs"):
        return

    siblings = [p for p in parent.iterdir() if p.suffix.lower() == suffix and p != file_path]
    if not siblings:
        return

    warnings.warn(
        f"{interface_name}: detected {len(siblings)} other {suffix} file(s) next to {file_path.name} "
        f"in {parent}. If this is a recording saved with Intan RHX's 'new save file every N minutes' "
        "option, pass saved_files_are_split=True to concatenate all chunks.",
        UserWarning,
        stacklevel=3,
    )
