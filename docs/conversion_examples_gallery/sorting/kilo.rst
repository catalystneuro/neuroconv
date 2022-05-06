Kilosorting data conversion
^^^^^^^^^^^^^^^^^^^

Convert Kilosorting data to NWB using :py:class:`~nwb_conversion_tools.datainterfaces.Kilosorting`.

.. code-block:: python
    
    from datetime import datetime
    from dateutil import tz
    from pathlib import Path

    from nwb_conversion_tools import PhySortingInterface


    folder_path = f"/home/heberto/ephy_testing_data/phy/phy_example_0"
    interface = PhySortingInterface(folder_path=folder_path)

    metadata = interface.get_metadata()
    print(metadata)
    tzinfo = tz.gettz("US/Pacific")
    session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    session_start_time = session_start_time.replace(tzinfo=tzinfo).isoformat()
    metadata["NWBFile"] = dict(session_start_time=session_start_time)
    save_path = "./test3.nwb"
    interface.run_conversion(save_path=save_path, metadata=metadata)

    Path(save_path).is_file()
    Path(save_path).unlink()