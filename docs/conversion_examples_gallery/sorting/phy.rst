Phy sorting data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Convert Phy data to NWB using :py:class:`~nwb_conversion_tools.datainterfaces.PhySortingInterface`.

.. code-block:: python
    
    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> 
    >>> from nwb_conversion_tools import PhySortingInterface
    >>> 
    >>> folder_path = f"{ECEPHY_DATA_PATH}/phy/phy_example_0"
    >>> # Change the file_path to the location of the data in your system
    >>> interface = PhySortingInterface(folder_path=folder_path)
    >>> 
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific")).isoformat()
    >>> metadata["NWBFile"] = dict(session_start_time=session_start_time)
    >>> save_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(save_path=save_path, metadata=metadata)
    >>> 
    >>> # If the conversion was successful this should evaluate to ``True`` as the file was created.
    >>> Path(save_path).is_file()
    True