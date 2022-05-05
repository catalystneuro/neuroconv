Neuroscope data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^

Convert Neuroscope data to NWB using :py:class:`~nwb_conversion_tools.datainterfaces.NeuroscopeRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from nwb_conversion_tools import NeuroscopeRecordingInterface
    >>> 
    >>> # For Neuroscope we need to pass the location of the `.dat` file
    >>> file_path = "./ephy_testing_data/neuroscope/test1/test1.dat"
    >>> interface = NeuroscopeRecordingInterface(file_path=file_path)
    >>> 
    >>> # Extract what metadata we can from the source files 
    >>> # session_start_time is required for conversion. If it cannot be inferred 
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>>  # Choose a path for saving the nwb file and run the conversion
    >>> save_path = "./nwb_neuroscope.nwb"
    >>> interface.run_conversion(save_path=save_path, metadata=metadata)
    >>>
    >>> # If the conversion was successful this should evaluate to ``True`` as the file was created.
    >>> Path(save_path).is_file()
    False