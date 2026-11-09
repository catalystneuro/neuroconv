OptiTrack data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading OptiTrack data.

.. code-block:: bash

    pip install "neuroconv[optitrack]"

Convert the rigid bodies, skeletons and marker sets in a CSV file exported by OptiTrack Motive to NWB using
:py:class:`~neuroconv.datainterfaces.behavior.optitrack.optitrackdatainterface.OptiTrackInterface`.
Each rigid body is written to the behavior module as a ``SpatialSeries`` for its position and a ``TimeSeries``
for its orientation, in Euler angles or as a quaternion with columns w, x, y, z, and, when the export has it,
a ``TimeSeries`` for its mean marker error. The labeled bones and markers of each skeleton or marker set are
written as one ``ndx-pose`` ``MultiCameraPoseEstimation`` container, and the orientation of each bone as a
``TimeSeries`` like a rigid body's.

The interface reads CSV files exported from Motive with the header information turned on and with skeletons
in global coordinates. An export without the header information, one with skeletons in local
coordinates, and the row-typed CSV of early Motive and Arena versions raise an error that says how to export
the take again.

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

Some exports do not give a session start time that can be read: exports in format version 1.22 write the
capture start time as a date in 1969, and some locales write the time of day with a localized AM or PM
marker, or none. ``get_metadata`` then warns and leaves ``session_start_time`` out, and you set it from
your own records. A take that kept the name Motive gave it, such as ``Take 2023-01-24 09.35.03 AM``, has the
capture date and time in its name.

.. code-block:: python

    >>> from datetime import datetime
    >>>
    >>> file_path = BEHAVIOR_DATA_PATH / "optitrack" / "csv_export" / "version_1_22" / "euler_angles_yxz_meters" / "Take 2023-01-24 09.35.03 AM.csv"
    >>> interface = OptiTrackInterface(file_path=file_path)
    >>> metadata = interface.get_metadata()
    >>> "session_start_time" in metadata["NWBFile"]
    False
    >>> session_start_time = datetime(2023, 1, 24, 9, 35, 3, tzinfo=ZoneInfo("America/New_York"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as the anatomical location,
the meaning of the values, or a semantically meaningful description of the data. For the skeletons and
marker sets, which are written as pose estimation, follow
:ref:`the pose estimation how-to <annotate_pose_metadata>` for a modality-relevant guide to adding this
extra metadata, which makes the data more useful for future users and for the community as a whole.
Its :ref:`section on templates <how_to_annotate_pose_from_a_template>` starts from scratch, and the
:ref:`reference template <pose_estimation_metadata_template>` lists every element the metadata accepts.
