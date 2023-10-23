FicTrac data conversion
--------------------------

Install NeuroConv with the additional dependencies necessary for reading FicTrac data.

.. code-block:: bash

    pip install neuroconv[fictrac]

Convert FicTrac pose estimation data to NWB using :py:class:`~neuroconv.datainterfaces.behavior.fictrac.fictracdatainterface.FicTracDataInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import FicTracDataInterface

    >>> file_path = BEHAVIOR_DATA_PATH / "FicTrac" / "sample" / "sample-20230724_113055.dat"

    >>> radius = 0.035  # If you have the radius of the ball (in meters), you can pass it to the interface and the data will be saved in meters
    >>> interface = FicTracDataInterface(file_path=file_path, radius=radius, verbose=False)

    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)

    >>> # For data provenance we add the time zone information to the conversion
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)
