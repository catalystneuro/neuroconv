import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....utils import DeepDict


class DeepLabCutInterface(BaseTemporalAlignmentInterface):
    """Data interface for DeepLabCut datasets."""

    display_name = "DeepLabCut"
    keywords = ("DLC", "DeepLabCut", "pose estimation", "behavior")
    associated_suffixes = (".h5", ".csv")
    info = "Interface for handling data from DeepLabCut."

    _timestamps = None

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the file output by dlc (.h5 or .csv)."
        source_schema["properties"]["config_file_path"]["description"] = "Path to .yml config file."
        return source_schema

    def get_available_subjects(file_path: FilePath) -> list[str]:
        """
        Extract available subjects from a DeepLabCut output file.

        Parameters
        ----------
        file_path : FilePath
            Path to the DeepLabCut output file (.h5 or .csv).

        Returns
        -------
        list[str]
            List of subject names found in the file.

        Raises
        ------
        IOError
            If the file is not a valid DeepLabCut output file.
        FileNotFoundError
            If the file does not exist.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File {file_path} does not exist.")

        # Read the data
        if ".h5" in file_path.suffixes:
            df = pd.read_hdf(file_path)
        elif ".csv" in file_path.suffixes:
            df = pd.read_csv(file_path, header=[0, 1, 2], index_col=0)
        else:
            raise IOError(f"The file {file_path} passed in is not a valid DeepLabCut output data file.")

        # Check if 'individuals' level exists in the column structure
        if "individuals" in df.columns.names:
            # Multi-subject file - extract unique individuals
            individuals = df.columns.get_level_values("individuals").unique().tolist()
            return individuals
        else:
            # Single-subject file - return default subject name
            # For consistency with the interface's default behavior
            return ["ind1"]

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        config_file_path: FilePath | None = None,
        subject_name: str = "ind1",
        pose_estimation_metadata_key: str = "PoseEstimationDeepLabCut",
        verbose: bool = False,
    ):
        """
        Interface for writing DeepLabCut's output files to NWB.

        This interface reads DeepLabCut output files (.h5 or .csv) and converts them to NWB format
        using the ndx-pose extension. It extracts keypoints (bodyparts), their coordinates, and confidence
        values, and organizes them into a structured format within the NWB file.

        Parameters
        ----------
        file_path : FilePath
            Path to the file output by DeepLabCut (.h5 or .csv). The file should contain the pose estimation
            data with keypoints, coordinates, and confidence values.
        config_file_path : FilePath, optional
            Path to the DeepLabCut .yml config file. If provided, additional metadata such as video dimensions,
            task description, and experimenter information will be extracted.
        subject_name : str, default: "ind1"
            The subject name to be used in the metadata. For output files with multiple individuals,
            this must match the name of the individual for which the data will be added. This name is also
            used to link the skeleton to the subject in the NWB file.
        pose_estimation_metadata_key : str, default: "PoseEstimationDeepLabCut"
            This controls where in the metadata the pose estimation metadata is stored:
            metadata["PoseEstimation"]["PoseEstimationContainers"][pose_estimation_metadata_key].
            This key is also used as the name of the PoseEstimation container in the NWB file.
        verbose : bool, default: False
            Controls verbosity of the conversion process.


        Metadata Structure
        ------------------
        The metadata is organized in a hierarchical structure:

        .. code-block:: python

            metadata = {
                "PoseEstimation": {
                    "Skeletons": {
                        "skeleton_name": {
                            "name": "SkeletonPoseEstimationDeepLabCut_SubjectName",
                            "nodes": ["bodypart1", "bodypart2", ...],  # List of keypoints/bodyparts
                            "edges": [[0, 1], [1, 2], ...],  # Connections between nodes (optional)
                            "subject": "subject_name"  # Links the skeleton to the subject
                        }
                    },
                    "Devices": {
                        "device_name": {
                            "name": "CameraPoseEstimationDeepLabCut",
                            "description": "Camera used for behavioral recording and pose estimation."
                        }
                    },
                    "PoseEstimationContainers": {
                        "pose_estimation_metadata_key": {
                            "name": "PoseEstimationDeepLabCut",
                            "description": "2D keypoint coordinates estimated using DeepLabCut.",
                            "source_software": "DeepLabCut",
                            "devices": ["device_name"],  # References to devices
                            "PoseEstimationSeries": {
                                "PoseEstimationSeriesBodyPart1": {
                                    "name": "bodypart1",
                                    "description": "Keypoint bodypart1.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network."
                                },
                                "PoseEstimationSeriesBodyPart2": {
                                    "name": "bodypart2",
                                    "description": "Keypoint bodypart2.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network."
                                }
                                # And so on for each bodypart
                            }
                        }
                    }
                }
            }

        The metadata can be customized by:

        #. Calling get_metadata() to retrieve the default metadata
        #. Modifying the returned dictionary as needed
        #. Passing the modified metadata to add_to_nwbfile() or run_conversion()

        See also our `Conversion Gallery <https://neuroconv.readthedocs.io/en/main/conversion_examples_gallery/behavior/deeplabcut.html>`_
        for more examples using DeepLabCut data.

        Notes
        -----
        - When the subject_name matches a subject_id in the NWBFile, the skeleton will be automatically
        linked to that subject.
        """
        # This import is to assure that the ndx_pose is in the global namespace when an pynwb.io object is created
        from importlib.metadata import version

        import ndx_pose  # noqa: F401
        from packaging import version as version_parse

        ndx_pose_version = version("ndx-pose")
        if version_parse.parse(ndx_pose_version) < version_parse.parse("0.2.0"):
            raise ImportError(
                "DeepLabCut interface requires ndx-pose version 0.2.0 or later. "
                f"Found version {ndx_pose_version}. Please upgrade: "
                "pip install 'ndx-pose>=0.2.0'"
            )

        from ._dlc_utils import _read_config

        file_path = Path(file_path)
        suffix_is_valid = ".h5" in file_path.suffixes or ".csv" in file_path.suffixes
        if not "DLC" in file_path.stem or not suffix_is_valid:
            raise IOError("The file passed in is not a valid DeepLabCut output data file.")

        self.config_dict = dict()
        if config_file_path is not None:
            self.config_dict = _read_config(config_file_path=config_file_path)
        self.subject_name = subject_name
        self.verbose = verbose
        self.pose_estimation_metadata_key = pose_estimation_metadata_key
        self.pose_estimation_container_kwargs = dict()

        super().__init__(file_path=file_path, config_file_path=config_file_path)

    def get_metadata_schema(self) -> dict:
        """
        Retrieve JSON schema for metadata specific to the DeepLabCutInterface.

        Returns
        -------
        dict
            The JSON schema defining the metadata structure.
        """
        from ....utils import get_base_schema

        metadata_schema = super().get_metadata_schema()

        # Define the schema for PoseEstimation metadata
        metadata_schema["properties"]["PoseEstimation"] = get_base_schema(tag="PoseEstimation")

        # Add Skeletons schema
        skeleton_schema = get_base_schema(tag="Skeletons")
        skeleton_schema["additionalProperties"] = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the skeleton"},
                "nodes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of node names (bodyparts)",
                },
                "edges": {
                    "type": ["array", "null"],
                    "items": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "description": "List of edges connecting nodes, each edge is a pair of node indices",
                },
                "subject": {
                    "type": ["string", "null"],
                    "description": "Subject ID associated with this skeleton",
                },
            },
            "required": ["name", "nodes"],
        }

        # Add Devices schema
        devices_schema = get_base_schema(tag="Devices")
        devices_schema["additionalProperties"] = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the device",
                },
                "description": {
                    "type": "string",
                    "description": "Description of the device",
                },
            },
            "required": ["name"],
        }

        # Add PoseEstimationContainers schema
        containers_schema = get_base_schema(tag="PoseEstimationContainers")
        containers_schema["additionalProperties"] = {
            "type": "object",
            "description": "Metadata for a PoseEstimation group corresponding to one subject/session",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the PoseEstimation group",
                    "default": "PoseEstimationDeepLabCut",
                },
                "description": {
                    "type": ["string", "null"],
                    "description": "Description of the pose estimation procedure and output",
                },
                "source_software": {
                    "type": ["string", "null"],
                    "description": "Name of the software tool used",
                    "default": "DeepLabCut",
                },
                "source_software_version": {
                    "type": ["string", "null"],
                    "description": "Version string of the software tool used",
                },
                "scorer": {
                    "type": ["string", "null"],
                    "description": "Name of the scorer or algorithm used",
                },
                "dimensions": {
                    "type": ["array", "null"],
                    "description": "Dimensions [height, width] of the labeled video(s)",
                    "items": {"type": "array", "items": {"type": "integer"}},
                },
                "original_videos": {
                    "type": ["array", "null"],
                    "description": "Paths to the original video files",
                    "items": {"type": "string"},
                },
                "labeled_videos": {
                    "type": ["array", "null"],
                    "description": "Paths to the labeled video files",
                    "items": {"type": "string"},
                },
                "skeleton": {
                    "type": ["string", "null"],
                    "description": "Reference to a Skeleton defined in Skeletons",
                },
                "devices": {
                    "type": ["array", "null"],
                    "description": "References to Device objects used to record the videos",
                    "items": {"type": "string"},
                },
                "PoseEstimationSeries": {
                    "type": ["object", "null"],
                    "description": "Dictionary of PoseEstimationSeries, one per body part",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": ["string", "null"],
                                "description": "Name for this series, typically the body part",
                            },
                            "description": {
                                "type": ["string", "null"],
                                "description": "Description for this specific series",
                            },
                            "unit": {
                                "type": ["string", "null"],
                                "description": "Unit of measurement (default: pixels)",
                                "default": "pixels",
                            },
                            "reference_frame": {
                                "type": ["string", "null"],
                                "description": "Description of the reference frame",
                                "default": "(0,0) corresponds to the bottom left corner of the video.",
                            },
                            "confidence_definition": {
                                "type": ["string", "null"],
                                "description": "How the confidence was computed (e.g., Softmax output)",
                                "default": "Softmax output of the deep neural network.",
                            },
                        },
                        "required": ["name"],
                    },
                },
            },
            "required": ["name"],
        }

        # Add all schemas to the PoseEstimation schema
        metadata_schema["properties"]["PoseEstimation"]["properties"] = {
            "Skeletons": skeleton_schema,
            "Devices": devices_schema,
            "PoseEstimationContainers": containers_schema,
        }

        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        if self.config_dict:
            metadata["NWBFile"].update(
                session_description=self.config_dict["Task"],
                experimenter=[self.config_dict["scorer"]],
            )

        # Extract information from the DeepLabCut data
        file_path = self.source_data["file_path"]

        # Read the data to extract bodyparts
        if ".h5" in Path(file_path).suffixes:
            df = pd.read_hdf(file_path)
        elif ".csv" in Path(file_path).suffixes:
            df = pd.read_csv(file_path, header=[0, 1, 2], index_col=0)

        # Ensure individuals in header if needed
        from ._dlc_utils import _ensure_individuals_in_header

        df = _ensure_individuals_in_header(df, self.subject_name)

        # Extract bodyparts and individuals
        bodyparts = df.columns.get_level_values("bodyparts").unique().tolist()
        individuals = df.columns.get_level_values("individuals").unique().tolist()

        # Get video dimensions from config if available
        dimensions = None
        if self.source_data.get("config_file_path"):
            from ._dlc_utils import _get_video_info_from_config_file

            video_name = Path(file_path).stem.split("DLC")[0]
            _, image_shape = _get_video_info_from_config_file(
                config_file_path=self.source_data["config_file_path"], vidname=video_name
            )
            # Parse dimensions from image_shape (format: "0, width, 0, height")
            try:
                shape_parts = [int(x.strip()) for x in image_shape.split(",")]
                if len(shape_parts) == 4:
                    dimensions = [[shape_parts[3], shape_parts[1]]]  # [[height, width]]
            except (ValueError, IndexError):
                pass

        # Get edges from metadata pickle file if available
        edges = []
        try:
            from ._dlc_utils import _get_graph_edges

            filename = str(Path(file_path).parent / Path(file_path).stem)
            for i, c in enumerate(filename[::-1]):
                if c.isnumeric():
                    break
            if i > 0:
                filename = filename[:-i]

            metadata_file_path = Path(filename + "_meta.pickle")
            edges = _get_graph_edges(metadata_file_path=metadata_file_path)
        except Exception:
            pass

        # Create default PoseEstimation metadata
        container_name = self.pose_estimation_metadata_key
        skeleton_name = f"Skeleton{container_name}_{self.subject_name.capitalize()}"
        device_name = f"Camera{container_name}"

        # Create PoseEstimation metadata structure
        pose_estimation_metadata = DeepDict()

        # Add Skeleton as a dictionary
        pose_estimation_metadata["Skeletons"] = {
            skeleton_name: {"name": skeleton_name, "nodes": bodyparts, "edges": edges, "subject": self.subject_name}
        }

        # Add Device as a dictionary
        pose_estimation_metadata["Devices"] = {
            device_name: {
                "name": device_name,
                "description": "Camera used for behavioral recording and pose estimation.",
            }
        }

        # Extract video name and scorer
        video_name, scorer = Path(file_path).stem.split("DLC")
        scorer = "DLC" + scorer

        # Get video info from config file if available
        video_file_path = None
        image_shape = "0, 0, 0, 0"

        if self.source_data.get("config_file_path"):
            from ._dlc_utils import _get_video_info_from_config_file

            video_file_path, image_shape = _get_video_info_from_config_file(
                config_file_path=self.source_data["config_file_path"], vidname=video_name
            )

        # Add PoseEstimation container
        pose_estimation_metadata["PoseEstimationContainers"] = {
            container_name: {
                "name": container_name,
                "description": "2D keypoint coordinates estimated using DeepLabCut.",
                "source_software": "DeepLabCut",
                "dimensions": dimensions,
                "skeleton": skeleton_name,
                "devices": [device_name],
                "scorer": scorer,
                "original_videos": [video_file_path] if video_file_path else None,
                "PoseEstimationSeries": {},
            }
        }

        # Add a series for each bodypart
        for bodypart in bodyparts:
            pose_estimation_metadata["PoseEstimationContainers"][container_name]["PoseEstimationSeries"][bodypart] = {
                "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                "description": f"Pose estimation series for {bodypart}.",
                "unit": "pixels",
                "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                "confidence_definition": "Softmax output of the deep neural network.",
            }

        # Add PoseEstimation metadata to the main metadata
        metadata["PoseEstimation"] = pose_estimation_metadata

        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to retrieve the original unaltered timestamps for this interface! "
            "Define the `get_original_timestamps` method for this interface."
        )

    def get_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to retrieve timestamps for this interface! Define the `get_timestamps` method for this interface."
        )

    def set_aligned_timestamps(self, aligned_timestamps: list | np.ndarray):
        """
        Set aligned timestamps vector for DLC data with user defined timestamps

        Parameters
        ----------
        aligned_timestamps : list, np.ndarray
            A timestamps vector.
        """
        self._timestamps = np.asarray(aligned_timestamps)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        container_name: str | None = None,
    ):
        """
        Conversion from DLC output files to nwb. Derived from dlc2nwb library.

        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict
            metadata info for constructing the nwb file (optional).
        container_name: str, default: None
            name of the PoseEstimation container in the nwb. If None, uses the container_name from the interface.
            This parameter is deprecated and will be removed on or after October 2025.
            Use the pose_estimation_metadata_key parameter when initializing the interface instead to specify
            the content of the metadata.

        """
        from ._dlc_utils import (
            _add_pose_estimation_to_nwbfile,
            _ensure_individuals_in_header,
        )

        # Use the pose_estimation_metadata_key from the instance if container_name not provided
        if container_name is not None:
            warnings.warn(
                "The container_name parameter in add_to_nwbfile is deprecated and will be removed on or after October 2025. "
                "Use the pose_estimation_metadata_key parameter when initializing the interface instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            pose_estimation_metadata_key = container_name
        else:
            pose_estimation_metadata_key = self.pose_estimation_metadata_key

        # Get default metadata
        default_metadata = DeepDict(self.get_metadata())

        # Update with user-provided metadata if available
        if metadata is not None:
            default_metadata.deep_update(metadata)

        # Set the container name in the metadata, remove this once container_name is deprecated
        if container_name is not None:
            if (
                "PoseEstimation" in default_metadata
                and "PoseEstimationContainers" in default_metadata["PoseEstimation"]
            ):
                if container_name in default_metadata["PoseEstimation"]["PoseEstimationContainers"]:
                    default_metadata["PoseEstimation"]["PoseEstimationContainers"][container_name][
                        "name"
                    ] = container_name
                else:
                    # If the container doesn't exist in the metadata, create it with the name
                    default_metadata["PoseEstimation"]["PoseEstimationContainers"][container_name] = {
                        "name": container_name
                    }

        file_path = Path(self.source_data["file_path"])

        # Read the data
        if ".h5" in file_path.suffixes:
            df = pd.read_hdf(file_path)
        elif ".csv" in file_path.suffixes:
            df = pd.read_csv(file_path, header=[0, 1, 2], index_col=0)

        # Ensure individuals in header
        df = _ensure_individuals_in_header(df, self.subject_name)

        # Get timestamps
        timestamps = self._timestamps
        if timestamps is None:
            timestamps = df.index.tolist()  # Use index as dummy timestamps if not provided

        df_animal = df.xs(self.subject_name, level="individuals", axis=1)

        _add_pose_estimation_to_nwbfile(
            nwbfile=nwbfile,
            df_animal=df_animal,
            timestamps=timestamps,
            exclude_nans=False,
            metadata=default_metadata,
            pose_estimation_metadata_key=pose_estimation_metadata_key,
        )
