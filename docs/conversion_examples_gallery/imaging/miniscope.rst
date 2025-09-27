Miniscope data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading Miniscope data.

.. code-block:: bash

    pip install "neuroconv[miniscope]"

Miniscope simultaneously records optical physiology and behavior in the form of video data.

MiniscopeConverter: Multi-recording format
==========================================

The :py:class:`~neuroconv.datainterfaces.ophys.miniscope.miniscopeconverter.MiniscopeConverter` is designed for
data where multiple recordings are organized in timestamp subfolders. It combines both imaging
and behavioral video data streams into a single conversion.

**Expected folder structure:**

.. code-block::

    main_folder/
    ├── 15_03_28/              # timestamp folder
    │   ├── Miniscope/         # imaging data
    │   │   ├── 0.avi
    │   │   ├── 1.avi
    │   │   ├── metaData.json
    │   │   └── timeStamps.csv
    │   ├── BehavCam_2/        # behavioral video
    │   │   ├── 0.avi
    │   │   ├── metaData.json
    │   │   └── timeStamps.csv
    │   └── metaData.json
    ├── 15_06_28/              # another timestamp folder
    │   ├── Miniscope/
    │   ├── BehavCam_2/
    │   └── metaData.json
    └── 15_12_28/
        └── ...

**Usage:**

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.converters import MiniscopeConverter
    >>>
    >>> # The 'folder_path' is the path to the main Miniscope folder containing timestamp subfolders
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

MiniscopeImagingInterface: Flexible single-recording format
===========================================================

For alternative folder structures or when you only need to convert imaging data (without behavioral video),
use the more flexible :py:class:`~neuroconv.datainterfaces.ophys.miniscope.MiniscopeImagingInterface`.

**Standard Usage with folder_path:**

For the standard case, the interface expects a folder with the following structure:

.. code-block::

    miniscope_folder/
    ├── 0.avi                  # video file 1
    ├── 1.avi                  # video file 2 (optional)
    ├── 2.avi                  # video file 3 (optional)
    ├── metaData.json          # required configuration file
    └── timeStamps.csv         # optional timestamps file

.. code-block:: python

    >>> from neuroconv.datainterfaces import MiniscopeImagingInterface
    >>>
    >>> # Point directly to a Miniscope folder containing .avi files and metaData.json
    >>> folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5" / "15_03_28" / "Miniscope")
    >>> interface = MiniscopeImagingInterface(folder_path=folder_path)
    >>>
    >>> # Get metadata and add required session_start_time
    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Convert to NWB
    >>> nwbfile_path = "miniscope_single_recording.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

**Alternative Parameters for Non-Standard Structures:**

If you don't have the required configuration file in the expected location, or if the timestamps are stored elsewhere,
you can specify the file paths directly using these parameters:

- ``file_paths`` (*list*): List of .avi file paths to be processed from the same recording session
- ``configuration_file_path`` (*str*): Path to the metaData.json configuration file
- ``timeStamps_file_path`` (*str, optional*): Path to the timeStamps.csv file containing timestamps for this recording

**Example with custom file paths:**

.. code-block:: python

    >>> from neuroconv.datainterfaces import MiniscopeImagingInterface
    >>>
    >>> # Specify individual files for non-standard folder structures
    >>> file_paths = ["/path/to/video1.avi", "/path/to/video2.avi"]
    >>> configuration_file_path = "/path/to/metaData.json"
    >>> timeStamps_file_path = "/path/to/timeStamps.csv"  # optional
    >>>
    >>> interface = MiniscopeImagingInterface(
    ...     file_paths=file_paths,
    ...     configuration_file_path=configuration_file_path,
    ...     timeStamps_file_path=timeStamps_file_path
    ... )
    >>>
    >>> # Get metadata and add required session_start_time
    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Convert to NWB
    >>> nwbfile_path = "miniscope_custom_structure.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
