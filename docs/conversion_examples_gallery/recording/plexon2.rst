Plexon Recording Conversion
---------------------------

Install NeuroConv with the additional dependencies necessary for reading Plexon acquisition data.

.. code-block:: bash

    pip install neuroconv[plexon]

Convert Plexon recording data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.plexon.plexondatainterface.Plexon2RecordingInterface`. Currently, only .plx is supported.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import Plexon2RecordingInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/plexon/4chDemoPL2.pl2"
    >>> # Change the file_path to the location in your system
    >>> interface = Plexon2RecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
