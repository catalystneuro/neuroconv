Miniscope data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading Miniscope data.

.. code-block:: bash

    pip install "neuroconv[miniscope]"

Miniscope simultaneously records optical physiology and behavior in the form of video data.

Miniscope Converter
~~~~~~~~~~~~~~~~~~~

The :py:class:`~neuroconv.datainterfaces.ophys.miniscope.miniscopeconverter.MiniscopeConverter` follows the folder
hierarchy recorded by the Miniscope acquisition software. That layout is defined by the
``directoryStructure`` array in ``UserConfigFile.json``—many templates include ``"date"`` and ``"time"`` keys (yielding
``YYYY_MM_DD/HH_MM_SS`` folders), but users can replace those entries with any fields they prefer. The converter reads
that configuration to discover session folders and per-device subdirectories, combining imaging and behavioral video
streams into a single NWB conversion. Behavioral video is handled automatically when present in the dataset.


.. code-block:: python

    >>> from pathlib import Path
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.converters import MiniscopeConverter
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "dual_miniscope_with_config"
    >>> converter = MiniscopeConverter(
    ...     folder_path=folder_path,
    ...     user_configuration_file_path=folder_path / "UserConfigFile.json",
    ...     verbose=False,
    ... )
    >>>
    >>> metadata = converter.get_metadata()
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=ZoneInfo("US/Pacific")))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

If the configuration file is unavailable, the converter assumes the legacy layout used by historical datasets: each recording is
stored in a timestamp-named folder that contains ``Miniscope/`` and optional ``BehavCam_*/`` subdirectories with their
own ``metaData.json`` and ``timeStamps.csv`` files. For other arrangements, supply ``UserConfigFile.json`` so the
converter can follow the declared directory structure.

**Important:** The converter concatenates all recordings into a single continuous data stream. Timestamps are
preserved to maintain the actual time gaps between acquisitions. For example, if you have three acquisitions at
different times, they will appear as one continuous ``OnePhotonSeries`` with timestamps showing large intervals (e.g.,
180 seconds) between the last frame of one acquisition and the first frame of the next.

Miniscope Imaging Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :py:class:`~neuroconv.datainterfaces.ophys.miniscope.MiniscopeImagingInterface` provides a flexible interface
for converting imaging data from a single Miniscope acquisition. It supports two usage modes to accommodate
different folder structures and data organizations.

**Standard Usage with folder_path:**

The interface expects a folder with the following structure:

.. code-block::

    miniscope_folder/
    ├── 0.avi                  # video file 1
    ├── 1.avi                  # video file 2
    ├── 2.avi                  # video file 3
    ├── ...                    # additional video files
    ├── metaData.json          # required configuration file
    └── timeStamps.csv         # optional timestamps file

.. code-block:: python

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
    >>> # For data provenance we can add the time zone information to the conversion
    >>> metadata["NWBFile"]["session_start_time"] = session_start_time.replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Convert to NWB
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

**Alternative Parameters for Custom File Locations:**

If your data is organized differently than the format above (e.g., you have changed the names, or the
configuration file or timestamps are in another directory), you can specify the structure using the following parameters:

- ``file_paths``: List of .avi file paths (must be named 0.avi, 1.avi, 2.avi, ...) from the same acquisition
- ``configuration_file_path``: Path to the metaData.json configuration file (required)
- ``timeStamps_file_path``: Optional path to the timeStamps.csv file. If not provided, timestamps will be generated as regular intervals based on the sampling frequency

For more information see the
:py:class:`~neuroconv.datainterfaces.ophys.miniscope.MiniscopeImagingInterface` docstring.

Combining Multiple Acquisitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :py:class:`~neuroconv.nwbconverter.ConverterPipe` allows you to assemble multiple interfaces
into a single converter for complex experimental sessions with multiple data streams and flexible folder structures.

To illustrate how a workflow with :py:class:`~neuroconv.nwbconverter.ConverterPipe` works, we'll use the same folder structure that :py:class:`~neuroconv.datainterfaces.ophys.miniscope.miniscopeconverter.MiniscopeConverter`
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
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
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

When you instantiate multiple ``MiniscopeImagingInterface`` objects directly they still produce individual
``OnePhotonSeries`` entries—exactly what happens under the hood when ``MiniscopeConverter`` discovers multiple
segments for a device. With ``ConverterPipe`` you can configure metadata and conversion options explicitly, while
``MiniscopeConverter`` handles that bookkeeping automatically based on the Miniscope configuration.

If your acquisitions were **simultaneous** (e.g., recording from two brain regions at the same time), you would
NOT need to use ``set_aligned_starting_time()`` - each interface would have its own ``OnePhotonSeries`` with
timestamps that naturally start at the same relative time (both starting at 0.0 seconds).

To summarize the workflow for aggregating multiple Miniscope acquisitions:

1. Create a ``MiniscopeImagingInterface`` for each folder with data.
2. For sequential acquisitions, use ``set_aligned_starting_time()`` to set the starting time for each acquisition to preserve the temporal relationship between them
3. Combine interfaces with ``ConverterPipe`` using descriptive names
4. Configure metadata with unique ``OnePhotonSeries`` names and use ``photon_series_index`` in conversion options
5. (Optional) Add behavioral video using :py:class:`~neuroconv.datainterfaces.behavior.video.externalvideodatainterface.ExternalVideoInterface`
