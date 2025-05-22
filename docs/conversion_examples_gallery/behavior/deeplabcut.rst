DeepLabCut data conversion
--------------------------

Install NeuroConv with the additional dependencies necessary for reading DeepLabCut data.

.. code-block:: bash

    pip install "neuroconv[deeplabcut]"

Convert DeepLabCut pose estimation data to NWB using :py:class:`~neuroconv.datainterfaces.behavior.deeplabcut.deeplabcutdatainterface.DeepLabCutInterface`.
This interface supports both .h5 and .csv output files from DeepLabCut.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import DeepLabCutInterface

    >>> file_path = BEHAVIOR_DATA_PATH / "DLC" / "open_field_without_video" / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"
    >>> config_file_path = BEHAVIOR_DATA_PATH / "DLC" / "open_field_without_video" / "config.yaml"

    >>> interface = DeepLabCutInterface(file_path=file_path, config_file_path=config_file_path, subject_name="ind1", verbose=False)

    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)


Specifying Metadata
~~~~~~~~~~~~~~~~~~~

The example above shows how to convert DeepLabCut data without specifying detailed metadata, in which case the metadata will be
automatically generated with default values. To ensure that the NWB file is properly annotated, you can specify the metadata
using the formats described below.

For :py:class:`~neuroconv.datainterfaces.behavior.deeplabcut.deeplabcutdatainterface.DeepLabCutInterface`,
use the following structure:

.. code-block:: python

    >>> pose_estimation_metadata_key = "PoseEstimationContainerName"
    >>> interface = DeepLabCutInterface(file_path=file_path, pose_estimation_metadata_key=pose_estimation_metadata_key)
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Customize the PoseEstimation container metadata
    >>> metadata["PoseEstimation"]["PoseEstimationContainers"][pose_estimation_metadata_key] = {
    ...     "name": "PoseEstimationContainerName", # Edit to change the name and if you add multiple DLC containers for disambiguation
    ...     "description": "2D keypoint coordinates estimated using DeepLabCut.",
    ...     "source_software": "DeepLabCut",
    ...     "dimensions": [0, 0],
    ...     "skeleton": "SubjectIDSkeleton",
    ...     "devices": ["CameraPoseEstimationContainerName"],
    ...     "scorer": "DLC_resnet50_openfieldAug20shuffle1_30000",
    ...     "original_videos": None,
    ...     "PoseEstimationSeries": {
    ...         "snout": {
    ...             "name": "PoseEstimationSeriesSnout",
    ...             "description": "Pose estimation series for snout.",
    ...             "unit": "pixels",
    ...             "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
    ...             "confidence_definition": "Softmax output of the deep neural network.",
    ...         },
    ...         "leftear": {
    ...             "name": "PoseEstimationSeriesLeftear",
    ...             "description": "Pose estimation series for leftear.",
    ...             "unit": "pixels",
    ...             "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
    ...             "confidence_definition": "Softmax output of the deep neural network.",
    ...         },
    ...         "rightear": {
    ...             "name": "PoseEstimationSeriesRightear",
    ...             "description": "Pose estimation series for rightear.",
    ...             "unit": "pixels",
    ...             "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
    ...             "confidence_definition": "Softmax output of the deep neural network.",
    ...         },
    ...         "tailbase": {
    ...             "name": "PoseEstimationSeriesTailbase",
    ...             "description": "Pose estimation series for tailbase.",
    ...             "unit": "pixels",
    ...             "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
    ...             "confidence_definition": "Softmax output of the deep neural network.",
    ...         },
    ...     },
    ... }

    >>> # Define skeleton metadata
    >>> skeletons_metadata = {
    ...     "SubjectIDSkeleton": {
    ...         "name": "SkeletonPoseEstimationContainerName_Ind1",
    ...         "nodes": ["snout", "leftear", "rightear", "tailbase"],
    ...         "edges": [],
    ...         "subject": "the_subject_id",  # If this matches the subject_id in the video, it will be used to link the skeleton to the video
    ...     }
    ... }

    >>> # Add skeleton metadata to the main metadata
    >>> metadata["PoseEstimation"]["Skeletons"] = skeletons_metadata

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

The metadata structure for DeepLabCut includes:

1. **PoseEstimationContainers** - Contains the main metadata for the pose estimation:

   - ``name``: Name of the pose estimation container
   - ``description``: Description of the pose estimation data
   - ``source_software``: Software used for pose estimation (DeepLabCut)
   - ``dimensions``: Video dimensions [height, width]
   - ``skeleton``: Reference to a skeleton defined in Skeletons
   - ``devices``: List of devices used for recording
   - ``scorer``: Name of the DeepLabCut model used
   - ``original_videos``: Paths to original videos (if available)
   - ``PoseEstimationSeries``: Dictionary of series for each bodypart

2. **Skeletons** - Defines the skeleton structure:

   - ``name``: Name of the skeleton
   - ``nodes``: List of bodyparts/keypoints
   - ``edges``: Connections between nodes (optional)
   - ``subject``: Subject ID associated with this skeleton. If the subject matches the subject_id of the nwbfile the skeleton will be linked to the Subject.
