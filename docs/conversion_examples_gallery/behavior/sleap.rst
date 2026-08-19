SLEAP data conversion
---------------------

Install NeuroConv with the additional dependencies necessary for reading SLEAP data.

.. code-block:: bash

    pip install "neuroconv[sleap]"

Convert SLEAP pose estimation data to NWB using :py:class:`~neuroconv.datainterfaces.behavior.sleap.sleapdatainterface.SLEAPInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import SLEAPInterface
    >>>
    >>> # Change the file_path so it points to the slp file in your system
    >>> file_path = BEHAVIOR_DATA_PATH / "sleap" / "predictions_1.2.7_provenance_and_tracking.slp"
    >>> interface = SLEAPInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

NeuroConv writes as much metadata as is available in the source format, but most of the time the
experimenter has metadata that the records do not carry. Adding the rest improves the provenance of
the file and makes it more useful for future users and for the community as a whole. To add it, follow
:ref:`the pose estimation how-to <annotate_pose_metadata>`, which walks through common experimental
configurations.
