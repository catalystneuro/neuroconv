import os
from collections import defaultdict
from glob import glob
from typing import Union, Tuple

from parse import parse

from .types import FilePathType, FolderPathType


def parse_glob_directory(path: Union[FilePathType, FolderPathType], format_: str) -> Tuple:
    """Find matching paths and return those paths and extracted metadata

    Parameters
    ----------
    path: path-like
        Start the recursive search here.
    format_: str
        An f-string formatted query.

    Yields
    ------
    tuple:
        filepath: str
        metadata: dict

    """
    path = str(path)
    for filepath in glob(os.path.join(path, "**", "*"), recursive=True):
        filepath = filepath[len(path) + 1 :]
        result = parse(format_, filepath)
        if result:
            yield filepath, result.named


def _ddict():
    """Create a defaultdict of defaultdicts"""
    return defaultdict(_ddict)


def _unddict(d):
    """Turn a ddict into a normal dictionary"""
    return {key: _unddict(value) for key, value in d.items()} if isinstance(d, defaultdict) else d


def expand_paths(
        data_directory: FolderPathType,
        source_data_spec: dict,
):
    """

    Parameters
    ----------
    data_directory : path-like
        Directory where the data are. Start the recursive search here.
    source_data_spec : dict
        Source spec.
    Returns
    -------

    """
    out = _ddict()
    for interface, source_data in source_data_spec.items():
        for path_type in ("file_path", "folder_path"):
            if path_type in source_data:
                for path, metadata in parse_glob_directory(data_directory, source_data["file_path"]):
                    key = tuple(sorted(metadata.items()))
                    out[key]["source_data"][interface][path_type] = path
                    if "session_id" in metadata:
                        out[key]["metadata"]["NWBFile"]["session_id"] = metadata["session_id"]
                    if "subject_id" in metadata:
                        out[key]["metadata"]["Subject"]["subject_id"] = metadata["subject_id"]
    return list(_unddict(out).values())
