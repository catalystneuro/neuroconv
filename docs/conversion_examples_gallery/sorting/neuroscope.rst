NeuroScope sorting data conversion
----------------------------------

Install NeuroConv with the additional dependencies necessary for reading neuroscope data.

.. code-block:: bash

    pip install neuroconv[neuroscope]

Convert NeuroScope sorting data to NWB using
:py:class:`~neuroconv.datainterfaces.ecephys.neuroscope.neuroscopedatainterface.NeuroScopeSortingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import NeuroScopeSortingInterface
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/neuroscope/dataset_1"
    >>> xml_file_path = folder_path + "/YutaMouse42-151117.xml"
    >>> # Neuroscope sorting requires both the folder_path (containing the .clu and .res files.)and the xml_file_path
    >>> interface = NeuroScopeSortingInterface(folder_path=folder_path, xml_file_path=xml_file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>>  # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
