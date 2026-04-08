XClust data conversion
----------------------

Install NeuroConv with the additional dependencies necessary for reading XClust data.

.. code-block:: bash

    pip install "neuroconv[xclust]"

Convert XClust sorting data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.xclust.xclustdatainterface.XClustSortingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import XClustSortingInterface
    >>>
    >>> # For this interface we need to pass the folder containing .CEL files
    >>> folder_path = f"{ECEPHY_DATA_PATH}/xclust/TT6"
    >>> # Change the folder_path to the location in your system
    >>> # The sampling frequency must be provided as .CEL files do not contain this information
    >>> interface = XClustSortingInterface(folder_path=folder_path, sampling_frequency=30_000.0, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific")).isoformat()
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
