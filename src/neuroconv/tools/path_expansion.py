"""Helpful classes for expanding file or folder paths on a system given a f-string rule for matching patterns."""
import abc
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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


def generate_path_expander_ibl_demo(folder_path: Optional[str] = None) -> None:
    """
    Partially replicate the file structure of IBL data with dummy files for
    experimentation with `LocalPathExpander`. Specifically, it recreates the
    directory tree for the video files of the first three subjects of the
    Steinmetz Lab's data.

    Parameters
    ----------
    folder_path : str, optional
        Path to folder where the files are to be generated.
        If None, the current working directory will be used.
    """
    if folder_path is None:
        folder_path = Path(os.getcwd())

    IBL_TREE = [
        {
            "type": "directory",
            "name": "steinmetzlab",
            "contents": [
                {
                    "type": "directory",
                    "name": "Subjects",
                    "contents": [
                        {
                            "type": "directory",
                            "name": "NR_0017",
                            "contents": [
                                {
                                    "type": "directory",
                                    "name": "2022-03-22",
                                    "contents": [
                                        {
                                            "type": "directory",
                                            "name": "001",
                                            "contents": [
                                                {
                                                    "type": "directory",
                                                    "name": "raw_video_data",
                                                    "contents": [
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_bodyCamera.raw.2f88d70a-2172-4635-8ee9-88d9c5193aae.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_leftCamera.raw.6252a2f0-c10f-4e49-b085-75749ba29c35.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_rightCamera.raw.4472ab1c-cad8-4eca-8023-b10a4d9005fb.mp4",
                                                        },
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "type": "directory",
                            "name": "NR_0019",
                            "contents": [
                                {
                                    "type": "directory",
                                    "name": "2022-04-29",
                                    "contents": [
                                        {
                                            "type": "directory",
                                            "name": "001",
                                            "contents": [
                                                {
                                                    "type": "directory",
                                                    "name": "raw_video_data",
                                                    "contents": [
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_bodyCamera.raw.44f8c3db-45fa-4c47-aed5-fade079b6d3d.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_leftCamera.raw.9041b63e-02e2-480e-aaa7-4f6b776a647f.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_rightCamera.raw.a2d1f683-48fe-4212-b7fd-27ec21421c59.mp4",
                                                        },
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "type": "directory",
                                    "name": "2022-05-03",
                                    "contents": [
                                        {
                                            "type": "directory",
                                            "name": "001",
                                            "contents": [
                                                {
                                                    "type": "directory",
                                                    "name": "raw_video_data",
                                                    "contents": [
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_bodyCamera.raw.4dcfd4a8-8034-4832-aa93-cee3ddb97a41.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_leftCamera.raw.05576d90-6fb7-4aba-99ae-7ba63cc50a9a.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_rightCamera.raw.284fc2c3-a73e-4b86-aeac-efe8359368d9.mp4",
                                                        },
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                },
                            ],
                        },
                        {
                            "type": "directory",
                            "name": "NR_0020",
                            "contents": [
                                {
                                    "type": "directory",
                                    "name": "2022-05-08",
                                    "contents": [
                                        {
                                            "type": "directory",
                                            "name": "001",
                                            "contents": [
                                                {
                                                    "type": "directory",
                                                    "name": "raw_video_data",
                                                    "contents": [
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_bodyCamera.raw.cb0a07b5-995f-4143-9590-905af7c4a3f6.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_leftCamera.raw.1bbb8002-3f34-4d46-8bbd-f46862869f2c.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_rightCamera.raw.5ad559b2-d5ad-4768-b1f6-cb3db8ebc7e5.mp4",
                                                        },
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "type": "directory",
                                    "name": "2022-05-09",
                                    "contents": [
                                        {
                                            "type": "directory",
                                            "name": "001",
                                            "contents": [
                                                {
                                                    "type": "directory",
                                                    "name": "raw_video_data",
                                                    "contents": [
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_bodyCamera.raw.aba7e662-e45b-409b-893d-4ca827bee29a.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_leftCamera.raw.6fd084e3-93cd-439a-a655-132f1e74138d.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_rightCamera.raw.22479d80-252b-4d97-8d6e-c9bb61af3fed.mp4",
                                                        },
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "type": "directory",
                                    "name": "2022-05-10",
                                    "contents": [
                                        {
                                            "type": "directory",
                                            "name": "001",
                                            "contents": [
                                                {
                                                    "type": "directory",
                                                    "name": "raw_video_data",
                                                    "contents": [
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_bodyCamera.raw.d93f87ae-eec7-435e-9bc7-753d84f1dc98.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_leftCamera.raw.17c69b88-6aa1-4699-9837-f93b1083275d.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_rightCamera.raw.eb8c31f0-9181-421a-91c2-59dd1f027bd9.mp4",
                                                        },
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "type": "directory",
                                    "name": "2022-05-11",
                                    "contents": [
                                        {
                                            "type": "directory",
                                            "name": "001",
                                            "contents": [
                                                {
                                                    "type": "directory",
                                                    "name": "raw_video_data",
                                                    "contents": [
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_bodyCamera.raw.c282d15f-ad59-4ac7-b4c1-b68d47da91b4.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_leftCamera.raw.d5e4ed1b-c8a4-402c-a64d-803f734a8569.mp4",
                                                        },
                                                        {
                                                            "type": "file",
                                                            "name": "_iblrig_rightCamera.raw.d52f6dca-1f39-401b-8882-e0dd80df3847.mp4",
                                                        },
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                },
                            ],
                        },
                    ],
                }
            ],
        }
    ]

    def _build_tree(dir: Path, tree: list[dict]) -> None:
        """Internal recursive method to build directory tree from JSON"""
        for item in tree:
            if item["type"] == "directory":
                (dir / item["name"]).mkdir(parents=True, exist_ok=True)
                _build_tree(dir / item["name"], item["contents"])
            elif item["type"] == "file":
                (dir / item["name"]).touch()

    _build_tree(folder_path, IBL_TREE)
