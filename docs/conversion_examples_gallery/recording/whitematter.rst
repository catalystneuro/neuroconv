WhiteMatter data conversion
-----------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading WhiteMatter data.

.. code-block:: bash

    pip install "neuroconv[whitematter]"

Convert WhiteMatter data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.whitematter.whitematterdatainterface.WhiteMatterRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import WhiteMatterRecordingInterface
    >>>
    >>> # For this data interface we need to pass the file_path with the location of the data
    >>> file_path = f"{ECEPHY_DATA_PATH}/whitematter/HSW_2024_12_12__10_28_23__70min_17sec__hsamp_64ch_25000sps_stub.bin"
    >>> # Change the file_path to the location of the data in your system
    >>> sampling_frequency = 25_000.0
    >>> num_channels = 64
    >>> interface = WhiteMatterRecordingInterface(file_paths=[file_path], sampling_frequency=sampling_frequency, num_channels=num_channels)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>>  # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
