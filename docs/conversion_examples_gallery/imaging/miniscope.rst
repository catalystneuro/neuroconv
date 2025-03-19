Miniscope data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading Miniscope data.

.. code-block:: bash

    pip install "neuroconv[miniscope]"

Miniscope simultaneously records optical physiology and behavior in the form of video data.
The :py:class:`~neuroconv.datainterfaces.ophys.miniscope.miniscopeconverter.MiniscopeConverter` combines the two data streams
into a single conversion.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.converters import MiniscopeConverter
    >>>
    >>> # The 'folder_path' is the path to the main Miniscope folder containing both the recording and behavioral data streams in separate subfolders.
    >>> folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5")
    >>> converter = MiniscopeConverter(folder_path=folder_path, verbose=False)
    >>>
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we can add the time zone information to the conversion if missing
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = ZoneInfo("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
