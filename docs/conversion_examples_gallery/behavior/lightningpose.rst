LightningPose data conversion
-----------------------------

Install NeuroConv with the additional dependencies necessary for reading LightningPose data.

.. code-block:: bash

    pip install "neuroconv[lightningpose]"

Convert LightningPose pose estimation data to NWB using :py:class:`~neuroconv.datainterfaces.behavior.lightningpose.lightningposeconverter.LightningPoseConverter`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.converters import LightningPoseConverter

    >>> folder_path = BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds"
    >>> file_path = str(folder_path / "test_vid.csv")
    >>> original_video_file_path = str(folder_path / "test_vid.mp4")
    >>> # The labeled video file path is optional
    >>> labeled_video_file_path = str(folder_path / "labeled_videos/test_vid_labeled.mp4")

    >>> converter = LightningPoseConverter(file_path=file_path, original_video_file_path=original_video_file_path, labeled_video_file_path=labeled_video_file_path, verbose=False)
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = ZoneInfo("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> converter.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as the anatomical location,
the meaning of the values, or a semantically meaningful description of the data. Follow
:ref:`the pose estimation how-to <annotate_pose_metadata>` for a modality-relevant guide to adding this
extra metadata, which makes the data more useful for future users and for the community as a whole.
Its :ref:`section on templates <how_to_annotate_pose_from_a_template>` starts from scratch, and the
:ref:`reference template <pose_estimation_metadata_template>` lists every element the metadata accepts.
