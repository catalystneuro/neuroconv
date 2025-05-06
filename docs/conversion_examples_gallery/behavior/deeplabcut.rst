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

Customizing Pose Estimation Metadata
-----------------------------------

The DeepLabCutInterface provides a rich metadata schema that allows you to customize how the pose estimation data is represented in the NWB file. You can customize the container name, description, reference frame, units, and more.

.. code-block:: python

    >>> # Get the default metadata
    >>> metadata = interface.get_metadata()
    >>>
    >>> # The PoseEstimation metadata contains information about skeletons, devices, and containers
    >>> pose_metadata = metadata["PoseEstimation"]
    >>>
    >>> # Create a custom container name
    >>> custom_container_name = "CustomPoseEstimation"
    >>>
    >>> # Get the skeleton name and device name from the default metadata
    >>> skeleton_name = list(pose_metadata["Skeletons"].keys())[0]
    >>> device_name = list(pose_metadata["Devices"].keys())[0]
    >>>
    >>> # Create a custom container with custom settings
    >>> pose_metadata["PoseEstimationContainers"][custom_container_name] = {
    ...     "name": custom_container_name,
    ...     "description": "Custom pose estimation container for demonstration",
    ...     "reference_frame": "Custom reference frame: (0,0) is at the center of the arena",
    ...     "skeleton": skeleton_name,
    ...     "devices": [device_name],
    ...     "PoseEstimationSeries": {}
    ... }
    >>>
    >>> # Get the bodyparts from the data
    >>> import pandas as pd
    >>> data_frame = pd.read_hdf(file_path)
    >>> bodyparts = data_frame.columns.get_level_values("bodyparts").unique().tolist()
    >>>
    >>> # Add custom series for each bodypart
    >>> for bodypart in bodyparts:
    ...     pose_metadata["PoseEstimationContainers"][custom_container_name]["PoseEstimationSeries"][bodypart] = {
    ...         "name": f"ind1_{bodypart}",
    ...         "description": f"Custom description for {bodypart}",
    ...         "unit": "centimeters",  # Change the default unit
    ...         "reference_frame": "Custom reference frame: (0,0) is at the center of the arena",
    ...         "confidence_definition": "Softmax output of the deep neural network."
    ...     }
    >>>
    >>> # For specific bodyparts, you can override settings
    >>> if "snout" in bodyparts:
    ...     pose_metadata["PoseEstimationContainers"][custom_container_name]["PoseEstimationSeries"]["snout"].update({
    ...         "description": "Special description for the snout keypoint",
    ...         "unit": "millimeters"  # Override the unit for this specific keypoint
    ...     })
    >>>
    >>> # Run the conversion with the custom container name
    >>> interface.run_conversion(
    ...     nwbfile_path=path_to_save_nwbfile,
    ...     metadata=metadata,
    ...     container_name=custom_container_name
    ... )

You can also customize the skeleton nodes and edges:

.. code-block:: python

    >>> # Create custom edges (connections between bodyparts)
    >>> # For example, connect nose to ears, ears to each other, etc.
    >>> if "snout" in bodyparts and "leftear" in bodyparts and "rightear" in bodyparts:
    ...     snout_idx = bodyparts.index("snout")
    ...     leftear_idx = bodyparts.index("leftear")
    ...     rightear_idx = bodyparts.index("rightear")
    ...
    ...     custom_edges = [
    ...         [snout_idx, leftear_idx],   # Connect snout to left ear
    ...         [snout_idx, rightear_idx],  # Connect snout to right ear
    ...         [leftear_idx, rightear_idx]  # Connect left ear to right ear
    ...     ]
    ...
    ...     # Add the custom edges to the skeleton
    ...     pose_metadata["Skeletons"][skeleton_name]["edges"] = custom_edges
