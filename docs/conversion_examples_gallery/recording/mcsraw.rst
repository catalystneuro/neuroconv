MCSRaw conversion
-----------------

Install NeuroConv with the additional dependencies necessary for reading MCSRaw data.

.. code-block:: bash

    pip install neuroconv[mcsraw]

Convert MCSRaw data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.mcsraw.mcsrawdatainterface.MCSRawRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import MCSRawRecordingInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/rawmcs/raw_mcs_with_header_1.raw"
    >>> # Change the file_path to the location in your system
    >>> interface = MCSRawRecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
