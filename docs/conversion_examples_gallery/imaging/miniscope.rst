Miniscope data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading Miniscope data.

.. code-block:: bash

    pip install "neuroconv[miniscope]"

Miniscope simultaneously records optical physiology and behavior in the form of video data.

MiniscopeConverter: Timestamp-organized multi-session format
=============================================================

The :py:class:`~neuroconv.datainterfaces.ophys.miniscope.miniscopeconverter.MiniscopeConverter` is designed for
data where multiple recordings are organized in timestamp subfolders. It combines both imaging
and behavioral video data streams into a single conversion.

**Important:** The converter concatenates all recordings into a single continuous data stream.
Timestamps are preserved to maintain the actual time gaps between acquisitions. For example,
if you have three acquisitions at different times, they will appear as one continuous
``OnePhotonSeries`` with timestamps showing large intervals (e.g., 180 seconds) between the last
frame of one acquisition and the first frame of the next.

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


.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.converters import MiniscopeConverter
    >>>
    >>> # The 'folder_path' is the path to the main Miniscope folder containing timestamp subfolders
    >>> folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5")
    >>> converter = MiniscopeConverter(folder_path=folder_path, verbose=False)
    >>>
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we can add the time zone information to the conversion if missing
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=ZoneInfo("US/Pacific")))
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

MiniscopeImagingInterface: Individual acquisition folder
=========================================================

For alternative folder structures or when you only need to convert imaging data (without behavioral video),
use the more flexible :py:class:`~neuroconv.datainterfaces.ophys.miniscope.MiniscopeImagingInterface`.
This interface handles a single Miniscope acquisition and provides two usage modes.

**Standard Usage with folder_path:**

For the standard case, the interface expects a folder with the following structure:

.. code-block::

    miniscope_folder/
    ├── 0.avi                  # video file 1
    ├── 1.avi                  # video file 2
    ├── 2.avi                  # video file 3
    ├── ...                    # additional video files
    ├── metaData.json          # required configuration file
    └── timeStamps.csv         # optional timestamps file

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import MiniscopeImagingInterface
    >>>
    >>> # Point directly to a Miniscope folder containing .avi files and metaData.json
    >>> folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5" / "15_03_28" / "Miniscope")
    >>> interface = MiniscopeImagingInterface(folder_path=folder_path)
    >>>
    >>> # Get metadata (session_start_time is automatically extracted from parent folder's metaData.json)
    >>> metadata = interface.get_metadata()
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> # Add timezone information for data provenance
    >>> metadata["NWBFile"]["session_start_time"] = session_start_time.replace(tzinfo=ZoneInfo("US/Pacific"))
    >>>
    >>> # Convert to NWB
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

**Alternative Parameters for Non-Standard Folder Structures:**

If your data is organized in a non-standard folder structure where files are not in the same directory,
you can specify the file paths directly using these parameters:

- ``file_paths``: List of .avi file paths (must be named 0.avi, 1.avi, 2.avi, ...) from the same acquisition
- ``configuration_file_path``: Path to the metaData.json configuration file (required)
- ``timeStamps_file_path``: Optional path to the timeStamps.csv file. If not provided, timestamps will be generated as regular intervals based on the sampling frequency

For detailed usage examples with custom file paths, see the
:py:class:`~neuroconv.datainterfaces.ophys.miniscope.MiniscopeImagingInterface` docstring.

ConverterPipe: Custom multi-acquisition workflows
==================================================

For complex experimental sessions with multiple data streams or non-standard folder structures,
you can use :py:class:`~neuroconv.nwbconverter.ConverterPipe` to assemble multiple interfaces
into a single converter. This approach gives you maximum flexibility to handle arbitrary folder structures.

To illustrate how ``ConverterPipe`` works, we'll use the same folder structure that ``MiniscopeConverter``
expects. **Note:** This is purely for demonstration purposes. You should adapt the paths below to match
your actual data organization, which may be completely different.

The example folder structure:

.. code-block::

    C6-J588_Disc5/
    ├── 15_03_28/
    │   ├── Miniscope/
    │   │   ├── 0.avi
    │   │   ├── metaData.json
    │   │   └── timeStamps.csv
    │   ├── BehavCam_2/
    │   │   ├── 0.avi
    │   │   ├── metaData.json
    │   │   └── timeStamps.csv
    │   └── metaData.json
    └── 15_06_28/
        └── ...

In this structure, the two timestamp folders (``15_03_28`` and ``15_06_28``) represent **sequential acquisitions** -
recordings that occurred one after the other at different times. To preserve the time gap between these acquisitions,
we need to use ``set_aligned_starting_time()`` to shift the timestamps of the second acquisition.

.. code-block:: python

    >>> from neuroconv.datainterfaces import MiniscopeImagingInterface
    >>> from neuroconv import ConverterPipe
    >>> from zoneinfo import ZoneInfo
    >>>
    >>> # Initialize imaging interfaces for sequential acquisitions
    >>> # Acquisition 1 starts at time 0
    >>> acquisition1_interface = MiniscopeImagingInterface(
    ...     folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5" / "15_03_28" / "Miniscope")
    ... )
    >>> acquisition1_interface.set_aligned_starting_time(0.0)
    >>>
    >>> # Acquisition 2 starts 180 seconds after acquisition 1 (preserving the time gap)
    >>> acquisition2_interface = MiniscopeImagingInterface(
    ...     folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5" / "15_06_28" / "Miniscope")
    ... )
    >>> acquisition2_interface.set_aligned_starting_time(180.0)
    >>>
    >>> # Compose using ConverterPipe with descriptive names
    >>> # Each interface creates its own OnePhotonSeries
    >>> converter = ConverterPipe(data_interfaces={
    ...     "MiniscopeAcquisition1": acquisition1_interface,
    ...     "MiniscopeAcquisition2": acquisition2_interface
    ... })
    >>>
    >>> # Configure metadata (session_start_time is automatically extracted from first acquisition)
    >>> metadata = converter.get_metadata()
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> metadata["NWBFile"]["session_start_time"] = session_start_time.replace(tzinfo=ZoneInfo("US/Pacific"))
    >>>
    >>> # Add a second OnePhotonSeries entry to metadata with a unique name
    >>> acquisition2_metadata = metadata["Ophys"]["OnePhotonSeries"][0].copy()
    >>> acquisition2_metadata["name"] = "OnePhotonSeriesAcquisition2"
    >>> metadata["Ophys"]["OnePhotonSeries"].append(acquisition2_metadata)
    >>> metadata["Ophys"]["OnePhotonSeries"][0]["name"] = "OnePhotonSeriesAcquisition1"
    >>>
    >>> # Use conversion_options to specify which photon_series_index each interface should use
    >>> conversion_options = {
    ...     "MiniscopeAcquisition1": {"photon_series_index": 0},
    ...     "MiniscopeAcquisition2": {"photon_series_index": 1}
    ... }
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(
    ...     nwbfile_path=nwbfile_path,
    ...     metadata=metadata,
    ...     conversion_options=conversion_options,
    ...     overwrite=True
    ... )

Note that unlike ``MiniscopeConverter`` which concatenates all acquisitions into a single ``OnePhotonSeries``,
using ``ConverterPipe`` with multiple ``MiniscopeImagingInterface`` instances writes each Miniscope acquisition
as a separate ``OnePhotonSeries`` object in the NWB file. This gives you more control over how each acquisition
is represented and named.

If your acquisitions were **simultaneous** (e.g., recording from two brain regions at the same time), you would
NOT need to use ``set_aligned_starting_time()`` - each interface would have its own ``OnePhotonSeries`` with
naturally synchronized timestamps.

To summarize the workflow for aggregating multiple Miniscope acquisitions:

1. Create a ``MiniscopeImagingInterface`` for each folder with data.
2. For sequential acquisitions, use ``set_aligned_starting_time()`` to align timestamps
3. Combine interfaces with ``ConverterPipe`` using descriptive names
4. Configure metadata with unique ``OnePhotonSeries`` names and use ``photon_series_index`` in conversion options
5. (Optional) Add behavioral video using :py:class:`~neuroconv.datainterfaces.behavior.video.videodatainterface.VideoInterface`
