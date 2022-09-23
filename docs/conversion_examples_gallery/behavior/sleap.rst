SLEAP data conversion
---------------------

Install NeuroConv with the additional dependencies necessary for reading SLEAP data.

.. code-block:: bash

    pip install neuroconv[sleap]

Convert SLEAP pose estimation data to NWB using :py:class:`~neuroconv.datainterfaces.behavior.sleap.sleapdatainterface.SLEAPInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import SLEAPInterface
    >>>
    >>> # Change the file_path so it points to the slp file in your system
    >>> file_path = BEHAVIOR_DATA_PATH / "sleap" / "predictions_1.2.7_provenance_and_tracking.slp"
    >>>
    >>> interface = SLEAPInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    >>>
    >>> Path(nwbfile_path).is_file()
    True
