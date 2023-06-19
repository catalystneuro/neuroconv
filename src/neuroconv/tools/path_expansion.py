"""Helpful classes for expanding file or folder paths on a system given a f-string rule for matching patterns."""
import abc
import os
from pathlib import Path
from typing import Dict, Iterable, List

from fparse import parse
from pydantic import DirectoryPath, FilePath

from ..utils import DeepDict


class AbstractPathExpander(abc.ABC):
    def extract_metadata(self, base_directory: DirectoryPath, format_: str):
        format_ = format_.replace("\\", os.sep)  # Actual character is a single back-slash; first is an escape for that
        format_ = format_.replace("/", os.sep)  # our f-string uses '/' to communicate os-independent separators

        for filepath in self.list_directory(base_directory=Path(base_directory)):
            result = parse(format_, filepath)
            if result:
                yield filepath, result.named

    @abc.abstractmethod
    def list_directory(self, base_directory: DirectoryPath) -> Iterable[FilePath]:
        """
        List all folders and files in a directory recursively.

        Parameters
        ----------
        base_directory : DirectoryPath
            The base directory whose contents will be iterated recursively.

        Yields
        ------
        sub_paths : iterable of strings
            Generator that yields all sub-paths of file and folders from the common root `base_directory`.
        """
        pass

    def expand_paths(self, source_data_spec: Dict[str, dict]) -> List[DeepDict]:
        """
        Match paths in a directory to specs and extract metadata from the paths.

        Parameters
        ----------
        source_data_spec : dict
            Source spec.

        Returns
        -------
        deep_dicts : list of DeepDict objects

        Examples
        --------
        >>> path_expander.expand_paths(
        ...     dict(
        ...         spikeglx=dict(
        ...             base_directory="source_folder",
        ...             paths=dict(
        ...                 file_path="sub-{subject_id}/sub-{subject_id}_ses-{session_id}"
        ...             )
        ...         )
        ...     )
        ... )
        """

        session_keys = {"session_start_time", "session_id", "subject_id"}

        out = DeepDict()
        for interface, source_data in source_data_spec.items():
            for path_type in ("file_path", "folder_path"):
                if path_type in source_data:
                    for path, metadata in self.extract_metadata(source_data["base_directory"], source_data[path_type]):
                        key = tuple((k, v) for k, v in sorted(metadata.items()) if k in session_keys)
                        out[key]["source_data"][interface][path_type] = os.path.join(
                            source_data["base_directory"], path
                        )  # return the absolute path
                        if "session_id" in metadata:
                            out[key]["metadata"]["NWBFile"]["session_id"] = metadata["session_id"]
                        if "session_start_time" in metadata:
                            out[key]["metadata"]["NWBFile"]["session_start_time"] = metadata["session_start_time"]
                        if "subject_id" in metadata:
                            out[key]["metadata"]["Subject"]["subject_id"] = metadata["subject_id"]
        return list(dict(out).values())


class LocalPathExpander(AbstractPathExpander):
    def list_directory(self, base_directory: DirectoryPath) -> Iterable[FilePath]:
        base_directory = Path(base_directory)
        assert base_directory.is_dir(), f"The specified 'base_directory' ({base_directory}) is not a directory!"
        return (str(path.relative_to(base_directory)) for path in base_directory.rglob("*"))
