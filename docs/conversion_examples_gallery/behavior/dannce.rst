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

    >>> file_path = BEHAVIOR_DATA_PATH / "dannce" / "save_data_MAX.mat"
    >>> interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0, verbose=False)
    >>> metadata = interface.get_metadata()
    >>> # DANNCE prediction files do not carry a session start time, so it must be set explicitly
    >>> session_start_time = datetime(2024, 6, 24, 13, 58, 40, tzinfo=ZoneInfo("US/Eastern"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Rattus norvegicus", sex="M", age="P90D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)

Camera calibration and multiple cameras
========================================

DANNCE/sDANNCE rigs typically use several calibrated cameras to triangulate 3D landmarks.
Passing ``calibration_path`` auto-detects the camera names and calibration parameters (see
:py:meth:`~neuroconv.datainterfaces.behavior.dannce.danncedatainterface.DANNCEInterface.get_camera_calibrations`
for the supported calibration file formats) and creates one calibrated camera ``Device`` per camera:

.. code-block:: python

    >>> calibration_path = BEHAVIOR_DATA_PATH / "dannce" / "calibration"
    >>> interface = DANNCEInterface(
    ...     file_path=file_path,
    ...     sampling_rate=30.0,
    ...     calibration_path=calibration_path,
    ... )
    >>> interface._camera_names
    ['Camera1', 'Camera2']

Multi-animal (sDANNCE) sessions
================================

Social DANNCE output stores multiple animals in a single file, selected via ``animal_index``.
Construct one interface instance per animal, each with a distinct ``metadata_key``, to write every
animal to the same NWBFile:

.. code-block:: python

    >>> multi_animal_file_path = BEHAVIOR_DATA_PATH / "dannce" / "save_data_sdannce.mat"
    >>> interface_animal2 = DANNCEInterface(
    ...     file_path=multi_animal_file_path,
    ...     sampling_rate=30.0,
    ...     animal_index=1,
    ...     subject_name="rat2",
    ...     metadata_key="PoseEstimationRat2",
    ... )
