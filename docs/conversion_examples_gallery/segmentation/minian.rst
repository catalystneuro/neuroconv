Minian
------

Install NeuroConv with the additional dependencies necessary for reading Minian data.

.. code-block:: bash

    pip install "neuroconv[minian]"

Convert Minian segmentation data to NWB using :py:class:`~neuroconv.datainterfaces.ophys.minian.miniandatainterface.MinianSegmentationInterface`.

**Important Note on Sampling Frequency:**
Minian does not store sampling frequency information in its native output. For NWB conversion, you must provide either:

1. **sampling_frequency** parameter (recommended for regular sampling)
2. **timeStamps.csv file** containing frame timestamps (often copied from Miniscope outputs)

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import MinianSegmentationInterface
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "segmentation_datasets" / "minian" / "segmented_data_3units_100frames"
    >>>
    >>> # Option 1: Provide sampling frequency directly (most common)
    >>> interface = MinianSegmentationInterface(
    ...     folder_path=folder_path,
    ...     sampling_frequency=20.0,  # Hz
    ...     verbose=False
    ... )
    >>>
    >>> # Option 2: Use existing timeStamps.csv (default location: folder_path/timeStamps.csv)
    >>> # interface = MinianSegmentationInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> # Option 3: Specify custom timestamps file location
    >>> # timestamps_path = folder_path / "custom_timeStamps.csv"
    >>> # interface = MinianSegmentationInterface(
    >>> #     folder_path=folder_path,
    >>> #     timestamps_path=timestamps_path,
    >>> #     verbose=False
    >>> # )
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
