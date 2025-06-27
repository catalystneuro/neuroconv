Femtonics imaging data conversion
---------------------------------

Install NeuroConv with the additional dependencies necessary for reading Femtonics data.

.. code-block:: bash

    pip install "neuroconv[femtonics]"

Convert Femtonics imaging data to NWB using :py:class:`~neuroconv.datainterfaces.ophys.femtonics.femtonicsimaginginterface.FemtonicsImagingInterface``

.. code-block:: python
    >>> import sys, platform
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import FemtonicsImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p29.mesc"
    >>> 
    >>> # Check available sessions, units, and channels
    >>> available_sessions = FemtonicsImagingInterface.get_available_sessions(file_path)
    >>> available_units = FemtonicsImagingInterface.get_available_units(file_path, session_index=0)
    >>> available_channels = FemtonicsImagingInterface.get_available_channels(file_path, session_index=0, munit_index=0)
    >>> 
    >>> interface = FemtonicsImagingInterface( # specify session_index and munit_index and channel_name
    ...     file_path=file_path,
    ...     session_index=0,
    ...     munit_index=0,
    ...     channel_name="UG",
    ...     verbose=False
    ... )
    >>>
    >>> metadata = interface.get_metadata()
    >>> # Session start time is automatically extracted from the .mesc file with timezone information
    >>> print(f"Session start time: {metadata['NWBFile']['session_start_time']}")
    >>>
    >>> # Run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)