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

    >>> interface = DeepLabCutInterface(file_path=file_path, config_file_path=config_file_path, subject_name="ind1", sampling_frequency=30.0, verbose=False)

    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)


NeuroConv writes as much metadata as is available in the source format, but most of the time the
experimenter has metadata that the records do not carry. Adding the rest improves the provenance of
the file and makes it more useful for future users and for the community as a whole. To add it, follow
:ref:`the pose estimation how-to <annotate_pose_metadata>`, which walks through common experimental
configurations.

Specifying Metadata
~~~~~~~~~~~~~~~~~~~

The example above shows how to convert DeepLabCut data without specifying detailed metadata, in which case the metadata will be
automatically generated with default values. To ensure that the NWB file is properly annotated, you can specify the metadata
using the formats described below.

For :py:class:`~neuroconv.datainterfaces.behavior.deeplabcut.deeplabcutdatainterface.DeepLabCutInterface`,
use the following structure:

.. code-block:: python

    >>> metadata_key = "deep_lab_cut_metadata_key"
    >>> interface = DeepLabCutInterface(file_path=file_path, metadata_key=metadata_key, sampling_frequency=30.0)
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # The container: its name is what appears in the file, the key is only how you address it here
    >>> container = metadata["Pose"]["PoseEstimations"][metadata_key]
    >>> container.update(
    ...     name="PoseEstimationContainerName",
    ...     description="2D keypoint coordinates estimated using DeepLabCut.",
    ...     source_software_version="2.2.0",
    ... )
    >>>
    >>> # Each keypoint gets one series. Nothing in the source says what the coordinates mean, so the
    >>> # unit, the reference frame and the confidence definition are yours to state.
    >>> for keypoint_name, series in container["PoseEstimationSeries"].items():
    ...     series.update(
    ...         unit="pixels",
    ...         reference_frame="(0,0) corresponds to the bottom left corner of the video.",
    ...         confidence_definition="Softmax output of the deep neural network.",
    ...     )
    >>>
    >>> # The skeleton names the body parts and the edges between them, and links to the subject
    >>> metadata["Pose"]["Skeletons"][metadata_key].update(
    ...     name="SkeletonPoseEstimationContainerName_Ind1",
    ...     edges=[[0, 1], [0, 2], [0, 3]],
    ...     subject="subject1",  # links the skeleton when it matches the subject_id below
    ... )
    >>>
    >>> # The camera, if you know it. No pose format records one, so none is written unless you say so.
    >>> metadata["Devices"]["camera"] = dict(name="CameraPoseEstimationContainerName")
    >>> container["device_metadata_key"] = "camera"
    >>>
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

The metadata lives under the top-level ``metadata["Pose"]``, in two registries plus the shared
``metadata["Devices"]``. Each entry is addressed by a key of your choosing; that key is an internal
handle and never appears in the NWB file, while the entry's ``name`` field is what does.

1. **PoseEstimations** - the container, one per camera view of one subject:

   - ``name``: Name of the ``PoseEstimation`` container in the file
   - ``description``: Description of the pose estimation data
   - ``source_software`` and ``source_software_version``: the tracker and its version
   - ``scorer``: Name of the DeepLabCut model used
   - ``dimensions``: Video dimensions [height, width] for each video
   - ``original_videos`` and ``labeled_videos``: Paths to the videos, if available
   - ``device_metadata_key``: Address of an entry in ``metadata["Devices"]``, if you have a camera
   - ``skeleton_metadata_key``: Address of an entry in ``metadata["Pose"]["Skeletons"]``
   - ``PoseEstimationSeries``: One entry per bodypart, each with a ``name`` and optionally a
     ``description``, ``unit``, ``reference_frame`` and ``confidence_definition``

2. **Skeletons** - the layout of the body:

   - ``name``: Name of the skeleton
   - ``nodes``: List of bodyparts/keypoints
   - ``edges``: Connections between nodes, as pairs of node indices (optional)
   - ``subject``: Subject ID associated with this skeleton. If it matches the ``subject_id`` of the
     NWBFile the skeleton is linked to the ``Subject``.
