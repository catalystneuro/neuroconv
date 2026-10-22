OptiTrack data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading OptiTrack data.

.. code-block:: bash

    pip install "neuroconv[optitrack]"

Convert the rigid bodies, skeletons and marker sets in a CSV file exported by OptiTrack Motive to NWB using
:py:class:`~neuroconv.datainterfaces.behavior.optitrack.optitrackdatainterface.OptiTrackInterface`.
Each rigid body is written to the behavior module as a ``SpatialSeries`` for its position and a ``TimeSeries``
for its orientation, in Euler angles or as a quaternion with columns w, x, y, z. The labeled bones and markers
of each skeleton or marker set are written as one ``ndx-pose`` ``MultiCameraPoseEstimation`` container, and the
orientation of each bone as a ``TimeSeries`` like a rigid body's.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import OptiTrackInterface
    >>>
    >>> # Change the file_path so it points to the csv file in your system
    >>> file_path = BEHAVIOR_DATA_PATH / "optitrack" / "csv_export" / "version_1_23" / "euler_angles_yxz_meters" / "Take 2023-03-15 08.25.25 AM.csv"
    >>> interface = OptiTrackInterface(file_path=file_path)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # Motive writes the capture start time without a time zone, so add it
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=ZoneInfo("America/Montreal")))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as the anatomical location,
the meaning of the values, or a semantically meaningful description of the data. Follow
:ref:`the pose estimation how-to <annotate_pose_metadata>` for a modality-relevant guide to adding this
extra metadata, which makes the data more useful for future users and for the community as a whole.
Its :ref:`section on templates <how_to_annotate_pose_from_a_template>` starts from scratch, and the
:ref:`reference template <pose_estimation_metadata_template>` lists every element the metadata accepts.
