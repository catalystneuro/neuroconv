CaImAn
------

Install NeuroConv with the additional dependencies necessary for reading CaImAn data.

.. code-block:: bash

    pip install "neuroconv[minian]"

Convert Minian segmentation data to NWB using :py:class:`~neuroconv.datainterfaces.ophys.minian.miniandatainterface.MinianSegmentationInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import MinianSegmentationInterface
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "segmentation_datasets" / "minian" / "segmented_data_3units_100frames"
    >>> interface = MinianSegmentationInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)