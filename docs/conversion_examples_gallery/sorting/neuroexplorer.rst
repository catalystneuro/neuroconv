NeuroExplorer sorting data conversion
-------------------------------------

Install NeuroConv with the additional dependencies necessary for reading NeuroExplorer data.

.. code-block:: bash

    pip install "neuroconv[neuroexplorer]"

Convert the sorted units of a NeuroExplorer file (.nex) to NWB using
:py:class:`~neuroconv.datainterfaces.ecephys.neuroexplorer.neuroexplorerdatainterface.NeuroExplorerSortingInterface`.
Each neuron variable in the file becomes a unit, named after the variable.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import NeuroExplorerSortingInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/neuroexplorer/File_neuroexplorer_1.nex"
    >>> # Change the file_path to the location in your system
    >>> interface = NeuroExplorerSortingInterface(file_path=file_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # The file does not store when the session started, so it has to be added
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
