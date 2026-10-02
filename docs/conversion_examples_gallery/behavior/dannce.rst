DANNCE data conversion
-----------------------

Install NeuroConv with the additional dependencies necessary for reading DANNCE data.

.. code-block:: bash

    pip install "neuroconv[dannce]"

Convert DANNCE (or social DANNCE / sDANNCE) 3D pose estimation data to NWB using
:py:class:`~neuroconv.datainterfaces.behavior.dannce.danncedatainterface.DANNCEInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import DANNCEInterface

    >>> file_path = BEHAVIOR_DATA_PATH / "dannce" / "dannce" / "avg_and_max_predictions" / "DANNCE" / "predict_results" / "save_data_MAX.mat"
    >>> interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, verbose=False)
    >>> metadata = interface.get_metadata()
    >>> # DANNCE prediction files do not carry a session start time, so it must be set explicitly
    >>> session_start_time = datetime(2024, 6, 24, 13, 58, 40, tzinfo=ZoneInfo("US/Eastern"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Rattus norvegicus", sex="M", age="P90D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)

Timestamps and the sync table
=============================

A prediction's ``sampleID`` is not a video frame index: it is a row label of the synchronization
(``sync``) table that Label3D writes, whose ``data_frame`` column gives the video frame. In classic
DANNCE output, for example, ``sampleID`` 1, 11, 21, ... are frames 0, 1, 2, .... Pass the table as
``sync_path``, either a Label3D ``*_dannce.mat`` file (MATLAB v5 or v7.3) or a ``sync/`` folder of
``CameraN_sync.mat`` files, and each sample's time becomes its frame divided by ``sampling_rate``.
When ``calibration_path`` is a Label3D ``.mat`` file, the table is read from there and
``sync_path`` can be left out.

.. code-block:: python

    >>> run_path = BEHAVIOR_DATA_PATH / "dannce" / "dannce" / "avg_and_max_predictions"
    >>> interface = DANNCEInterface(
    ...     file_paths=run_path / "DANNCE" / "predict_results" / "save_data_AVG.mat",
    ...     sync_path=run_path / "label3d_dannce.mat",
    ...     sampling_rate=100.0,
    ... )
    >>> interface.video_frame_indices[:3]
    array([0, 1, 2])

Without a sync table the samples are taken to be consecutive frames from the start of the recording,
which only holds when no frame was skipped. With neither ``sampling_rate`` nor a sync table, set the
times yourself with ``interface.alignment[interface.metadata_key].set_times(times)``.

Camera calibration and multiple cameras
========================================

DANNCE/sDANNCE rigs typically use several calibrated cameras to triangulate 3D landmarks.
Passing ``calibration_path`` auto-detects the camera names and calibration parameters (see
:py:meth:`~neuroconv.datainterfaces.behavior.dannce.danncedatainterface.DANNCEInterface.get_camera_calibrations`
for the supported calibration file formats) and creates one calibrated camera ``Device`` per camera:

.. code-block:: python

    >>> calibration_path = BEHAVIOR_DATA_PATH / "dannce" / "dannce" / "avg_and_max_predictions" / "calibration"
    >>> interface = DANNCEInterface(
    ...     file_paths=file_path,
    ...     sampling_rate=30.0,
    ...     calibration_path=calibration_path,
    ... )
    >>> interface._camera_names
    ['Camera1', 'Camera2', 'Camera3', 'Camera4', 'Camera5', 'Camera6']

Multi-animal (sDANNCE) sessions
================================

Social DANNCE output stores multiple animals in a single file, selected via ``animal_index``.
Construct one interface instance per animal to write every animal to the same NWBFile. Each one
is named after its ``subject_name`` (``"rat2"`` gives the ``metadata_key`` ``"dannce_rat2"`` and the
container ``PoseEstimationDANNCERat2``), or, without one, after its ``animal_index``
(``PoseEstimationDANNCEAnimal1``). The same holds for animals predicted in separate files: give
each interface its ``subject_name`` and they write to one NWBFile side by side.

.. code-block:: python

    >>> multi_animal_file_path = (
    ...     BEHAVIOR_DATA_PATH / "dannce" / "sdannce" / "multiple_subjects_per_file" / "two_subjects"
    ...     / "SDANNCE" / "predict00" / "save_data_AVG0.mat"
    ... )
    >>> interface_animal2 = DANNCEInterface(
    ...     file_paths=multi_animal_file_path,
    ...     sampling_rate=30.0,
    ...     animal_index=1,
    ...     subject_name="rat2",
    ... )
    >>> interface_animal2.metadata_key
    'dannce_rat2'

Combining with source videos
=============================

Each camera's original video can be linked to DANNCE's 3D pose estimation as its
``source_video``, and the video and the pose share that camera's calibrated ``Device``. Wiring this
up by hand with ``DANNCEInterface`` and :py:class:`~neuroconv.datainterfaces.ExternalVideoInterface`
means pointing each video's ``device_metadata_key`` at the camera's ``Devices`` entry, setting
``source_video_metadata_key`` on each camera's entry in ``metadata["Pose"]["PoseEstimations"]``, and
writing the videos before DANNCE. :py:class:`~neuroconv.datainterfaces.behavior.dannce.dannceconverter.DANNCEConverter`
does this internally: it combines a ``DANNCEInterface`` with one ``ExternalVideoInterface`` per camera
and links each camera's video for you.

Videos are discovered from a single ``videos_folder_path``: the DANNCE/campy ``videos`` folder,
containing one subdirectory per camera (e.g. ``Camera1``, ``Camera2``, ...), each with that camera's
video file(s) and, optionally, a ``frametimes.npy`` file (the campy/pCamPI capture standard). When
present, each camera's own frametimes align its video. The first camera's frametimes also align the
DANNCE pose estimation, read at the frame the sync table gives for each ``sampleID``, so no
``sampling_rate`` is needed. Without a sync table the frametimes are not used for the pose, since
the frames of the predictions are unknown, and the converter warns. A rig recorded without
campy/pCamPI (no ``frametimes.npy`` at all) can still be converted: each video is timed from its own
header, a camera split across several files has them placed one after another, and the pose uses
``sampling_rate``.

.. code-block:: python

    >>> from neuroconv.converters import DANNCEConverter

    >>> run_path = BEHAVIOR_DATA_PATH / "dannce" / "sdannce" / "one_file_per_subject" / "two_subjects"
    >>> converter = DANNCEConverter(
    ...     file_paths=run_path / "SDANNCE" / "bsl0.5_FM_rat1" / "save_data_AVG0.mat",
    ...     videos_folder_path=run_path / "videos",
    ...     calibration_path=run_path / "calibration",
    ...     sync_path=run_path / "sampleCAL_BG_dannce.mat",
    ... )
    >>> metadata = converter.get_metadata()
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Rattus norvegicus", sex="M", age="P90D")
    >>>
    >>> converter.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)
