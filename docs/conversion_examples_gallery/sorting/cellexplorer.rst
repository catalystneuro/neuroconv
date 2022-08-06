Cell Explorer data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Convert cell explorer sorting data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.cellexplorer.cellexplorerdatainterface.CellExplorerSortingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces.ecephys.cellexplorer import CellExplorerSortingInterface
    >>>
    >>> # For this interface we need to pass the location of the ``cellinfo.mat`` file
    >>> file_path = f"{ECEPHY_DATA_PATH}/cellexplorer/dataset_1/20170311_684um_2088um_170311_134350.spikes.cellinfo.mat"
    >>> # Change the file_path to the location in your system
    >>> interface = CellExplorerSortingInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> tzinfo = tz.gettz("US/Pacific")
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific")).isoformat()
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    >>>
    >>> # If the conversion was successful this should evaluate to ``True`` as the file was created.
    >>> Path(nwbfile_path).is_file()
    True
