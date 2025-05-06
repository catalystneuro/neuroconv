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

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        config_file_path: FilePath | None = None,
        subject_name: str = "ind1",
        verbose: bool = False,
        container_name: str = "PoseEstimationDeepLabCut",
    ):
        """
        Interface for writing DLC's output files to nwb using dlc2nwb.

        Parameters
        ----------
        file_path : FilePath
            Path to the file output by dlc (.h5 or .csv).
        config_file_path : FilePath, optional
            Path to .yml config file
        subject_name : str, default: "ind1"
            The name of the subject for which the :py:class:`~pynwb.file.NWBFile` is to be created.
        verbose: bool, default: True
            Controls verbosity.
        container_name: str, default: "PoseEstimationDeepLabCut"
            Name of the PoseEstimation container in the NWB file.
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
        self.container_name = container_name
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

        # Create a dynamic skeleton name based on the subject name
        skeleton_name = f"SkeletonPoseEstimationDeepLabCut_{self.subject_name.capitalize()}"

        skeleton_schema["properties"] = {
            skeleton_name: {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the skeleton", "default": skeleton_name},
                    "nodes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of node names (bodyparts)",
                    },
                    "edges": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                        "description": "List of edges connecting nodes, each edge is a pair of node indices",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Subject ID associated with this skeleton",
                        "default": self.subject_name,
                    },
                },
                "required": ["name", "nodes"],
            }
        }

        # Allow additional properties in the Skeletons schema
        skeleton_schema["additionalProperties"] = True

        # Add Devices schema
        devices_schema = get_base_schema(tag="Devices")
        devices_schema["properties"] = {
            "CameraPoseEstimationDeepLabCut": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the device",
                        "default": "CameraPoseEstimationDeepLabCut",
                    },
                    "description": {"type": "string", "description": "Description of the device"},
                    "compression": {"type": "string", "description": "Compression format used by the camera"},
                    "deviceType": {"type": "string", "description": "Type of the device"},
                },
                "required": ["name"],
            }
        }

        # Add PoseEstimationContainers schema
        containers_schema = get_base_schema(tag="PoseEstimationContainers")
        containers_schema["properties"] = {
            self.container_name: {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the PoseEstimation container",
                        "default": self.container_name,
                    },
                    "description": {"type": "string", "description": "Description of the pose estimation data"},
                    "source_software": {
                        "type": "string",
                        "description": "Software used to generate the pose estimation data",
                        "default": "DeepLabCut",
                    },
                    "dimensions": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Dimensions of the video [height, width]",
                    },
                    "skeleton": {"type": "string", "description": "Reference to a skeleton defined in Skeletons"},
                    "devices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "References to devices defined in Devices",
                    },
                    "PoseEstimationSeries": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Name for this specific series"},
                                "description": {
                                    "type": "string",
                                    "description": "Description for this specific series",
                                },
                                "unit": {
                                    "type": "string",
                                    "description": "Unit for this specific series",
                                    "default": "pixels",
                                },
                                "reference_frame": {
                                    "type": "string",
                                    "description": "Reference frame for this specific series",
                                    "default": "(0,0) corresponds to the bottom left corner of the video.",
                                },
                                "confidence_definition": {
                                    "type": "string",
                                    "description": "Definition of the confidence values",
                                    "default": "Softmax output of the deep neural network.",
                                },
                            },
                        },
                        "description": "Dictionary of pose estimation series, one for each bodypart",
                    },
                },
                "required": ["name"],
            }
        }

        # Allow additional properties in the PoseEstimationContainers schema
        containers_schema["additionalProperties"] = True

        # Add all schemas to the PoseEstimation schema
        metadata_schema["properties"]["PoseEstimation"]["properties"] = {
            "Skeletons": skeleton_schema,
            "Devices": devices_schema,
            "PoseEstimationContainers": containers_schema,
        }

        return metadata_schema

    def get_metadata(self):
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
        dimensions = [0, 0]
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
                    dimensions = [shape_parts[3], shape_parts[1]]  # [height, width]
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
        container_name = self.container_name
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
                "name": f"{self.subject_name}_{bodypart}",
                "description": f"Keypoint {bodypart} from individual {self.subject_name}.",
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
            Use the container_name parameter when initializing the interface instead.

        """
        import warnings

        # Use the container_name from the instance if not provided
        if container_name is None:
            container_name = self.container_name
        else:
            warnings.warn(
                "The container_name parameter in add_to_nwbfile is deprecated and will be removed on or after October 2025. "
                "Use the container_name parameter when initializing the interface instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        from pathlib import Path

        import pandas as pd

        from ._dlc_utils import _ensure_individuals_in_header, _write_pes_to_nwbfile

        # Get default metadata
        default_metadata = DeepDict(self.get_metadata())

        # Update with user-provided metadata if available
        if metadata is not None:
            default_metadata.deep_update(metadata)

        # Set the container name in the metadata
        if "PoseEstimation" in default_metadata and "PoseEstimationContainers" in default_metadata["PoseEstimation"]:
            if container_name in default_metadata["PoseEstimation"]["PoseEstimationContainers"]:
                default_metadata["PoseEstimation"]["PoseEstimationContainers"][container_name]["name"] = container_name
            else:
                # If the container doesn't exist in the metadata, create it with the name
                default_metadata["PoseEstimation"]["PoseEstimationContainers"][container_name] = {
                    "name": container_name
                }

        # Process the DLC file
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

        # Extract data for the subject
        df_animal = df.xs(self.subject_name, level="individuals", axis=1)

        # Write to NWB file
        _write_pes_to_nwbfile(
            nwbfile=nwbfile,
            df_animal=df_animal,
            timestamps=timestamps,
            exclude_nans=False,
            metadata=default_metadata,
        )
