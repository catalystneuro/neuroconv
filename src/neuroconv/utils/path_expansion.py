import abc
import os
from collections import defaultdict
from glob import glob
from typing import Dict, List, Union

from parse import parse

from .types import FilePathType, FolderPathType


def _ddict():
    """
    Create a defaultdict of defaultdicts

    This allows you to easily nest hierarchical dictionaries. For example, this syntax
    >>> a = dict(b=dict(c=dict(d=5)))

    becomes
    >>> a = _ddict()["b"]["c"]["d"] = 5

    It becomes particularly useful when modifying an existing hierarchical dictionary,
    because the next level is only created if it does not already exist.

    """
    return defaultdict(_ddict)


def _unddict(d):
    """Turn a ddict into a normal dictionary"""
    return {key: _unddict(value) for key, value in d.items()} if isinstance(d, defaultdict) else d


class AbstractPathExpander(abc.ABC):

    def extract_metadata(self, folder, format_: str):
        for filepath in self.list_directory(folder):
            result = parse(format_, filepath)
            if result:
                yield filepath, result.named

    @abc.abstractmethod
    def list_directory(self, folder):
        """
        List all folders and files in a directory recursively

        Yields
        ------
        str

        """
        pass

    def expand_paths(self, source_data_spec: dict) -> List[Dict]:
        """
        Match paths in a directory to specs and extract metadata from the paths.

        Parameters
        ----------
        folder
        source_data_spec : dict
            Source spec.

        Returns
        -------

        Examples
        --------
        >>> path_expander.expand_paths(
        ...     dict(
        ...         spikeglx=dict(
        ...             folder="source_folder",
        ...             paths=dict(
        ...                 file_path="sub-{subject_id}/sub-{subject_id}_ses-{session_id}"
        ...             )
        ...         )
        ...     )
        ... )

        """
        out = _ddict()
        for interface, source_data in source_data_spec.items():
            for path_type in ("file_path", "folder_path"):
                if path_type in source_data:
                    for path, metadata in self.extract_metadata(source_data["folder"], source_data[path_type]):
                        key = tuple(sorted(metadata.items()))
                        out[key]["source_data"][interface][path_type] = path
                        if "session_id" in metadata:
                            out[key]["metadata"]["NWBFile"]["session_id"] = metadata["session_id"]
                        if "subject_id" in metadata:
                            out[key]["metadata"]["Subject"]["subject_id"] = metadata["subject_id"]
        return list(_unddict(out).values())


class LocalPathExpander(AbstractPathExpander):

    def list_directory(self, folder: Union[FilePathType, FolderPathType]):
        folder_str = str(folder)
        li = glob(os.path.join(folder_str, "**", "*"), recursive=True)
        return (x[len(folder_str) + 1 :] for x in li)
