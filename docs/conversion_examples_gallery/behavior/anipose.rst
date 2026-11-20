Anipose data conversion
-----------------------

Install NeuroConv with the additional dependencies necessary for reading Anipose data.

.. code-block:: bash

    pip install "neuroconv[anipose]"

Convert the 3D pose that Anipose triangulates, one pose-3d CSV per recording, to NWB using
:py:class:`~neuroconv.datainterfaces.behavior.anipose.aniposedatainterface.AniposeInterface`. The
``calibration.toml`` the recording was triangulated with is optional; with it, each camera is written as a
calibrated camera device.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import AniposeInterface

    >>> session_path = BEHAVIOR_DATA_PATH / "anipose" / "pose_input_format" / "deeplabcut_h5" / "020920_preDTreaches_day2" / "JiDT12"
    >>> file_path = session_path / "pose-3d" / "preDT2_JiDT12_reach14_miss.csv"
    >>> calibration_file_path = session_path / "calibration" / "calibration.toml"
    >>> interface = AniposeInterface(file_path=file_path, calibration_file_path=calibration_file_path, sampling_rate=200.0)
    >>> metadata = interface.get_metadata()
    >>> # Anipose output does not carry a session start time, so it must be set explicitly
    >>> session_start_time = datetime(2020, 2, 9, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Anipose does not record the unit of the coordinates: it is the unit of the calibration board
    >>> for series_metadata in metadata["Pose"]["MultiCameraPoseEstimations"]["anipose"]["PoseEstimationSeries"].values():
    ...     series_metadata["unit"] = "millimeters"
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)

Timestamps
==========

The pose-3d CSV records the frame index of each row (``fnum``) and no times, so each time is ``fnum``
divided by ``sampling_rate``, the frame rate of the videos. Without ``sampling_rate``, set the times
yourself with ``interface.temporal_alignment[interface.metadata_key].set_times(times)`` before writing.
