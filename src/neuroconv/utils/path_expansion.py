import abc
import os
from pathlib import Path
from typing import List, Tuple, Union

from parse import parse

from .dict import DeepDict
from .types import FilePathType, FolderPathType


class AbstractPathExpander(abc.ABC):
    def extract_metadata(self, folder, format_: str):
        format_ = format_.replace("\", os.sep)
        format_ = format_.replace("/", os.sep)  # our f-string uses '/' to communicate os-independent separators
        for filepath in self.list_directory(folder):
            result = parse(format_, filepath)
            if result:
                yield filepath, result.named

    @abc.abstractmethod
    def list_directory(self, folder: Union[FilePathType, FolderPathType]) -> Tuple[str]:
        """
        List all folders and files in a directory recursively

        Yields
        ------
        str

        """
        pass

    def expand_paths(self, source_data_spec: dict) -> List[DeepDict]:
        """
        Match paths in a directory to specs and extract metadata from the paths.

        Parameters
        ----------
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
        out = DeepDict()
        for interface, source_data in source_data_spec.items():
            for path_type in ("file_path", "folder_path"):
                if path_type in source_data:
                    for path, metadata in self.extract_metadata(source_data["folder"], source_data[path_type]):
                        key = tuple(sorted(metadata.items()))
                        out[key]["source_data"][interface][path_type] = os.path.join(
                            source_data["folder"], path
                        )  # return the absolute path
                        if "session_id" in metadata:
                            out[key]["metadata"]["NWBFile"]["session_id"] = metadata["session_id"]
                        if "subject_id" in metadata:
                            out[key]["metadata"]["Subject"]["subject_id"] = metadata["subject_id"]
        return list(dict(out).values())


class LocalPathExpander(AbstractPathExpander):
    def list_directory(self, folder: Union[FilePathType, FolderPathType]):
        return (str(path.relative_to(folder)) for path in Path(folder).rglob("*"))
