import os
from collections import defaultdict
from glob import glob
from typing import Union

from parse import parse

from neuroconv.utils import FilePathType, FolderPathType


def parse_glob_directory(
    path: Union[FilePathType, FolderPathType],
    format_: str
):
    """Find matching paths and return those paths and extracted metadata

    Parameters
    ----------
    path: path-like
        Start the recursive search here.
    format_: str
        An f-string formatted query.

    Returns
    -------

    """
    path = str(path)
    for filepath in glob(os.path.join(path, "**", "*"), recursive=True):
        filepath = filepath[len(path) + 1 :]
        result = parse(format_, filepath)
        if result:
            yield filepath, result.named


def ddict():
    """Create a defaultdict of defaultdicts"""
    return defaultdict(ddict)


def unddict(d):
    """Turn a ddict into a normal dictionary"""
    if isinstance(d, defaultdict):
        return {key: unddict(value) for key, value in d.items()}
    else:
        return d


def unpack_experiment_dynamic_paths(
    data_directory: FolderPathType,
    source_data_spec: dict,
):
    """

    Parameters
    ----------
    data_directory : path-like
        Directory where the data are. Start the resursive search here.
    source_data_spec : dict
        Source spec.
    Returns
    -------

    """
    out = ddict()
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
    return list(unddict(out).values())
