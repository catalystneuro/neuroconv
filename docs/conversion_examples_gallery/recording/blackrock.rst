Blackrock data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^

Convert Blackrock data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.blackrock.blackrockdatainterface.BlackrockRecordingExtractorInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces.ecephys.blackrock import BlackrockRecordingExtractorInterface
    >>>
    >>> # For this interface we need to pass the location of the ``.ns5`` file
    >>> file_path = f"{ECEPHY_DATA_PATH}/blackrock/FileSpec2.3001.ns5"
    >>> # Change the file_path to the location in your system
    >>> interface = BlackrockRecordingExtractorInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime.fromisoformat(metadata["NWBFile"]["session_start_time"])
    >>> session_start_time = session_start_time.replace(tzinfo=tz.gettz("US/Pacific")).isoformat()
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    >>>
    >>> # If the conversion was successful this should evaluate to ``True`` as the file was created.
    >>> Path(nwbfile_path).is_file()
    True
