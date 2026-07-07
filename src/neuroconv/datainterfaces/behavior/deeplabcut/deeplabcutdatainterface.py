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
        *args,  # TODO: change to * (keyword only) on or after August 2026
        config_file_path: FilePath | None = None,
        subject_name: str = "ind1",
        pose_estimation_metadata_key: str | None = None,
        verbose: bool = False,
        metadata_key: str | None = None,
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
        pose_estimation_metadata_key : str, optional
            Deprecated. Renamed to ``metadata_key``; passing it forwards the value to ``metadata_key``
            and will be removed on or after December 2026. Passing both raises ``ValueError``.
        verbose : bool, default: False
            Controls verbosity of the conversion process.
        metadata_key : str, optional
            The registry key under which this interface's metadata is stored in the dict-based format.
            When ``None`` it resolves to a default (``"deep_lab_cut_metadata_key"``). The key is an
            internal handle and does not appear in the NWB file; rename NWB objects via their ``name``
            fields in the metadata dict instead. To opt into the dict-based shape, call
            ``get_metadata(use_new_metadata_format=True)``.


        Metadata Structure
        ------------------
        With ``use_new_metadata_format=True`` the metadata follows the unified, dict-based layout: a
        shared top-level ``Devices`` registry plus the pose registries nested under
        ``metadata["Behavior"]["Pose"]``, cross-referenced by key.

        .. code-block:: python

            metadata = {
                "Devices": {
                    "deep_lab_cut_metadata_key": {  # registry key (snake_case, never written to the file)
                        "name": "CameraPoseEstimationDeepLabCut",
                        "description": "Camera used for behavioral recording and pose estimation.",
                    }
                },
                "Behavior": {
                    "Pose": {
                        "Skeletons": {
                            "deep_lab_cut_metadata_key": {
                                "name": "SkeletonPoseEstimationDeepLabCut_SubjectName",
                                "nodes": ["bodypart1", "bodypart2", ...],  # keypoints/bodyparts
                                "edges": [[0, 1], [1, 2], ...],  # connections between nodes (optional)
                                "subject": "subject_name",  # links the skeleton to the subject
                            }
                        },
                        "PoseEstimations": {
                            "deep_lab_cut_metadata_key": {  # keyed by metadata_key
                                "name": "PoseEstimationDeepLabCut",
                                "source_software": "DeepLabCut",
                                "scorer": "...",
                                "dimensions": [[height, width]],
                                "original_videos": ["path/to/video.mp4"],
                                "device_metadata_key": "deep_lab_cut_metadata_key",  # -> metadata["Devices"]
                                "skeleton_metadata_key": "deep_lab_cut_metadata_key",  # -> Behavior.Pose.Skeletons
                                "PoseEstimationSeries": {
                                    "bodypart1": {"name": "PoseEstimationSeriesBodypart1"},
                                    "bodypart2": {"name": "PoseEstimationSeriesBodypart2"},
                                    # one entry per bodypart; the dict key is the bodypart name
                                },
                            }
                        },
                    }
                },
            }

        The registry key (``deep_lab_cut_metadata_key`` above) is an internal handle that never appears in
        the NWB file; rename NWB objects through their ``name`` fields instead. ``get_metadata`` emits only
        values extracted from the DeepLabCut source plus the object ``name``s; per-series defaults
        (``description``, ``unit``, ``reference_frame``, ``confidence_definition``) are applied by the writer
        at write time, so set them here only to override.

        The metadata can be customized by:

        #. Calling ``get_metadata(use_new_metadata_format=True)`` to retrieve the default metadata
        #. Modifying the returned dictionary as needed
        #. Passing the modified metadata to add_to_nwbfile() or run_conversion()

        See also our `Conversion Gallery <https://neuroconv.readthedocs.io/en/main/conversion_examples_gallery/behavior/deeplabcut.html>`_
        for more examples using DeepLabCut data.

        Notes
        -----
        - When the subject_name matches a subject_id in the NWBFile, the skeleton will be automatically
        linked to that subject.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "config_file_path",
                "subject_name",
                "pose_estimation_metadata_key",
                "verbose",
            ]
            num_positional_args_before_args = 1  # file_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to DeepLabCutInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            config_file_path = positional_values.get("config_file_path", config_file_path)
            subject_name = positional_values.get("subject_name", subject_name)
            pose_estimation_metadata_key = positional_values.get(
                "pose_estimation_metadata_key", pose_estimation_metadata_key
            )
            verbose = positional_values.get("verbose", verbose)

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
        if not suffix_is_valid:
            raise IOError(
                "The file passed in is not a valid DeepLabCut output data file. Only .h5 and .csv are supported."
            )

        if metadata_key is not None and pose_estimation_metadata_key is not None:
            raise ValueError(
                "Pass only 'metadata_key'. 'pose_estimation_metadata_key' has been renamed to "
                "'metadata_key' and the two cannot be combined."
            )
        if pose_estimation_metadata_key is not None:
            warnings.warn(
                "The 'pose_estimation_metadata_key' argument has been renamed to 'metadata_key' and "
                "will be removed on or after December 2026. Please use 'metadata_key' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            metadata_key = pose_estimation_metadata_key

        self.config_dict = dict()
        if config_file_path is not None:
            self.config_dict = _read_config(config_file_path=config_file_path)
        self.subject_name = subject_name
        self.verbose = verbose
        self.metadata_key = metadata_key
        self.pose_estimation_container_kwargs = dict()

        super().__init__(file_path=file_path, config_file_path=config_file_path)

    def get_metadata_schema(self, *, use_new_metadata_format: bool = False) -> dict:
        """
        Retrieve JSON schema for metadata specific to the DeepLabCutInterface.

        Returns
        -------
        dict
            The JSON schema defining the metadata structure.
        """
        # Canonical (dict-based) shape: top-level Devices and Behavior.Pose.* validate against the
        # base metadata schema, which permits these additional registries. The legacy
        # ``metadata["PoseEstimation"]`` schema is selected while ``use_new_metadata_format`` is False.
        if not use_new_metadata_format:
            return self._get_metadata_schema_old_format()
        return super().get_metadata_schema()

    def _get_metadata_schema_old_format(self) -> dict:
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

    def get_metadata(self, *, use_new_metadata_format: bool = False) -> DeepDict:
        from ._dlc_utils import (
            _ensure_individuals_in_header,
            _get_graph_edges,
            _get_video_info_from_config_file,
        )

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
        df = _ensure_individuals_in_header(df, self.subject_name)

        # Extract bodyparts and individuals
        bodyparts = df.columns.get_level_values("bodyparts").unique().tolist()

        # Get video dimensions from config if available
        dimensions = None
        if self.source_data.get("config_file_path"):
            video_name = Path(file_path).stem.split("DLC")[0]
            _, image_shape = _get_video_info_from_config_file(
                config_file_path=self.source_data["config_file_path"], vidname=video_name
            )
            try:
                shape_parts = [int(x.strip()) for x in image_shape.split(",")]
                if len(shape_parts) == 4:
                    dimensions = [[shape_parts[3], shape_parts[1]]]  # [[height, width]]
            except (ValueError, IndexError):
                pass

        # Get edges from metadata pickle file if available
        edges = []
        try:
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

        # Extract video name and scorer
        # If filename contains "DLC", split on it to get video name
        # Otherwise, use the full stem as video name
        file_stem = Path(file_path).stem
        if "DLC" in file_stem:
            video_name, scorer = Path(file_path).stem.split("DLC")
            scorer = "DLC" + scorer
        else:
            video_name = file_stem
            # Extract scorer from DataFrame header
            scorer = df.columns.get_level_values("scorer")[0]

        # Get video info from config file if available
        video_file_path = None
        if self.source_data.get("config_file_path"):
            video_file_path, _ = _get_video_info_from_config_file(
                config_file_path=self.source_data["config_file_path"], vidname=video_name
            )

        # Legacy shape (deprecated; removed with the flag): the parsed components arranged into the
        # top-level metadata["PoseEstimation"] block, with default strings baked in here.
        if not use_new_metadata_format:
            container_name = self.metadata_key or "PoseEstimationDeepLabCut"
            skeleton_name = f"Skeleton{container_name}_{self.subject_name.capitalize()}"
            device_name = f"Camera{container_name}"

            pose_estimation_metadata = DeepDict()
            pose_estimation_metadata["Skeletons"] = {
                skeleton_name: {"name": skeleton_name, "nodes": bodyparts, "edges": edges, "subject": self.subject_name}
            }
            pose_estimation_metadata["Devices"] = {
                device_name: {
                    "name": device_name,
                    "description": "Camera used for behavioral recording and pose estimation.",
                }
            }
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
            for bodypart in bodyparts:
                pose_estimation_metadata["PoseEstimationContainers"][container_name]["PoseEstimationSeries"][
                    bodypart
                ] = {
                    "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                    "description": f"Pose estimation series for {bodypart}.",
                    "unit": "pixels",
                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                    "confidence_definition": "Softmax output of the deep neural network.",
                }
            metadata["PoseEstimation"] = pose_estimation_metadata
            return metadata

        metadata_key = self.metadata_key or "deep_lab_cut_metadata_key"
        container_name = "PoseEstimationDeepLabCut"
        skeleton_name = f"Skeleton{container_name}_{self.subject_name.capitalize()}"
        device_name = f"Camera{container_name}"

        # We add an artificial camera device even when one is not available from the source, only to
        # avoid an ndx-pose warning: ndx-pose ties the number of dimensions/original_videos to the
        # number of camera devices, so a device is required to carry the frame dimensions and video
        # path. Remove once ndx-pose decouples those recording fields from the camera-device count.
        metadata["Devices"] = {
            metadata_key: {
                "name": device_name,
                "description": "Camera used for behavioral recording and pose estimation.",
            }
        }

        metadata["Behavior"]["Pose"]["Skeletons"] = {
            metadata_key: {
                "name": skeleton_name,
                "nodes": bodyparts,
                "edges": edges,
                "subject": self.subject_name,
            }
        }

        pose_estimation_series = {
            bodypart: {"name": f"PoseEstimationSeries{bodypart.capitalize()}"} for bodypart in bodyparts
        }
        metadata["Behavior"]["Pose"]["PoseEstimations"] = {
            metadata_key: {
                "name": container_name,
                "source_software": "DeepLabCut",
                "scorer": scorer,
                "dimensions": dimensions,
                "original_videos": [video_file_path] if video_file_path else None,
                "device_metadata_key": metadata_key,
                "skeleton_metadata_key": metadata_key,
                "PoseEstimationSeries": pose_estimation_series,
            }
        }

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
    ):
        """
        Conversion from DLC output files to nwb. Derived from dlc2nwb library.

        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict
            metadata info for constructing the nwb file (optional).
        """
        from ._dlc_utils import (
            _add_pose_estimation_to_nwbfile,
            _ensure_individuals_in_header,
        )

        # Dispatch on the shape of the user-supplied metadata: the dict-based format has the pose
        # sub-modality at metadata["Behavior"]["Pose"]; anything else (including no metadata) uses the
        # legacy path. The defaults are fetched in the matching shape, then user metadata is merged on.
        use_new_metadata_format = metadata is not None and "Pose" in metadata.get("Behavior", {})

        # Get default metadata
        default_metadata = DeepDict(self.get_metadata(use_new_metadata_format=use_new_metadata_format))

        # Update with user-provided metadata if available
        if metadata is not None:
            default_metadata.deep_update(metadata)

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

        default_key = "deep_lab_cut_metadata_key" if use_new_metadata_format else "PoseEstimationDeepLabCut"
        _add_pose_estimation_to_nwbfile(
            nwbfile=nwbfile,
            df_animal=df_animal,
            timestamps=timestamps,
            exclude_nans=False,
            metadata=default_metadata,
            metadata_key=self.metadata_key or default_key,
            use_new_metadata_format=use_new_metadata_format,
        )
