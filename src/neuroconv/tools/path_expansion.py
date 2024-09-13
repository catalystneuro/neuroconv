"""Helpful classes for expanding file or folder paths on a system given an f-string rule for matching patterns."""

import abc
import os
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from parse import parse
from pydantic import DirectoryPath, FilePath

from ..utils import DeepDict


class AbstractPathExpander(abc.ABC):
    """
    Abstract base class for expanding file paths and extracting metadata.

    This class provides methods to extract metadata from file paths within a directory
    and to expand paths based on a specified data specification. It is designed to be
    subclassed, with the `list_directory` method needing to be implemented by any
    subclass to provide the specific logic for listing files in a directory.
    """

    def extract_metadata(self, base_directory: DirectoryPath, format_: str):
        """
        Uses the parse library to extract metadata from file paths in the base_directory.

        This method iterates over files in `base_directory`, parsing each file path according to `format_`.
        The format string is adjusted to the current operating system's path separator. The method yields
        each file path and its corresponding parsed metadata. To constrain metadata matches to only the
        name of the file or folder/directory, the method checks that the metadata does not contain the
        OS path separator (e.g., '/' or '\\').

        Parameters
        ----------
        base_directory : DirectoryPath
            The base directory from which to list files for metadata extraction. It should be a path-like
            object that is convertible to a `pathlib.Path`.
        format_ : str
            The format string used for parsing the file paths. This string can represent a path in any
            OS format, and is adjusted internally to match the current OS's path separator.

        Yields
        ------
        tuple[Path, dict[str, Any]]
            A tuple containing the file path as a `Path` object and a dictionary of the named metadata
            extracted from the file path.
        """

        format_ = format_.replace("\\", os.sep)  # Actual character is a single back-slash; first is an escape for that
        format_ = format_.replace("/", os.sep)  # our f-string uses '/' to communicate os-independent separators

        for filepath in self.list_directory(base_directory=Path(base_directory)):
            result = parse(format_, filepath)
            if result:
                named_result = result.named
                no_field_in_metadata_contains_os_sep = all(os.sep not in str(val) for val in named_result.values())
                if no_field_in_metadata_contains_os_sep:
                    yield filepath, named_result

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

    def expand_paths(self, source_data_spec: dict[str, dict]) -> list[DeepDict]:
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

        non_standard_super = "extras"
        standard_metadata = {"session_id": "NWBFile", "session_start_time": "NWBFile", "subject_id": "Subject"}

        out = DeepDict()
        for interface, source_data in source_data_spec.items():
            base_directory = Path(source_data["base_directory"]).resolve()
            for path_type in ("file_path", "folder_path"):
                if path_type not in source_data:
                    continue

                _format = source_data[path_type]
                extracted_metadata = self.extract_metadata(base_directory, _format)
                for path, metadata in extracted_metadata:
                    key = tuple((k, v) for k, v in sorted(metadata.items()))

                    asset_path = base_directory / path

                    if path_type == "file_path" and not asset_path.is_file():
                        continue
                    if path_type == "folder_path" and not asset_path.is_dir():
                        continue

                    out[key]["source_data"][interface][path_type] = str(asset_path)

                    for meta_key, meta_val in metadata.items():
                        super_key = standard_metadata.get(meta_key, non_standard_super)
                        if meta_key == "session_start_time" and isinstance(meta_val, date):
                            meta_val = datetime(meta_val.year, meta_val.month, meta_val.day)
                        out[key]["metadata"][super_key][meta_key] = meta_val

        return list(dict(out).values())


class LocalPathExpander(AbstractPathExpander):
    """
    Class for expanding file paths and extracting metadata on a local filesystem.

    See https://neuroconv.readthedocs.io/en/main/user_guide/expand_path.html for more information.
    """

    def list_directory(self, base_directory: DirectoryPath) -> Iterable[FilePath]:  # noqa: D101
        base_directory = Path(base_directory)
        assert base_directory.is_dir(), f"The specified 'base_directory' ({base_directory}) is not a directory!"
        return (str(path.relative_to(base_directory)) for path in base_directory.rglob("*"))


def construct_path_template(path: str, *, subject_id: str, session_id: str, **metadata_kwargs) -> str:
    """
    Construct a path template by replacing specific parts of a given path with placeholders.

    This function takes a real path example and replaces the occurrences of subject ID, session ID,
    and any additional metadata values with their respective placeholders.

    Parameters
    ----------
    path : str
        The path string containing actual data that needs to be templated.
    subject_id : str
        The subject ID in the path that will be replaced with the '{subject_id}' placeholder.
    session_id : str
        The session ID in the path that will be replaced with the '{session_id}' placeholder.
    **metadata_kwargs : dict
        Additional key-value pairs where the key is the placeholder name and the value is the actual data
        in the path that should be replaced by the placeholder.

    Returns
    -------
    str
        The path string with specified parts replaced by placeholders.

    Raises
    ------
    ValueError
        If `subject_id`, `session_id`, or any value in `metadata_kwargs` is an empty string, or if `subject_id`
        or `session_id` placeholders are not found in the path.

    Examples
    --------
    >>> construct_path_template(
    >>>     "/data/subject456/session123/file.txt",
    >>>     subject_id="subject456",
    >>>     session_id="session123"
    >>> )
    '/data/{subject_id}/{session_id}/file.txt'

    >>> construct_path_template(
    >>>     "/data/subject789/session456/image.txt",
    >>>     subject_id="subject789",
    >>>     session_id="session456",
    >>>     file_type="image"
    >>> )
    '/data/{subject_id}/{session_id}/{file_type}.txt'
    """

    if subject_id == "" or session_id == "":
        raise ValueError("Subject ID and Session ID cannot be empty strings")

    if subject_id not in path or session_id not in path:
        raise ValueError("Subject ID and Session ID must be present in the path")

    format_string = path.replace(subject_id, "{subject_id}").replace(session_id, "{session_id}")

    for key, val in metadata_kwargs.items():
        if val == "":
            raise ValueError(f"Value for '{key}' cannot be an empty string")
        if val not in format_string:
            raise ValueError(f"Value for '{key}' not found in the path")
        format_string = format_string.replace(val, f"{{{key}}}")

    return format_string
