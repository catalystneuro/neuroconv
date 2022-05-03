Neuroscope data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^

Example of how to convert ``Neuroscope`` to nwb:

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from nwb_conversion_tools import NeuroscopeRecordingInterface

Then we creates a datetime object representing the date of the first of January of 2020 in the US/Pacific time-zone. 
We use this for the metadata:
    
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))    
    >>> metadata = {"NWBFile":{"session_start_time":session_start_time}}

Finally, we indicate the location of the ``dat`` file and run the conversion.

    >>> file_path = "./ephy_testing_data/neuroscope/test1/test1.dat"  
    >>> interface = NeuroscopeRecordingInterface(file_path=file_path)
    >>> save_path = "./nwb_neurocope_file.nwb"
    >>> interface.run_conversion(save_path=save_path, metadata=metadata)

Note that the file path is design to run in our CI. You have to make the file_path point to your local data file.

If everything went right, this should return True

    >>> Path(save_path).is_file()
    False