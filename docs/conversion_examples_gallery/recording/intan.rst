Intan data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^

Convert Neuroscope data to NWB using :py:class:`~nwb_conversion_tools.datainterfaces.IntanRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from nwb_conversion_tools import IntanRecordingInterface
    >>> 
    >>> # For this data interface we need to pass the location of the `.rhd` file 
    >>> suffix = "rhd" # This can also be rhs
    >>> file_path = f"{ECEPHY_DATA_PATH}/intan/intan_{suffix}_test_1.{suffix}"
    >>> # Change the file_path to the location in your system
    >>> interface = IntanRecordingInterface(file_path=file_path)
    >>> 
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred 
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"] = dict(session_start_time=session_start_time)
    >>>
    >>>  # Choose a path for saving the nwb file and run the conversion
    >>> save_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(save_path=save_path, metadata=metadata)
    >>>
    >>> # If the conversion was successful this should evaluate to ``True`` as the file was created.
    >>> Path(save_path).is_file()
    True