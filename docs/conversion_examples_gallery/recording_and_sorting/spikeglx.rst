Spikelgx data conversion
^^^^^^^^^^^^^^^^^^^^^^^^

Example of how to convert Spikelgx to nwb

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from nwb_conversion_tools import NeuroscopeRecordingInterface

Then we creates a datetime object with date the first of Junuary of 2020 in the US/Pacific time-zone
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    
    >>> metadata = {"NWBFile":{"session_start_time":session_start_time}}

Finally, we indicate the location of the dat file and run the conversion.
    >>> file_path = "/home/heberto/ephy_testing_data/neuroscope/test1/test1.dat"
    
    >>> interface = NeuroscopeRecordingInterface(file_path=file_path)
    
    >>> save_path = "./nwb_file.nwb"
    
    >>> interface.run_conversion(save_path=save_path, metadata=metadata)

If everything went right, this should return True
    >>> Path(save_path).is_file()
    True